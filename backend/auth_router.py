"""
Authentication routes for Family Hub
Handles login, logout, token refresh, and user management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database import get_db, User
from auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    get_current_user,
    get_current_active_user,
    get_current_admin_user,
    set_auth_cookies,
    clear_auth_cookies,
    check_rate_limit,
    log_login_attempt,
    get_password_hash,
    SECURE_COOKIES,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# === PYDANTIC MODELS ===

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
    full_name: Optional[str]
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]


class CreateUserRequest(BaseModel):
    username: str
    email: str  # Changed from EmailStr to str (email-validator not needed)
    password: str
    full_name: Optional[str] = None
    is_admin: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateUserRequest(BaseModel):
    username: Optional[str] = None  # not used for updates but tolerated
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str


# === AUTHENTICATION ENDPOINTS ===

@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login endpoint - authenticates user and returns JWT tokens

    Security features:
    - Rate limiting (5 attempts per 15 minutes)
    - Failed login tracking
    - Secure HTTP-only cookies
    """

    ip_address = request.client.host if request.client else "unknown"

    # Check rate limit
    if not check_rate_limit(login_data.username, ip_address, db):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )

    # Authenticate user
    user = authenticate_user(login_data.username, login_data.password, db)

    if not user:
        # Log failed attempt
        log_login_attempt(login_data.username, ip_address, success=False, db=db)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log successful attempt
    log_login_attempt(login_data.username, ip_address, success=True, db=db)

    # Create tokens
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(user.id, db, request)

    # Set secure cookies
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_admin": user.is_admin
        }
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Logout endpoint - revokes refresh token and clears cookies
    """

    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        # Revoke refresh token
        revoke_refresh_token(refresh_token, db)

    # Clear authentication cookies
    clear_auth_cookies(response)

    return {"message": "Successfully logged out"}


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Token refresh endpoint - exchanges refresh token for new access token
    """

    # Get refresh token from cookie
    refresh_token_str = request.cookies.get("refresh_token")

    if not refresh_token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found"
        )

    # Verify refresh token
    db_token = verify_refresh_token(refresh_token_str, db)

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Get user
    user = db.query(User).filter(User.id == db_token.user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Create new access token
    access_token = create_access_token(data={"sub": user.username})

    # Update access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,  # Use configurable setting
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user information
    """
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Change user password
    """
    from auth import verify_password

    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Password changed successfully"}


# === USER MANAGEMENT (ADMIN ONLY) ===

@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Create new user (admin only)
    """

    # Check if username exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        is_admin=user_data.is_admin
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    List all users (admin only)
    """
    users = db.query(User).all()
    return users


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Delete user (admin only)
    """

    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    db.delete(user)
    db.commit()

    return {"message": f"User {user.username} deleted successfully"}


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    updates: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Update user fields (admin only): email, full_name, is_admin, is_active
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent self-demotion and self-deactivation
    if user.id == current_user.id:
        if updates.is_admin is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove your own admin rights")
        if updates.is_active is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    if updates.email is not None and updates.email != user.email:
        # Ensure unique email
        existing_email = db.query(User).filter(User.email == updates.email).first()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        user.email = updates.email

    if updates.full_name is not None:
        user.full_name = updates.full_name

    if updates.is_admin is not None:
        user.is_admin = bool(updates.is_admin)

    if updates.is_active is not None:
        user.is_active = bool(updates.is_active)

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Reset a user's password (admin only)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not payload.new_password or len(payload.new_password) < 4:
        # keep minimal requirement for private setup
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short")

    user.hashed_password = get_password_hash(payload.new_password)
    user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": f"Password for {user.username} updated"}


# === HEALTH CHECK ===

@router.get("/health")
async def auth_health():
    """Authentication system health check"""
    return {
        "status": "healthy",
        "service": "authentication",
        "endpoints": [
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/refresh",
            "/api/auth/me",
            "/api/auth/change-password"
        ]
    }
