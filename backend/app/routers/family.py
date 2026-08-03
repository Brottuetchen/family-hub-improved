"""Familienmitglieder-Verwaltung."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user, get_current_user
from app.models.family import FamilyMember
from app.models.user import User

router = APIRouter(prefix="/api/family", tags=["family"])


class MemberRequest(BaseModel):
    name: str
    color: str = "#4f46e5"
    avatar: Optional[str] = None
    role: str = "partner"
    birthday: Optional[str] = None


class MemberResponse(BaseModel):
    id: int
    name: str
    color: str
    avatar: Optional[str] = None
    role: str
    birthday: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[MemberResponse])
async def list_members(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(FamilyMember).all()


@router.post("", response_model=MemberResponse)
async def create_member(data: MemberRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    member = FamilyMember(**data.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.patch("/{member_id}", response_model=MemberResponse)
async def update_member(member_id: int, data: MemberRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    for key, value in data.model_dump().items():
        setattr(member, key, value)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}")
async def delete_member(member_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()
    return {"message": "deleted"}
