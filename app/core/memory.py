"""
Memory module for ChatTutor - Production Version.

This module provides session and task management with dual storage:
1. Primary: PostgreSQL database (async)
2. Fallback: File I/O (for backward compatibility)

All functions maintain backward-compatible signatures for agent_builder.py.
"""

import os
import asyncio
import datetime
from typing import Dict, Any, List, Optional
from langchain_core.messages import messages_to_dict, messages_from_dict, BaseMessage
from langchain_core.messages import HumanMessage, AIMessage

from app.core.models import AgentState
from app.utils import file_io

# Use database if available (set via environment)
USE_DATABASE = os.getenv("USE_DATABASE", "false").lower() in ("1", "true", "yes", "on")

# Try to import database modules if enabled
try:
    if USE_DATABASE:
        from app.db.crud import (
            save_session as db_save_session,
            load_session as db_load_session,
            list_sessions as db_list_sessions,
            delete_session as db_delete_session,
            set_session_summarizing as db_set_session_summarizing,
            get_or_create_task,
            update_task as db_update_task,
            list_tasks as db_list_tasks,
            delete_task as db_delete_task,
            save_note,
            list_notes,
            get_task_note as db_get_task_note_orm,
            fetch_task_plan_json as db_fetch_task_plan_json,
            merge_task_plan_json as db_merge_task_plan_json,
        )
        from app.db.engine import async_session_maker
        DATABASE_AVAILABLE = True
    else:
        DATABASE_AVAILABLE = False
except (ImportError, Exception):
    DATABASE_AVAILABLE = False

# Paths Configuration (for fallback)
MEMORY_DIR = "memory/sessions"
NOTES_DIR = "memory/notes"
TASK_INDEX_DIR = "memory/task_index"
TASK_INDEX_PATH = os.path.join(TASK_INDEX_DIR, "tasks.json")

# 防重复总结标记（内存级别 + Redis if available）
_SUMMARIZING_SESSIONS = set()

# Try to import Redis for distributed locking
try:
    from app.core.redis_client import RedisSessionLock
    REDIS_AVAILABLE = True
except (ImportError, Exception):
    REDIS_AVAILABLE = False


def _get_daily_note_path(task_id: str, date: str, user_id: Optional[str] = None) -> str:
    if user_id:
        root = os.path.join(NOTES_DIR, "by_user", str(user_id), "daily", task_id)
    else:
        root = os.path.join(NOTES_DIR, "daily", task_id)
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, f"{date}.md")


def _get_task_note_path(task_id: str, user_id: Optional[str] = None) -> str:
    if user_id:
        root = os.path.join(NOTES_DIR, "by_user", str(user_id), "task")
    else:
        root = os.path.join(NOTES_DIR, "task")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, f"{task_id}.md")


def _get_task_plan_path(task_id: str, user_id: Optional[str] = None) -> str:
    if user_id:
        root = os.path.join(NOTES_DIR, "by_user", str(user_id), "task")
    else:
        root = os.path.join(NOTES_DIR, "task")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, f"{task_id}.json")


def _load_task_index() -> List[Dict[str, Any]]:
    if not os.path.exists(TASK_INDEX_PATH):
        return []
    try:
        data = file_io.load_json(TASK_INDEX_PATH)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _save_task_index(items: List[Dict[str, Any]]):
    file_io.save_json(items, TASK_INDEX_PATH)


def list_tasks(status: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List tasks for a user.

    If DATABASE_AVAILABLE and user_id is provided, query from database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio
        async def db_list():
            async with async_session_maker() as db:
                return await db_list_tasks(db=db, user_id=UUID(user_id), status=status)
        tasks = asyncio.run(db_list())
        return [
            {
                "id": t.task_id,
                "title": t.title,
                "icon": t.icon,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else "",
                "updated_at": t.updated_at.isoformat() if t.updated_at else "",
            }
            for t in tasks
        ]

    # Fallback to file-based storage
    tasks = _load_task_index()
    if user_id:
        tasks = [item for item in tasks if item.get("user_id") == user_id]
    if status:
        tasks = [item for item in tasks if item.get("status") == status]
    tasks.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return tasks


def upsert_task(
    task_id: str,
    title: str,
    icon: str,
    status: str = "active",
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upsert a task for a user.

    If DATABASE_AVAILABLE and user_id is provided, save to database.
    Otherwise, fallback to file-based storage.
    """
    now = datetime.datetime.now().isoformat()

    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio
        async def db_upsert():
            async with async_session_maker() as db:
                task_obj = await get_or_create_task(
                    db=db,
                    user_id=UUID(user_id),
                    task_id=task_id,
                    title=title,
                    icon=icon,
                    status=status,
                )
                return {
                    "id": task_obj.task_id,
                    "title": task_obj.title,
                    "icon": task_obj.icon,
                    "status": task_obj.status,
                    "created_at": task_obj.created_at.isoformat() if task_obj.created_at else "",
                    "updated_at": task_obj.updated_at.isoformat() if task_obj.updated_at else "",
                }
        return asyncio.run(db_upsert())

    # Fallback to file-based storage
    tasks = _load_task_index()
    existing = None
    for item in tasks:
        if item.get("id") == task_id:
            existing = item
            break

    if existing is None:
        existing = {
            "id": task_id,
            "created_at": now,
        }
        if user_id:
            existing["user_id"] = user_id
        tasks.insert(0, existing)

    existing.update(
        {
            "title": title,
            "icon": icon,
            "status": status,
            "updated_at": now,
        }
    )
    if user_id:
        existing["user_id"] = user_id
    _save_task_index(tasks)
    return existing


def update_task_status(
    task_id: str,
    status: str,
    user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Update task status for a user.

    If DATABASE_AVAILABLE and user_id is provided, update in database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio
        async def db_update():
            async with async_session_maker() as db:
                task_obj = await db_update_task(db=db, user_id=UUID(user_id), task_id=task_id, status=status)
                if task_obj:
                    return {
                        "id": task_obj.task_id,
                        "title": task_obj.title,
                        "icon": task_obj.icon,
                        "status": task_obj.status,
                        "created_at": task_obj.created_at.isoformat() if task_obj.created_at else "",
                        "updated_at": task_obj.updated_at.isoformat() if task_obj.updated_at else "",
                    }
                return None
        return asyncio.run(db_update())

    # Fallback to file-based storage
    now = datetime.datetime.now().isoformat()
    tasks = _load_task_index()
    for item in tasks:
        if item.get("id") == task_id and (not user_id or item.get("user_id") == user_id):
            item["status"] = status
            item["updated_at"] = now
            _save_task_index(tasks)
            return item
    return None


def update_task(
    task_id: str,
    title: Optional[str] = None,
    icon: Optional[str] = None,
    user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    更新任务的名称和/或图标

    If DATABASE_AVAILABLE and user_id is provided, update in database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio
        async def db_update():
            async with async_session_maker() as db:
                task_obj = await db_update_task(
                    db=db,
                    user_id=UUID(user_id),
                    task_id=task_id,
                    title=title,
                    icon=icon,
                )
                if task_obj:
                    return {
                        "id": task_obj.task_id,
                        "title": task_obj.title,
                        "icon": task_obj.icon,
                        "status": task_obj.status,
                        "created_at": task_obj.created_at.isoformat() if task_obj.created_at else "",
                        "updated_at": task_obj.updated_at.isoformat() if task_obj.updated_at else "",
                    }
                return None
        return asyncio.run(db_update())

    # Fallback to file-based storage
    now = datetime.datetime.now().isoformat()
    tasks = _load_task_index()
    for item in tasks:
        if item.get("id") == task_id and (not user_id or item.get("user_id") == user_id):
            if title is not None:
                item["title"] = title
            if icon is not None:
                item["icon"] = icon
            item["updated_at"] = now
            _save_task_index(tasks)
            return item
    return None


def delete_task(task_id: str, user_id: Optional[str] = None) -> bool:
    """
    Delete a task for a user.

    If DATABASE_AVAILABLE and user_id is provided, delete from database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio
        async def db_delete():
            async with async_session_maker() as db:
                return await db_delete_task(db=db, user_id=UUID(user_id), task_id=task_id)
        return asyncio.run(db_delete())

    # Fallback to file-based storage
    tasks = _load_task_index()

    def _same_task_row(item: Dict[str, Any]) -> bool:
        if item.get("id") != task_id:
            return False
        if not user_id:
            return True
        return item.get("user_id") == user_id

    next_tasks = [item for item in tasks if not _same_task_row(item)]
    if len(next_tasks) == len(tasks):
        return False
    _save_task_index(next_tasks)
    return True


def _file_updated_at(path: str) -> str:
    if not os.path.exists(path):
        return ""
    ts = os.path.getmtime(path)
    return datetime.datetime.fromtimestamp(ts).isoformat()


def _date_from_session_meta(session: Dict[str, Any]) -> str:
    """
    从 session 元数据中提取日期。

    优先级：
    1. session_id 中的日期（创建日期）- 用于准确归类
    2. last_updated 中的日期（最后更新日期）- 兜底
    """
    # 优先从 session_id 提取日期（创建日期）
    session_id = session.get("session_id", "")
    parts = session_id.split("__")
    if len(parts) >= 2 and len(parts[1]) == 8 and parts[1].isdigit():
        raw = parts[1]
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"

    # 兜底：使用 last_updated
    last_updated = session.get("last_updated", "")
    if isinstance(last_updated, str) and len(last_updated) >= 10 and "-" in last_updated:
        return last_updated[:10]

    return datetime.datetime.now().strftime("%Y-%m-%d")


def _display_date(date_str: str) -> str:
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.month}月{dt.day}日"
    except Exception:
        return date_str


def _read_daily_note_sections(task_id: str, date: str, user_id: Optional[str] = None) -> Dict[str, List[str]]:
    path = _get_daily_note_path(task_id, date, user_id=user_id)
    if not os.path.exists(path):
        return {"key_learnings": [], "review_areas": []}

    try:
        content = file_io.load_text(path)
    except Exception:
        return {"key_learnings": [], "review_areas": []}

    key_learnings: List[str] = []
    review_areas: List[str] = []
    section = ""
    for line in content.splitlines():
        txt = line.strip()
        if txt.startswith("##"):
            if "今日要点" in txt:
                section = "key"
            elif "待复习" in txt:
                section = "review"
            else:
                section = ""
            continue

        if txt.startswith("-"):
            item = txt[1:].strip()
            if not item:
                continue
            if section == "key":
                key_learnings.append(item)
            elif section == "review":
                review_areas.append(item)

    return {
        "key_learnings": key_learnings,
        "review_areas": review_areas,
    }

def _get_session_path(session_id: str) -> str:
    """Get the absolute path for a session JSON file."""
    if not session_id:
        raise ValueError("Session ID cannot be empty")
    return os.path.join(MEMORY_DIR, f"{session_id}.json")

def _get_note_path(session_id: str, topic: Optional[str] = None) -> str:
    """
    Get the absolute path for a markdown note file.
    If topic is provided, include it in the filename for better readability.
    """
    # Sanitize topic to be filename friendly if present
    filename = f"{session_id}"
    if topic:
        # Simple sanitization: replace spaces with _, remove non-alphanumeric chars
        safe_topic = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in topic)
        filename += f"_{safe_topic}"
    
    return os.path.join(NOTES_DIR, f"{filename}.md")

async def save_session_async(state: AgentState, user_id: Optional[str] = None) -> str:
    """
    Persist the current agent state to disk and PostgreSQL when enabled.

    Must be awaited from async code (e.g. LangGraph nodes) so DB commits complete.
    """
    session_id = state.get("session_id")
    if not session_id:
        return ""

    serialized_messages = messages_to_dict(state["messages"])

    session_data = {
        "session_id": session_id,
        "task_id": state.get("task_id"),
        "last_updated": datetime.datetime.now().isoformat(),
        "topic": state.get("current_topic", "General"),
        "conversation_summary": state.get("conversation_summary"),
        "summarized_msg_count": state.get("summarized_msg_count", 0),
        "messages": serialized_messages,
        "user_id": user_id,
    }

    json_path = _get_session_path(session_id)
    file_io.save_json(session_data, json_path)

    if DATABASE_AVAILABLE and user_id:
        try:
            from uuid import UUID

            async with async_session_maker() as db:
                await db_save_session(
                    db=db,
                    user_id=UUID(user_id),
                    session_id=session_id,
                    task_id=state.get("task_id", "task_default"),
                    messages=serialized_messages,
                    topic=state.get("current_topic", "General"),
                    conversation_summary=state.get("conversation_summary"),
                    summarized_msg_count=state.get("summarized_msg_count", 0),
                )
        except Exception as e:
            print(f"⚠️ Database save failed: {e}")

    if state.get("should_exit") and state.get("summary_output"):
        note_content = state["summary_output"]

        header = f"""---
source_session: {session_id}
date: {datetime.datetime.now().strftime("%Y-%m-%d")}
topic: {state.get("current_topic", "General")}
---

"""
        full_note = header + note_content

        note_path = _get_note_path(session_id, state.get("current_topic"))
        file_io.save_text(full_note, note_path)

    return json_path


def save_session(state: AgentState, user_id: Optional[str] = None) -> str:
    """
    Sync persist API: writes file + DB when no asyncio loop is running (scripts / tests).

    From **async** code (FastAPI / LangGraph), use ``await save_session_async(...)`` instead.
    ``run_coroutine_threadsafe`` without awaiting previously caused PostgreSQL writes to be
    dropped or never committed before the request ended.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(save_session_async(state, user_id))
    raise RuntimeError(
        "save_session() cannot commit PostgreSQL from inside a running event loop; "
        "use: await memory.save_session_async(state, user_id=...)"
    )


# ==================== 防重复总结标记 ====================

def set_session_summarizing(session_id: str, is_summarizing: bool = True):
    """设置会话的总结中状态"""
    global _SUMMARIZING_SESSIONS
    if is_summarizing:
        _SUMMARIZING_SESSIONS.add(session_id)
    else:
        _SUMMARIZING_SESSIONS.discard(session_id)


def is_session_summarizing(session_id: str) -> bool:
    """检查会话是否正在生成总结中"""
    return session_id in _SUMMARIZING_SESSIONS


def load_session(session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load a session from disk and reconstruct the AgentState.

    If user_id is provided and database is available, try to load from database first.
    """
    # Try to load from database first if user_id is provided
    if DATABASE_AVAILABLE and user_id:
        try:
            import asyncio
            from uuid import UUID

            async def load_from_db():
                async with async_session_maker() as db:
                    return await db_load_session(db, UUID(user_id), session_id)

            db_result = asyncio.run(load_from_db())
            if db_result:
                raw_stored = getattr(db_result, "messages", None) or []
                if isinstance(raw_stored, dict) and "messages" in raw_stored:
                    raw_stored = raw_stored.get("messages") or []
                if not isinstance(raw_stored, list):
                    raw_stored = []
                messages = messages_from_dict(raw_stored)

                return {
                    "messages": messages,
                    "task_id": getattr(db_result, "task_id", None),
                    "session_id": getattr(db_result, "session_id", None) or session_id,
                    "current_topic": getattr(db_result, "topic", None),
                    "conversation_summary": getattr(db_result, "conversation_summary", None),
                    "summarized_msg_count": int(getattr(db_result, "summarized_msg_count", 0) or 0),
                    "user_id": user_id,
                }
            return None
        except Exception as e:
            print(f"⚠️ Database load failed: {e}")
            # Fall back to file-based loading

    # Fall back to file-based loading
    json_path = _get_session_path(session_id)

    try:
        data = file_io.load_json(json_path)
    except FileNotFoundError:
        return None

    # Reconstruct Messages (List[Dict] -> List[BaseMessage])
    messages = messages_from_dict(data.get("messages", []))

    # Reconstruct Partial State
    # Note: We don't restore everything (like 'plan' or 'tutor_output'),
    # just the persistent memory parts.
    return {
        "messages": messages,
        "task_id": data.get("task_id"),
        "session_id": data.get("session_id"),
        "current_topic": data.get("topic"),
        "conversation_summary": data.get("conversation_summary"),
        "summarized_msg_count": data.get("summarized_msg_count", 0),
        "user_id": user_id or data.get("user_id"),
        # created_at/updated_at can be handled by the caller or added here if needed
    }


def _infer_task_id(task_id: Optional[str], session_id: str) -> str:
    if task_id:
        return task_id
    if "__" in session_id:
        return session_id.split("__")[0]
    return "task_default"


def list_task_sessions(task_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    列出某个 task_id 下的所有会话元信息，按更新时间倒序。

    If DATABASE_AVAILABLE and user_id is provided, query from database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio
        async def db_list():
            async with async_session_maker() as db:
                return await db_list_sessions(db=db, user_id=UUID(user_id), task_id=task_id)
        try:
            db_sessions = asyncio.run(db_list())
            return [
                {
                    "session_id": s.session_id,
                    "task_id": s.task_id,
                    "topic": s.topic,
                    "last_updated": s.updated_at.isoformat() if s.updated_at else "",
                    "message_count": s.message_count,
                }
                for s in db_sessions
            ]
        except Exception as e:
            print(f"⚠️ DB session list failed ({e}), falling back to file storage")

    # Fallback to file-based storage
    if not os.path.exists(MEMORY_DIR):
        return []

    results: List[Dict[str, Any]] = []
    for filename in os.listdir(MEMORY_DIR):
        if not filename.endswith(".json"):
            continue
        session_id = filename[:-5]
        path = os.path.join(MEMORY_DIR, filename)
        try:
            data = file_io.load_json(path)
        except Exception:
            continue

        file_task_id = _infer_task_id(data.get("task_id"), data.get("session_id", session_id))
        if file_task_id != task_id:
            continue

        # Filter by user_id if provided (file-based).旧数据未写 user_id 时不应整段丢弃。
        if user_id:
            fu = data.get("user_id")
            if fu not in (None, "") and fu != user_id:
                continue

        msgs = data.get("messages", [])
        results.append({
            "session_id": data.get("session_id", session_id),
            "task_id": file_task_id,
            "topic": data.get("topic", "General"),
            "last_updated": data.get("last_updated", ""),
            "message_count": len(msgs),
        })

    results.sort(key=lambda item: item.get("last_updated", ""), reverse=True)
    return results


def get_session_messages(session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    返回某个 session 的消息列表（前端友好格式）。

    If DATABASE_AVAILABLE and user_id is provided, query from database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio

        async def load_from_db():
            async with async_session_maker() as db:
                return await db_load_session(db, UUID(user_id), session_id)

        db_result = None
        db_available = True
        try:
            db_result = asyncio.run(load_from_db())
        except Exception as e:
            print(f"⚠️ DB session load failed ({e}), falling back to file storage")
            db_available = False

        if db_available and db_result:
            # Reconstruct Messages from database（db_result 为 ORM Session）
            raw_stored = getattr(db_result, "messages", None) or []
            if isinstance(raw_stored, dict) and "messages" in raw_stored:
                raw_stored = raw_stored.get("messages") or []
            if not isinstance(raw_stored, list):
                raw_stored = []
            messages = messages_from_dict(raw_stored)
            normalized: List[Dict[str, str]] = []
            for index, msg in enumerate(messages):
                if isinstance(msg, HumanMessage):
                    role = "user"
                elif isinstance(msg, AIMessage):
                    role = "assistant"
                else:
                    continue
                content = getattr(msg, "content", "") or ""
                ts = getattr(msg, "additional_kwargs", {}).get("timestamp", "") or ""
                normalized.append({
                    "message_id": f"{session_id}-{index}",
                    "role": role,
                    "content": content,
                    "timestamp": ts,
                })
            updated_at = getattr(db_result, "updated_at", None)
            return {
                "session_id": getattr(db_result, "session_id", session_id) or session_id,
                "task_id": getattr(db_result, "task_id", None) or _infer_task_id(None, session_id),
                "topic": getattr(db_result, "topic", None) or "General",
                "last_updated": updated_at.isoformat() if updated_at else "",
                "messages": normalized,
            }
        # 已走 DB 且带 user_id：无记录则视为无权或不存在，禁止回落到文件以免串会话
        # 但若 DB 不可用（表不存在等），允许回落至文件
        if db_available:
            return None

    # Fallback to file-based loading
    path = _get_session_path(session_id)
    try:
        data = file_io.load_json(path)
    except FileNotFoundError:
        return None

    # Filter by user_id if provided (file-based)。旧 JSON 无 user_id 时仍允许当前登录用户读取。
    if user_id:
        fu = data.get("user_id")
        if fu not in (None, "") and fu != user_id:
            return None

    raw_messages = messages_from_dict(data.get("messages", []))
    normalized: List[Dict[str, str]] = []

    for index, msg in enumerate(raw_messages):
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        else:
            continue

        content = getattr(msg, "content", "") or ""
        ts = ""
        if isinstance(msg, BaseMessage):
            ts = (
                getattr(msg, "additional_kwargs", {}).get("timestamp")
                or data.get("last_updated", "")
                or ""
            )

        normalized.append({
            "message_id": f"{session_id}-{index}",
            "role": role,
            "content": content,
            "timestamp": ts,
        })

    resolved_session_id = data.get("session_id", session_id)
    resolved_task_id = _infer_task_id(data.get("task_id"), resolved_session_id)
    return {
        "session_id": resolved_session_id,
        "task_id": resolved_task_id,
        "topic": data.get("topic", "General"),
        "last_updated": data.get("last_updated", ""),
        "messages": normalized,
    }


def get_daily_note(task_id: str, date: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get daily note for a task.

    If DATABASE_AVAILABLE and user_id is provided, query from database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio
        async def db_get():
            async with async_session_maker() as db:
                return await list_notes(db=db, user_id=UUID(user_id), task_id=task_id, date=date)
        notes = asyncio.run(db_get())
        if notes:
            note = notes[0]
            return {
                "task_id": note.task_id,
                "date": note.date.isoformat() if note.date else date,
                "content": note.content,
                "updated_at": note.updated_at.isoformat() if note.updated_at else "",
            }

    # Fallback to file-based storage
    path = _get_daily_note_path(task_id, date, user_id=user_id)
    if not os.path.exists(path):
        return {
            "task_id": task_id,
            "date": date,
            "content": "",
            "updated_at": "",
        }
    return {
        "task_id": task_id,
        "date": date,
        "content": file_io.load_text(path),
        "updated_at": _file_updated_at(path),
    }


def save_daily_note(task_id: str, date: str, content: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Save daily note for a task.

    If DATABASE_AVAILABLE and user_id is provided, save to database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio
        async def db_save():
            async with async_session_maker() as db:
                from app.db.models import Note
                from sqlalchemy import select
                # Check if note exists
                result = await db.execute(
                    select(Note).where(
                        Note.user_id == UUID(user_id),
                        Note.task_id == task_id,
                        Note.date == date,
                    )
                )
                note = result.scalar_one_or_none()
                if note:
                    note.content = content
                else:
                    note = Note(
                        user_id=UUID(user_id),
                        task_id=task_id,
                        date=date,
                        content=content,
                    )
                    db.add(note)
                await db.commit()
                await db.refresh(note)
                return {
                    "task_id": note.task_id,
                    "date": note.date.isoformat() if note.date else date,
                    "content": note.content,
                    "updated_at": note.updated_at.isoformat() if note.updated_at else "",
                }
        return asyncio.run(db_save())

    # Fallback to file-based storage
    path = _get_daily_note_path(task_id, date, user_id=user_id)
    file_io.save_text(content, path)
    return {
        "task_id": task_id,
        "date": date,
        "content": content,
        "updated_at": _file_updated_at(path),
    }

def _load_task_plan(task_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Load task plan.

    If DATABASE_AVAILABLE and user_id is provided, query from database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio

        async def db_get():
            async with async_session_maker() as db:
                return await db_fetch_task_plan_json(db=db, user_id=UUID(user_id), task_id=task_id)

        try:
            result = asyncio.run(db_get())
            if result:
                return result
        except Exception:
            pass

    # Fallback to file-based storage
    path = _get_task_plan_path(task_id, user_id=user_id)
    if not os.path.exists(path):
        return {}
    try:
        data = file_io.load_json(path)
        if isinstance(data, dict):
            if "plan" not in data and "nextSteps" in data:
                data["plan"] = data.get("nextSteps")
            data.pop("nextSteps", None)
            return data
    except Exception:
        pass
    return {}


def _resolve_task_note_updated_at(plan_path: str, note_path: str) -> str:
    plan_ts = _file_updated_at(plan_path) if os.path.exists(plan_path) else ""
    note_ts = _file_updated_at(note_path) if os.path.exists(note_path) else ""
    return max(plan_ts, note_ts)

def get_task_plan_data(task_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    return _load_task_plan(task_id, user_id=user_id)

def has_task_plan(task_id: str, user_id: Optional[str] = None) -> bool:
    plan = _load_task_plan(task_id, user_id=user_id)
    if not plan:
        return False
    for key in (
        "taskTitle",
        "overallSummary",
        "coreKnowledge",
        "masteryLevel",
        "milestones",
        "plan",
    ):
        value = plan.get(key)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def get_task_note(task_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get task note for a task.

    If DATABASE_AVAILABLE and user_id is provided, query from database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio

        async def db_get_combined():
            async with async_session_maker() as db:
                uid = UUID(user_id)
                note = await db_get_task_note_orm(db, uid, task_id)
                plan = await db_fetch_task_plan_json(db, uid, task_id)
                content = (note.content if note else "") or ""
                updated = ""
                if note and getattr(note, "updated_at", None):
                    updated = note.updated_at.isoformat()
                elif note and getattr(note, "created_at", None):
                    updated = note.created_at.isoformat()
                out: Dict[str, Any] = dict(plan) if plan else {}
                out["task_id"] = task_id
                out["content"] = content
                out["userNotes"] = content
                out["updated_at"] = updated
                return out

        try:
            combined = asyncio.run(db_get_combined())
            if combined:
                return combined
        except Exception:
            pass

    # Fallback to file-based storage
    note_path = _get_task_note_path(task_id, user_id=user_id)
    plan_path = _get_task_plan_path(task_id, user_id=user_id)
    plan_data = _load_task_plan(task_id, user_id=user_id)
    plan_data.pop("nextSteps", None)

    # 优先从 task_note.txt 文件读取用户笔记内容
    # 这样用户的个人笔记不会被计划数据覆盖
    content = ""
    if os.path.exists(note_path):
        content = file_io.load_text(note_path)
    elif "userNotes" in plan_data:
        content = plan_data.get("userNotes") or ""

    response = {
        "task_id": task_id,
        "content": content,
        "userNotes": content,
        "updated_at": _resolve_task_note_updated_at(plan_path, note_path),
    }
    response.update(plan_data)
    response["task_id"] = task_id
    return response


def save_task_note(task_id: str, content: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Save task note for a task.

    If DATABASE_AVAILABLE and user_id is provided, save to database.
    Otherwise, fallback to file-based storage.
    """
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio
        from app.db.models import Note, NoteType
        from sqlalchemy import select

        async def db_save():
            async with async_session_maker() as db:
                result = await db.execute(
                    select(Note).where(
                        Note.user_id == UUID(user_id),
                        Note.task_id == task_id,
                        Note.note_type == NoteType.TASK.value,
                    )
                )
                note = result.scalar_one_or_none()
                if note:
                    note.content = content
                else:
                    note = Note(
                        user_id=UUID(user_id),
                        task_id=task_id,
                        note_type=NoteType.TASK.value,
                        content=content,
                    )
                    db.add(note)
                await db.commit()
                await db.refresh(note)

        asyncio.run(db_save())
        return get_task_note(task_id, user_id=user_id)

    # Fallback to file-based storage
    note_path = _get_task_note_path(task_id, user_id=user_id)
    plan_path = _get_task_plan_path(task_id, user_id=user_id)
    plan_data = _load_task_plan(task_id, user_id=user_id)

    plan_data["task_id"] = task_id
    plan_data["userNotes"] = content
    plan_data.pop("nextSteps", None)
    file_io.save_text(content, note_path)
    file_io.save_json(plan_data, plan_path)
    title = plan_data.get("taskTitle")
    icon = plan_data.get("taskIcon")
    if title or icon:
        update_task(task_id, title=title, icon=icon, user_id=user_id)
    return get_task_note(task_id, user_id=user_id)


def save_task_plan(task_id: str, plan: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    if DATABASE_AVAILABLE and user_id:
        from uuid import UUID
        import asyncio

        async def db_save():
            async with async_session_maker() as db:
                await db_merge_task_plan_json(db, UUID(user_id), task_id, plan)

        try:
            asyncio.run(db_save())
            return get_task_note(task_id, user_id=user_id)
        except Exception:
            pass

    note_path = _get_task_note_path(task_id, user_id=user_id)
    plan_path = _get_task_plan_path(task_id, user_id=user_id)
    plan_data = _load_task_plan(task_id, user_id=user_id)

    plan_data.update(plan)
    plan_data["task_id"] = task_id
    plan_data.pop("nextSteps", None)
    if "userNotes" in plan_data:
        file_io.save_text(plan_data.get("userNotes") or "", note_path)
    file_io.save_json(plan_data, plan_path)
    title = plan_data.get("taskTitle")
    icon = plan_data.get("taskIcon")
    if title or icon:
        update_task(task_id, title=title, icon=icon, user_id=user_id)
    return get_task_note(task_id, user_id=user_id)


def list_task_timeline(task_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    按 task_id 聚合出"按天"的时间线数据。

    If DATABASE_AVAILABLE and user_id is provided, query from database.
    Otherwise, fallback to file-based storage.
    """
    sessions = list_task_sessions(task_id, user_id=user_id)
    grouped: Dict[str, Dict[str, Any]] = {}

    for session in sessions:
        date_key = _date_from_session_meta(session)
        bucket = grouped.setdefault(
            date_key,
            {
                "date": date_key,
                "session_count": 0,
                "message_count": 0,
                "last_updated": "",
            },
        )
        bucket["session_count"] += 1
        bucket["message_count"] += int(session.get("message_count", 0))
        current_latest = bucket.get("last_updated", "")
        this_updated = session.get("last_updated", "")
        if this_updated > current_latest:
            bucket["last_updated"] = this_updated

    timeline: List[Dict[str, Any]] = []
    for index, date_key in enumerate(sorted(grouped.keys(), reverse=True), start=1):
        bucket = grouped[date_key]
        note_sections = _read_daily_note_sections(task_id, date_key, user_id=user_id)
        key_learnings = note_sections.get("key_learnings", [])
        review_areas = note_sections.get("review_areas", [])

        if not key_learnings:
            key_learnings = [
                f"当日共 {bucket['session_count']} 个会话",
                f"累计 {bucket['message_count']} 条消息",
            ]

        timeline.append(
            {
                "id": str(index),
                "date": date_key,
                "display_date": _display_date(date_key),
                "key_learnings": key_learnings,
                "review_areas": review_areas,
                "session_count": bucket["session_count"],
                "message_count": bucket["message_count"],
                "last_updated": bucket.get("last_updated", ""),
            }
        )

    return timeline
