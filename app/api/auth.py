"""
Authentication API routes.

Endpoints:
- POST /register: Register a new user
- POST /login: Login and get JWT token
- POST /refresh: Refresh JWT token
- GET /me: Get current user info
"""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.db.crud import create_user, get_user_by_username
from app.db.models import User
from app.core.auth import hash_password, verify_password, create_access_token
from app.core.db_errors import await_db
from app.core.deps import get_current_user
from app.core.config import settings


router = APIRouter()


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """User response schema."""
    id: str
    username: str
    created_at: str


class RegisterRequest(BaseModel):
    """Register request schema."""
    username: str
    password: str


class LoginJsonRequest(BaseModel):
    """JSON 登录体（与 OAuth2 表单登录等价，便于前端 fetch）。"""
    username: str
    password: str


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user.

    - **username**: Must be at least 3 characters
    - **password**: Must be at least 6 characters
    """
    # Validate input
    if len(request.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters",
        )
    if len(request.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters",
        )

    # Check if user already exists
    existing_user = await await_db(get_user_by_username(db, request.username))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Create user
    hashed_password = hash_password(request.password)
    user = await await_db(create_user(db, username=request.username, hashed_password=hashed_password))

    # Generate token
    access_token = create_access_token(
        user_id=str(user.id),
        username=user.username,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Login with username and password.

    Returns JWT token for authenticated user.
    """
    # Find user
    user = await await_db(get_user_by_username(db, form_data.username))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate token
    access_token = create_access_token(
        user_id=str(user.id),
        username=user.username,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/login/json", response_model=TokenResponse)
async def login_json(
    body: LoginJsonRequest,
    db: AsyncSession = Depends(get_db),
):
    """使用 JSON body 登录（username/password），返回与 /login 相同的 JWT。"""
    user = await await_db(get_user_by_username(db, body.username))
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(user_id=str(user.id), username=user.username)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user information.

    Requires valid JWT token in Authorization header.
    """
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        created_at=current_user.created_at.isoformat(),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: User = Depends(get_current_user),
):
    """
    Refresh JWT token.

    Requires valid JWT token in Authorization header.
    Returns a new token with fresh expiration.
    """
    access_token = create_access_token(
        user_id=str(current_user.id),
        username=current_user.username,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )
