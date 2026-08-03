"""Paket-Tracking-Endpunkte."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.package import Package
from app.models.user import User

router = APIRouter(prefix="/api/packages", tags=["packages"])


class PackageRequest(BaseModel):
    carrier: str
    tracking_number: Optional[str] = None
    description: Optional[str] = None
    status: str = "in_transit"
    expected_at: Optional[datetime] = None


class PackageResponse(BaseModel):
    id: int
    carrier: str
    tracking_number: Optional[str] = None
    description: Optional[str] = None
    status: str
    expected_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[PackageResponse])
async def list_packages(include_delivered: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Package)
    if not include_delivered:
        query = query.filter(Package.status != "delivered")
    return query.order_by(Package.expected_at.is_(None), Package.expected_at.asc()).all()


@router.post("", response_model=PackageResponse)
async def create_package(data: PackageRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    package = Package(**data.model_dump())
    db.add(package)
    db.commit()
    db.refresh(package)
    return package


@router.patch("/{package_id}", response_model=PackageResponse)
async def update_package(package_id: int, data: PackageRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    package = db.query(Package).filter(Package.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(package, key, value)
    db.commit()
    db.refresh(package)
    return package


@router.delete("/{package_id}")
async def delete_package(package_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    package = db.query(Package).filter(Package.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    db.delete(package)
    db.commit()
    return {"message": "deleted"}
