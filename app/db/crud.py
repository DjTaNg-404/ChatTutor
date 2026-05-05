"""
CRUD Operations for ChatTutor database models.

Provides reusable database operations for sessions, tasks, notes, and profiles.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TypeVar
from uuid import UUID

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User, Session, Task, Note, LearnerProfile, KGGraph, Embedding, NoteType, TaskStatus
from app.core.models import AgentState


T = TypeVar("T")


# ===== User CRUD =====

async def create_user(
    db: AsyncSession,
    username: str,
    hashed_password: str,
) -> User:
    """Create a new user."""
    user = User(username=username, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get user by username."""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """Get user by ID."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


# ===== Session CRUD =====

async def save_session(
    db: AsyncSession,
    user_id: UUID,
    session_id: str,
    task_id: str,
    messages: List[Dict[str, Any]],
    topic: Optional[str] = None,
    conversation_summary: Optional[str] = None,
    summarized_msg_count: int = 0,
    is_summarizing: bool = False,
) -> Session:
    """
    Save or update a session.
    Uses upsert pattern for idempotency.
    """
    # Try to find existing session
    result = await db.execute(
        select(Session).where(
            Session.session_id == session_id,
            Session.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()

    if session is None:
        # Create new session
        session = Session(
            user_id=user_id,
            session_id=session_id,
            task_id=task_id,
            topic=topic,
            messages=messages,
            conversation_summary=conversation_summary,
            summarized_msg_count=summarized_msg_count,
            is_summarizing=is_summarizing,
        )
        db.add(session)
    else:
        # Update existing session
        session.task_id = task_id
        session.topic = topic
        session.messages = messages
        session.conversation_summary = conversation_summary
        session.summarized_msg_count = summarized_msg_count
        session.is_summarizing = is_summarizing
        session.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(session)
    return session


async def load_session(
    db: AsyncSession,
    user_id: UUID,
    session_id: str,
) -> Optional[Session]:
    """Load a session by session_id and user_id."""
    result = await db.execute(
        select(Session).where(
            Session.session_id == session_id,
            Session.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    user_id: UUID,
    task_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Session]:
    """List sessions for a user, optionally filtered by task_id."""
    query = select(Session).where(Session.user_id == user_id)

    if task_id:
        query = query.where(Session.task_id == task_id)

    query = query.order_by(Session.updated_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_session(
    db: AsyncSession,
    user_id: UUID,
    session_id: str,
) -> bool:
    """Delete a session."""
    result = await db.execute(
        delete(Session).where(
            Session.session_id == session_id,
            Session.user_id == user_id,
        )
    )
    await db.commit()
    return result.rowcount > 0


async def set_session_summarizing(
    db: AsyncSession,
    user_id: UUID,
    session_id: str,
    is_summarizing: bool,
) -> Optional[Session]:
    """Set the is_summarizing flag for a session."""
    await db.execute(
        update(Session)
        .where(
            Session.session_id == session_id,
            Session.user_id == user_id,
        )
        .values(is_summarizing=is_summarizing)
    )
    await db.commit()

    # Return updated session
    result = await db.execute(
        select(Session).where(Session.session_id == session_id)
    )
    return result.scalar_one_or_none()


# ===== Task CRUD =====

async def get_or_create_task(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
    title: Optional[str] = None,
    icon: Optional[str] = None,
    status: str = "active",
) -> Task:
    """Get existing task or create new one."""
    result = await db.execute(
        select(Task).where(
            Task.task_id == task_id,
            Task.user_id == user_id,
        )
    )
    task = result.scalar_one_or_none()

    if task is None:
        task = Task(
            user_id=user_id,
            task_id=task_id,
            title=title,
            icon=icon,
            status=status,
        )
        db.add(task)
    else:
        # Update if title or icon provided
        if title:
            task.title = title
        if icon:
            task.icon = icon
        task.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(task)
    return task


async def update_task(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
    title: Optional[str] = None,
    icon: Optional[str] = None,
    status: Optional[str] = None,
    plan_json: Optional[Dict[str, Any]] = None,
) -> Optional[Task]:
    """Update task fields."""
    result = await db.execute(
        select(Task).where(
            Task.task_id == task_id,
            Task.user_id == user_id,
        )
    )
    task = result.scalar_one_or_none()

    if task is None:
        return None

    if title:
        task.title = title
    if icon:
        task.icon = icon
    if status:
        task.status = status
    if plan_json:
        task.plan_json = plan_json

    task.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(task)
    return task


async def list_tasks(
    db: AsyncSession,
    user_id: UUID,
    status: Optional[str] = None,
) -> List[Task]:
    """List tasks for a user."""
    query = select(Task).where(Task.user_id == user_id)

    if status:
        query = query.where(Task.status == status)

    query = query.order_by(Task.updated_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


async def fetch_task_plan_json(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
) -> Dict[str, Any]:
    """Return merged plan/session JSON stored on Task.plan_json for this user+task."""
    result = await db.execute(
        select(Task).where(
            Task.user_id == user_id,
            Task.task_id == task_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task or not task.plan_json:
        return {}
    data = dict(task.plan_json) if isinstance(task.plan_json, dict) else {}
    data.pop("nextSteps", None)
    return data


async def merge_task_plan_json(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge ``plan`` into Task.plan_json (create task row if missing)."""
    result = await db.execute(
        select(Task).where(
            Task.user_id == user_id,
            Task.task_id == task_id,
        )
    )
    task = result.scalar_one_or_none()
    base: Dict[str, Any] = {}
    if task and isinstance(task.plan_json, dict):
        base = dict(task.plan_json)
    if plan:
        base.update(plan)
    base.pop("nextSteps", None)
    if task is None:
        task = Task(
            user_id=user_id,
            task_id=task_id,
            title=(base.get("taskTitle") or task_id)[:200],
            icon=base.get("taskIcon") or "✨",
            status=TaskStatus.ACTIVE.value,
            plan_json=base,
        )
        db.add(task)
    else:
        task.plan_json = base
        task.updated_at = datetime.now(timezone.utc)
        if base.get("taskTitle"):
            task.title = str(base["taskTitle"])[:200]
        if base.get("taskIcon"):
            task.icon = str(base["taskIcon"])[:50]
    await db.commit()
    await db.refresh(task)
    return dict(task.plan_json or {})


async def delete_task(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
) -> bool:
    """Delete a task."""
    result = await db.execute(
        delete(Task).where(
            Task.task_id == task_id,
            Task.user_id == user_id,
        )
    )
    await db.commit()
    return result.rowcount > 0


# ===== Note CRUD =====

async def save_note(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
    note_type: str,
    content: str,
    session_id: Optional[str] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Note:
    """Save a learning note."""
    note = Note(
        user_id=user_id,
        task_id=task_id,
        session_id=session_id,
        note_type=note_type,
        content=content,
        metadata_json=metadata_json,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def list_notes(
    db: AsyncSession,
    user_id: UUID,
    task_id: Optional[str] = None,
    note_type: Optional[str] = None,
) -> List[Note]:
    """List notes for a user."""
    query = select(Note).where(Note.user_id == user_id)

    if task_id:
        query = query.where(Note.task_id == task_id)
    if note_type:
        query = query.where(Note.note_type == note_type)

    query = query.order_by(Note.created_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task_note(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
    note_type: str = "task",
) -> Optional[Note]:
    """Get the latest note for a task."""
    result = await db.execute(
        select(Note)
        .where(
            Note.user_id == user_id,
            Note.task_id == task_id,
            Note.note_type == note_type,
        )
        .order_by(Note.created_at.desc())
    )
    return result.scalar_one_or_none()


# ===== Learner Profile CRUD =====

async def get_or_create_profile(
    db: AsyncSession,
    user_id: UUID,
) -> LearnerProfile:
    """Get existing profile or create new one."""
    result = await db.execute(
        select(LearnerProfile).where(LearnerProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = LearnerProfile(user_id=user_id, profile_json={})
        db.add(profile)
    else:
        profile.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(profile)
    return profile


async def update_profile(
    db: AsyncSession,
    user_id: UUID,
    profile_json: Dict[str, Any],
) -> Optional[LearnerProfile]:
    """Update user profile."""
    result = await db.execute(
        select(LearnerProfile).where(LearnerProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        return None

    profile.profile_json = profile_json
    profile.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(profile)
    return profile


# ===== KG Graph CRUD =====

async def save_kg_graph(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
    graph_data: Dict[str, Any],
    metadata_json: Optional[Dict[str, Any]] = None,
) -> KGGraph:
    """Save or update knowledge graph."""
    result = await db.execute(
        select(KGGraph).where(
            KGGraph.user_id == user_id,
            KGGraph.task_id == task_id,
        )
    )
    kg_graph = result.scalar_one_or_none()

    if kg_graph is None:
        kg_graph = KGGraph(
            user_id=user_id,
            task_id=task_id,
            graph_data=graph_data,
            metadata_json=metadata_json,
        )
        db.add(kg_graph)
    else:
        kg_graph.graph_data = graph_data
        kg_graph.metadata_json = metadata_json
        kg_graph.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(kg_graph)
    return kg_graph


async def get_kg_graph(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
) -> Optional[KGGraph]:
    """Get knowledge graph for a task."""
    result = await db.execute(
        select(KGGraph).where(
            KGGraph.user_id == user_id,
            KGGraph.task_id == task_id,
        )
    )
    return result.scalar_one_or_none()


# ===== Embedding CRUD =====

async def add_embedding(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
    session_id: str,
    content: str,
    embedding: List[float],
    metadata_json: Optional[Dict[str, Any]] = None,
) -> Embedding:
    """Add a vector embedding."""
    emb = Embedding(
        user_id=user_id,
        task_id=task_id,
        session_id=session_id,
        content=content,
        embedding=embedding,
        metadata_json=metadata_json,
    )
    db.add(emb)
    await db.commit()
    await db.refresh(emb)
    return emb
