"""Authentifizierungs- und Benutzerverwaltungs-Endpunkte."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    authenticate_user,
    check_rate_limit,
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    get_current_admin_user,
    get_current_user,
    get_password_hash,
    log_login_attempt,
    revoke_refresh_token,
    set_auth_cookies,
    verify_password,
    verify_refresh_token,
)
from app.models.user import VALID_ROLES, User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    role: str = "partner"


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, response: Response, data: LoginRequest, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(data.username, ip, db):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts.")

    user = authenticate_user(data.username, data.password, db)
    if not user:
        log_login_attempt(data.username, ip, success=False, db=db)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    log_login_attempt(data.username, ip, success=True, db=db)
    access = create_access_token(data={"sub": user.username})
    refresh = create_refresh_token(user.id, db, request)
    set_auth_cookies(response, access, refresh)
    return {
        "access_token": access,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_admin": user.is_admin,
        },
    }


@router.post("/logout")
async def logout(request: Request, response: Response, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    token = request.cookies.get("refresh_token")
    if token:
        revoke_refresh_token(token, db)
    clear_auth_cookies(response)
    return {"message": "Successfully logged out"}


@router.post("/refresh")
async def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found")
    db_token = verify_refresh_token(token, db)
    if not db_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    access = create_access_token(data={"sub": user.username})
    response.set_cookie(key="access_token", value=access, httponly=True, samesite="lax")
    return {"access_token": access, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
async def change_password(data: ChangePasswordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


# --- User management (admin) ---

@router.get("/users", response_model=list[UserResponse])
async def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    return db.query(User).all()


@router.post("/users", response_model=UserResponse)
async def create_user(data: CreateUserRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    if data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {', '.join(sorted(VALID_ROLES))}")
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=data.role,
        is_admin=(data.role == "admin"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, updates: UpdateUserRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id and updates.role and updates.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot remove your own admin rights")
    if updates.email is not None:
        user.email = updates.email
    if updates.full_name is not None:
        user.full_name = updates.full_name
    if updates.role is not None:
        if updates.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        user.role = updates.role
        user.is_admin = updates.role == "admin"
    if updates.is_active is not None:
        user.is_active = updates.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": f"User {user.username} deleted"}
