"""
Authentication module for ChatTutor.

- **登录密码**：使用 bcrypt 加盐哈希存储与校验（OWASP 推荐）。**不要**用 SHA256
  等快速哈希存密码（易被 GPU 暴力破解）。
- **JWT**：签名算法为 **HS256**（HMAC-SHA256），指「令牌签名」，与「密码存储哈希」是两件事。

Provides:
- Password hashing and verification (bcrypt)
- JWT token creation and validation
- OAuth2 password bearer scheme
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# 直接使用 bcrypt 库，避免 passlib 与 bcrypt 4.1+ 初始化自检不兼容（detect_wrap_bug / __about__）。
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a password using bcrypt（与历史 passlib 生成的 $2b$ 串互相校验兼容）。"""
    pw = password.encode("utf-8")
    if len(pw) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"Password too long (max {_BCRYPT_MAX_BYTES} bytes)")
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash string."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("ascii"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, username: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's UUID as string
        username: User's username
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    to_encode = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """Extract user ID from a JWT token."""
    payload = decode_access_token(token)
    if payload:
        return payload.get("sub")
    return None


def get_username_from_token(token: str) -> Optional[str]:
    """Extract username from a JWT token."""
    payload = decode_access_token(token)
    if payload:
        return payload.get("username")
    return None
