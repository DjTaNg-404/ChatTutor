"""
Rate limiting middleware for ChatTutor API.

Uses slowapi (limits library) for rate limiting based on:
- User ID (from JWT token)
- IP address (fallback)

Limits:
- /api/v1/chat: 10 requests per minute per user
- /api/v1/chat/stream: 5 requests per minute per user
- /api/v1/auth/login: 5 requests per minute per IP
"""

from typing import Callable, Optional
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def get_user_identifier(request: Request) -> Optional[str]:
    """
    Get user identifier for rate limiting.

    Priority:
    1. User ID from JWT token (Authorization header)
    2. Remote IP address (fallback)
    """
    # Try to get user ID from JWT token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Decode token without validation to get user ID
        # (validation is done by auth dependency)
        try:
            from app.core.auth import decode_access_token
            payload = decode_access_token(token)
            if payload:
                user_id = payload.get("sub")
                if user_id:
                    return f"user:{user_id}"
        except Exception:
            pass

    # Fallback to IP address
    return f"ip:{get_remote_address()}"


# Create limiter instance
limiter = Limiter(key_func=get_user_identifier)


def setup_rate_limiting(app: FastAPI) -> None:
    """
    Setup rate limiting for the FastAPI application.

    Call this after creating the FastAPI app.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    logger.info(
        "Rate limiting enabled",
        default_limits=["10/minute per user"],
    )


def rate_limit(limit: str):
    """
    Decorator for rate limiting routes.

    Usage:
        @router.post("/chat")
        @rate_limit("10/minute")
        async def chat_endpoint(...):
            ...
    """
    return limiter.limit(limit)


def get_retry_after(retry_after: Optional[int] = None) -> int:
    """Calculate retry-after header value in seconds."""
    if retry_after:
        return retry_after
    return 60  # Default to 1 minute
