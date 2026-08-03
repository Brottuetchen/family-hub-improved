"""Finanzen: wiederkehrende Kosten, Budgetübersicht.

Verwaltet Daueraufträge/Versicherungen/Abos und berechnet die monatliche
Gesamtbelastung (normalisiert über verschiedene Intervalle).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_min_role
from app.models.finance import RecurringExpense
from app.models.user import ROLE_PARTNER, User

router = APIRouter(prefix="/api/finance", tags=["finance"])

# Faktor zur Normalisierung auf einen Monat.
_MONTHLY_FACTOR = {"weekly": 52 / 12, "monthly": 1.0, "quarterly": 1 / 3, "yearly": 1 / 12}


class ExpenseRequest(BaseModel):
    name: str
    amount: float = 0.0
    currency: str = "EUR"
    interval: str = "monthly"
    category: str = "other"
    due_day: Optional[int] = None
    active: bool = True
    notes: Optional[str] = None


class ExpenseResponse(BaseModel):
    id: int
    name: str
    amount: float
    currency: str
    interval: str
    category: str
    due_day: Optional[int] = None
    active: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("/expenses", response_model=list[ExpenseResponse])
async def list_expenses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(RecurringExpense).order_by(RecurringExpense.category.asc()).all()


@router.post("/expenses", response_model=ExpenseResponse)
async def create_expense(data: ExpenseRequest, db: Session = Depends(get_db), current_user: User = Depends(require_min_role(ROLE_PARTNER))):
    expense = RecurringExpense(**data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(expense_id: int, data: ExpenseRequest, db: Session = Depends(get_db), current_user: User = Depends(require_min_role(ROLE_PARTNER))):
    expense = db.query(RecurringExpense).filter(RecurringExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(expense, key, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_min_role(ROLE_PARTNER))):
    expense = db.query(RecurringExpense).filter(RecurringExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"message": "deleted"}


@router.get("/overview")
async def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    expenses = db.query(RecurringExpense).filter(RecurringExpense.active == True).all()  # noqa: E712
    monthly_total = 0.0
    by_category: dict[str, float] = {}
    for e in expenses:
        monthly = (e.amount or 0.0) * _MONTHLY_FACTOR.get(e.interval, 1.0)
        monthly_total += monthly
        by_category[e.category] = round(by_category.get(e.category, 0.0) + monthly, 2)
    return {
        "monthly_total": round(monthly_total, 2),
        "yearly_total": round(monthly_total * 12, 2),
        "currency": "EUR",
        "by_category": by_category,
        "count": len(expenses),
    }
