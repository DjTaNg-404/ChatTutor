"""
SQLAlchemy ORM Models for ChatTutor.

Tables:
- users: User accounts with authentication
- sessions: Conversation sessions with messages
- tasks: Learning tasks with plans
- notes: Learning notes (daily/task/summary)
- learner_profiles: User learning profiles
- kg_graphs: Knowledge graph data
- embeddings: Vector embeddings for RAG (pgvector)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    Boolean,
    ForeignKey,
    Index,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column, declarative_base
from sqlalchemy.sql import func

from pgvector.sqlalchemy import Vector

from app.db.engine import Base


# ===== Enum Types =====

class NoteType(str, Enum):
    """Type of learning note."""
    DAILY = "daily"
    TASK = "task"
    SUMMARY = "summary"


class TaskStatus(str, Enum):
    """Status of learning task."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"


# ===== Models =====

class User(Base):
    """
    User account model.

    Stores authentication credentials and basic user info.
    """
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    sessions: Mapped[List["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notes: Mapped[List["Note"]] = relationship(
        "Note",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    profile: Mapped[Optional["LearnerProfile"]] = relationship(
        "LearnerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    embeddings: Mapped[List["Embedding"]] = relationship(
        "Embedding",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    kg_graphs: Mapped[List["KGGraph"]] = relationship(
        "KGGraph",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_users_username", "username", unique=True),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class Session(Base):
    """
    Conversation session model.

    Stores complete conversation history with messages in JSONB.
    """
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    session_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    topic: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    messages: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    conversation_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    summarized_msg_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    is_summarizing: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("ix_sessions_user_task", "user_id", "task_id"),
        Index("ix_sessions_session_id", "session_id"),
    )

    def __repr__(self) -> str:
        return f"<Session(session_id={self.session_id}, task_id={self.task_id})>"


class Task(Base):
    """
    Learning task model.

    Represents a learning subject/topic with optional plan.
    """
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=TaskStatus.ACTIVE.value,
        nullable=False,
    )
    plan_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tasks")
    notes: Mapped[List["Note"]] = relationship(
        "Note",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_tasks_user_task_id", "user_id", "task_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Task(task_id={self.task_id}, title={self.title})>"


class Note(Base):
    """
    Learning note model.

    Stores generated notes from conversations (daily/task/summary).
    """
    __tablename__ = "notes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("tasks.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    note_type: Mapped[str] = mapped_column(
        SQLEnum(NoteType),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notes")
    task: Mapped["Task"] = relationship("Task", back_populates="notes")

    __table_args__ = (
        Index("ix_notes_user_task_type", "user_id", "task_id", "note_type"),
    )

    def __repr__(self) -> str:
        return f"<Note(id={self.id}, type={self.note_type})>"


class LearnerProfile(Base):
    """
    Learner profile model.

    Stores user's learning preferences, knowledge cards, and progress.
    One row per user (upsert pattern).
    """
    __tablename__ = "learner_profiles"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    profile_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<LearnerProfile(user_id={self.user_id})>"


class KGGraph(Base):
    """
    Knowledge graph model.

    Stores knowledge graph data for tasks.
    """
    __tablename__ = "kg_graphs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    graph_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="kg_graphs")

    __table_args__ = (
        Index("ix_kg_graphs_user_task", "user_id", "task_id"),
    )

    def __repr__(self) -> str:
        return f"<KGGraph(task_id={self.task_id})>"


class Embedding(Base):
    """
    Vector embedding model for RAG.

    Uses pgvector extension for semantic search.
    Note: Requires pgvector extension installed in PostgreSQL.
    """
    __tablename__ = "embeddings"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # pgvector Vector type - dimension 384 for all-MiniLM-L6-v2
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(384),
        nullable=True,
        index=True,
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="embeddings")

    __table_args__ = (
        Index("ix_embeddings_user_task", "user_id", "task_id"),
    )

    def __repr__(self) -> str:
        return f"<Embedding(id={self.id}, task_id={self.task_id})>"
