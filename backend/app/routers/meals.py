"""Essensplanung (Wochenplan) + automatische Einkaufsliste."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.connectors.registry import registry
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.recipe import MealPlanEntry, Recipe
from app.models.user import User

router = APIRouter(prefix="/api/meals", tags=["meals"])


class MealEntryRequest(BaseModel):
    date: str  # YYYY-MM-DD
    meal_type: str = "dinner"
    recipe_id: Optional[int] = None
    custom_title: Optional[str] = None


@router.get("/plan")
async def get_plan(days: int = 7, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    today = date.today()
    end = today + timedelta(days=days)
    entries = (
        db.query(MealPlanEntry)
        .filter(MealPlanEntry.date >= today.isoformat(), MealPlanEntry.date <= end.isoformat())
        .order_by(MealPlanEntry.date.asc())
        .all()
    )
    recipes = {r.id: r.title for r in db.query(Recipe).all()}
    return [
        {
            "id": e.id,
            "date": e.date,
            "meal_type": e.meal_type,
            "recipe_id": e.recipe_id,
            "title": e.custom_title or recipes.get(e.recipe_id, "Mahlzeit"),
        }
        for e in entries
    ]


@router.post("/plan")
async def add_plan_entry(data: MealEntryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not data.recipe_id and not data.custom_title:
        raise HTTPException(status_code=400, detail="recipe_id oder custom_title erforderlich")
    entry = MealPlanEntry(
        date=data.date, meal_type=data.meal_type, recipe_id=data.recipe_id, custom_title=data.custom_title
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "date": entry.date, "meal_type": entry.meal_type}


@router.delete("/plan/{entry_id}")
async def delete_plan_entry(entry_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entry = db.query(MealPlanEntry).filter(MealPlanEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"message": "deleted"}


def _collect_ingredients(db: Session, days: int) -> List[str]:
    today = date.today()
    end = today + timedelta(days=days)
    entries = (
        db.query(MealPlanEntry)
        .filter(
            MealPlanEntry.date >= today.isoformat(),
            MealPlanEntry.date <= end.isoformat(),
            MealPlanEntry.recipe_id != None,  # noqa: E711
        )
        .all()
    )
    recipe_ids = {e.recipe_id for e in entries}
    if not recipe_ids:
        return []
    recipes = db.query(Recipe).filter(Recipe.id.in_(recipe_ids)).all()
    seen = set()
    out: List[str] = []
    for r in recipes:
        try:
            for ing in json.loads(r.ingredients_json or "[]"):
                key = ing.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    out.append(ing.strip())
        except (ValueError, TypeError):
            continue
    return out


@router.post("/shopping-list")
async def generate_shopping_list(days: int = 7, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Sammelt Zutaten aus dem Wochenplan und legt sie – wenn möglich – in KitchenOwl an."""
    ingredients = _collect_ingredients(db, days)
    if not ingredients:
        return {"ingredients": [], "added_to_kitchenowl": 0, "message": "Keine Rezepte im Zeitraum geplant."}

    added = 0
    shopping = registry.get("kitchenowl")
    if shopping and shopping.is_configured:
        for ing in ingredients:
            if await shopping.add_item(ing):
                added += 1

    return {
        "ingredients": ingredients,
        "added_to_kitchenowl": added,
        "message": f"{len(ingredients)} Zutaten gesammelt"
        + (f", {added} zu KitchenOwl hinzugefügt." if added else " (KitchenOwl nicht konfiguriert)."),
    }
