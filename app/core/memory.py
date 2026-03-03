import os
import datetime
from typing import Dict, Any, List, Optional
from langchain_core.messages import messages_to_dict, messages_from_dict, BaseMessage
from langchain_core.messages import HumanMessage, AIMessage

from app.core.models import AgentState
from app.utils import file_io

# Paths Configuration
MEMORY_DIR = "memory/sessions"
NOTES_DIR = "memory/notes"


def _get_daily_note_path(task_id: str, date: str) -> str:
    return os.path.join(NOTES_DIR, "daily", task_id, f"{date}.md")


def _get_task_note_path(task_id: str) -> str:
    return os.path.join(NOTES_DIR, "task", f"{task_id}.md")


def _file_updated_at(path: str) -> str:
    if not os.path.exists(path):
        return ""
    ts = os.path.getmtime(path)
    return datetime.datetime.fromtimestamp(ts).isoformat()


def _date_from_session_meta(session: Dict[str, Any]) -> str:
    last_updated = session.get("last_updated", "")
    if isinstance(last_updated, str) and len(last_updated) >= 10 and "-" in last_updated:
        return last_updated[:10]

    session_id = session.get("session_id", "")
    parts = session_id.split("__")
    if len(parts) >= 2 and len(parts[1]) == 8 and parts[1].isdigit():
        raw = parts[1]
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"

    return datetime.datetime.now().strftime("%Y-%m-%d")


def _display_date(date_str: str) -> str:
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.month}月{dt.day}日"
    except Exception:
        return date_str


def _read_daily_note_sections(task_id: str, date: str) -> Dict[str, List[str]]:
    path = _get_daily_note_path(task_id, date)
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

def save_session(state: AgentState) -> str:
    """
    Persist the current agent state to disk (Full Snapshot).
    
    1. Saves the raw session data (messages, metadata) to JSON.
    2. If a conclusion note exists (summary_output), saves it to Markdown.
    
    Returns:
        The path to the saved JSON session file.
    """
    session_id = state.get("session_id")
    if not session_id:
        # If no session ID, we can't save. Ideally should generate one or error.
        # For now, let's assume session_id is always present in State as per logical flow.
        return ""

    # 1. Serialize Messages (LangChain -> List[Dict])
    # This handles HumanMessage, AIMessage, ToolMessage, etc. automatically.
    serialized_messages = messages_to_dict(state["messages"])
    
    # 2. Construct Session Storage Object
    session_data = {
        "session_id": session_id,
        "task_id": state.get("task_id"),
        "last_updated": datetime.datetime.now().isoformat(),
        "topic": state.get("current_topic", "General"),
        "conversation_summary": state.get("conversation_summary"), # The Compressed Context (B)
        "summarized_msg_count": state.get("summarized_msg_count", 0),
        "messages": serialized_messages # The Full Log (A)
    }
    
    # 3. Save Session JSON (Overwrite Mode)
    json_path = _get_session_path(session_id)
    file_io.save_json(session_data, json_path)
    
    # 4. Save Markdown Note (if applicable)
    # Only save note if we are in a concluding state and actually have a note generated
    if state.get("should_exit") and state.get("summary_output"):
        note_content = state["summary_output"]
        
        # Add metadata header to the note
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

def load_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a session from disk and reconstruct the AgentState.
    """
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
        # created_at/updated_at can be handled by the caller or added here if needed
    }


def _infer_task_id(task_id: Optional[str], session_id: str) -> str:
    if task_id:
        return task_id
    if "__" in session_id:
        return session_id.split("__")[0]
    return "task_default"


def list_task_sessions(task_id: str) -> List[Dict[str, Any]]:
    """
    列出某个 task_id 下的所有会话元信息，按更新时间倒序。
    """
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


def get_session_messages(session_id: str) -> Optional[Dict[str, Any]]:
    """
    返回某个 session 的消息列表（前端友好格式）。
    """
    path = _get_session_path(session_id)
    try:
        data = file_io.load_json(path)
    except FileNotFoundError:
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


def get_daily_note(task_id: str, date: str) -> Dict[str, Any]:
    path = _get_daily_note_path(task_id, date)
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


def save_daily_note(task_id: str, date: str, content: str) -> Dict[str, Any]:
    path = _get_daily_note_path(task_id, date)
    file_io.save_text(content, path)
    return {
        "task_id": task_id,
        "date": date,
        "content": content,
        "updated_at": _file_updated_at(path),
    }


def get_task_note(task_id: str) -> Dict[str, Any]:
    path = _get_task_note_path(task_id)
    if not os.path.exists(path):
        return {
            "task_id": task_id,
            "content": "",
            "updated_at": "",
        }
    return {
        "task_id": task_id,
        "content": file_io.load_text(path),
        "updated_at": _file_updated_at(path),
    }


def save_task_note(task_id: str, content: str) -> Dict[str, Any]:
    path = _get_task_note_path(task_id)
    file_io.save_text(content, path)
    return {
        "task_id": task_id,
        "content": content,
        "updated_at": _file_updated_at(path),
    }


def list_task_timeline(task_id: str) -> List[Dict[str, Any]]:
    """
    按 task_id 聚合出“按天”的时间线数据。
    """
    sessions = list_task_sessions(task_id)
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
        note_sections = _read_daily_note_sections(task_id, date_key)
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
