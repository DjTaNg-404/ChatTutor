import os
import datetime
from typing import Dict, Any, List, Optional
from langchain_core.messages import messages_to_dict, messages_from_dict, BaseMessage

from chattutor.core.models import AgentState
from chattutor.utils import file_io

# Paths Configuration
MEMORY_DIR = "memory/sessions"
NOTES_DIR = "memory/notes"

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
        "last_updated": datetime.datetime.now().isoformat(),
        "topic": state.get("current_topic", "General"),
        "conversation_summary": state.get("conversation_summary"), # The Compressed Context (B)
        "messages": serialized_messages, # The Full Log (A)
        # include user_id so sessions can be filtered per user
        "user_id": state.get("user_id"),
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
        "session_id": data.get("session_id"),
        "current_topic": data.get("topic"),
        "conversation_summary": data.get("conversation_summary"),
        # created_at/updated_at can be handled by the caller or added here if needed
    }


# ---------------------------------------------------------------------------
# Utility functions for session management
# ---------------------------------------------------------------------------

def _ensure_memory_dir():
    """Make sure the base memory directory exists so that listing/deleting
    won't blow up when the folder is empty.
    """
    if not os.path.exists(MEMORY_DIR):
        os.makedirs(MEMORY_DIR, exist_ok=True)


def list_sessions(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return a list of saved sessions.

    Each entry is the raw JSON data that was written by :func:`save_session`.
    Sessions are sorted by ``last_updated`` (newest first).

    Args:
        user_id: if provided, filter the results to only sessions that match the
            given ``user_id`` field saved in the session metadata.  Ignore the
            argument if sessions were created by an older version that didn't
            record this field.
    """
    _ensure_memory_dir()
    sessions: List[Dict[str, Any]] = []
    for fname in os.listdir(MEMORY_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(MEMORY_DIR, fname)
        try:
            data = file_io.load_json(path)
        except Exception:
            # skip corrupt files
            continue
        if user_id and data.get("user_id"):
            if data.get("user_id") != user_id:
                continue
        sessions.append(data)

    # sort by last_updated descending; fallback to filename if missing
    sessions.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
    return sessions


def delete_session(session_id: str) -> bool:
    """Remove a previously saved session from disk.

    Returns True if the file was removed, False if it did not exist.
    """
    path = _get_session_path(session_id)
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False
