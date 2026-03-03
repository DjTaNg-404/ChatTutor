from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import memory

router = APIRouter()


class SessionMeta(BaseModel):
    session_id: str
    task_id: str
    topic: str
    last_updated: str
    message_count: int


class TaskSessionsResponse(BaseModel):
    task_id: str
    sessions: List[SessionMeta]


class ChatMessageOut(BaseModel):
    message_id: str
    role: str
    content: str
    timestamp: str


class SessionMessagesResponse(BaseModel):
    session_id: str
    task_id: str
    topic: str
    last_updated: str
    messages: List[ChatMessageOut]


class TimelineItem(BaseModel):
    id: str
    date: str
    display_date: str
    key_learnings: List[str]
    review_areas: List[str]
    session_count: int
    message_count: int
    last_updated: str


class TaskTimelineResponse(BaseModel):
    task_id: str
    timeline: List[TimelineItem]


@router.get("/tasks/{task_id}/sessions", response_model=TaskSessionsResponse)
async def get_task_sessions(task_id: str):
    sessions = memory.list_task_sessions(task_id)
    return TaskSessionsResponse(task_id=task_id, sessions=sessions)


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(session_id: str):
    session_data = memory.get_session_messages(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' 不存在")
    return SessionMessagesResponse(**session_data)


@router.get("/tasks/{task_id}/timeline", response_model=TaskTimelineResponse)
async def get_task_timeline(task_id: str):
    timeline = memory.list_task_timeline(task_id)
    return TaskTimelineResponse(task_id=task_id, timeline=timeline)
