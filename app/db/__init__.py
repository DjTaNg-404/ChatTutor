"""
Database module for ChatTutor production deployment.

Provides SQLAlchemy async engine, session management, and ORM models.
"""

from app.db.engine import get_db, Base, engine, async_session_maker
from app.db.models import User, Session, Task, Note, LearnerProfile, KGGraph, Embedding

__all__ = [
    "get_db",
    "Base",
    "engine",
    "async_session_maker",
    "User",
    "Session",
    "Task",
    "Note",
    "LearnerProfile",
    "KGGraph",
    "Embedding",
]
