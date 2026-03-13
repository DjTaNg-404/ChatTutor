from typing import List, Optional, Dict, Any
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core import memory
from app.core.summary.generator import summary_generator

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


class DailySummaryResponse(BaseModel):
    """每日总结响应模型"""
    task_id: str
    date: str
    summary: str
    ai_summary: Dict[str, List[str]]
    created_at: str


class GenerateDailySummaryRequest(BaseModel):
    """生成每日总结请求模型"""
    task_id: str
    date: str


class GenerateTaskSummaryRequest(BaseModel):
    """生成任务总结请求模型"""
    task_id: str


class TaskSummaryResponse(BaseModel):
    """任务总结响应模型"""
    task_id: str
    summary: str
    created_at: str


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


@router.post("/tasks/{task_id}/daily-summary")
async def generate_daily_summary(task_id: str, request: GenerateDailySummaryRequest):
    """
    根据指定日期的所有会话生成每日学习总结

    此端点会：
    1. 加载指定日期的所有会话
    2. 调用 SummaryGenerator 生成总结
    3. 保存总结到每日笔记
    4. 返回生成的总结内容
    """
    date = request.date

    # 获取该日期的所有会话
    sessions_data = memory.list_task_sessions(task_id)

    # 过滤出指定日期的会话
    day_sessions = []
    for session in sessions_data:
        session_id = session.get("session_id", "")
        last_updated = session.get("last_updated", "")

        # 从 session_id 或 last_updated 判断日期
        session_date = ""
        parts = session_id.split("__")
        if len(parts) >= 2 and len(parts[1]) == 8 and parts[1].isdigit():
            raw = parts[1]
            session_date = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
        elif last_updated and last_updated.startswith(date):
            session_date = last_updated[:10]

        if session_date == date:
            # 加载完整的会话消息
            messages_data = memory.get_session_messages(session_id)
            if messages_data:
                # 转换为 SummaryGenerator 需要的格式
                simple_messages = []
                for msg in messages_data.get("messages", []):
                    simple_messages.append({
                        "role": msg.get("role"),
                        "content": msg.get("content")
                    })
                day_sessions.append({
                    "session_id": session_id,
                    "messages": simple_messages
                })

    if not day_sessions:
        raise HTTPException(
            status_code=404,
            detail=f"日期 {date} 没有找到会话记录"
        )

    # 调用总结生成器
    summary = await asyncio.to_thread(
        summary_generator.generate_daily_summary,
        day_sessions,
        task_id,
        date
    )

    # 解析总结内容为结构化格式
    ai_summary = parse_daily_summary(summary)

    # 保存到每日笔记
    memory.save_daily_note(task_id=task_id, date=date, content=summary)

    return DailySummaryResponse(
        task_id=task_id,
        date=date,
        summary=summary,
        ai_summary=ai_summary,
        created_at=memory._file_updated_at(memory._get_daily_note_path(task_id, date))
    )


def parse_daily_summary(summary: str) -> Dict[str, List[str]]:
    """解析每日总结文本为结构化格式"""
    result = {
        "key_learnings": [],
        "review_areas": [],
        "achievements": []
    }

    current_section = None
    for line in summary.split("\n"):
        line = line.strip()
        if not line:
            continue

        if "核心知识点" in line or "## 📚" in line:
            current_section = "key_learnings"
        elif "待复习" in line or "## 🔍" in line:
            current_section = "review_areas"
        elif "关键洞察" in line or "💡" in line:
            current_section = "achievements"
        elif line.startswith("- ") and current_section:
            item = line[2:].strip()
            # 移除可能的 markdown 格式
            item = item.replace("**", "")
            if item and not item.startswith("["):
                result[current_section].append(item)

    return result

@router.post("/tasks/{task_id}/summary")
async def generate_task_summary(task_id: str, request: GenerateTaskSummaryRequest):
    """
    根据任务的所有会话生成任务学习总结

    此端点会：
    1. 加载任务的所有会话
    2. 调用 SummaryGenerator 生成总结
    3. 覆盖保存到任务笔记（我的笔记）
    4. 返回生成的总结内容
    """
    # 获取该任务的所有会话
    sessions_data = memory.list_task_sessions(task_id)

    if not sessions_data:
        raise HTTPException(
            status_code=404,
            detail=f"任务 '{task_id}' 没有找到会话记录"
        )

    # 加载所有会话的完整消息
    all_sessions = []
    for session in sessions_data:
        session_id = session.get("session_id", "")
        messages_data = memory.get_session_messages(session_id)
        if messages_data:
            # 转换为 SummaryGenerator 需要的格式
            simple_messages = []
            for msg in messages_data.get("messages", []):
                simple_messages.append({
                    "role": msg.get("role"),
                    "content": msg.get("content")
                })
            all_sessions.append({
                "session_id": session_id,
                "messages": simple_messages
            })

    if not all_sessions:
        raise HTTPException(
            status_code=404,
            detail=f"任务 '{task_id}' 没有找到会话内容"
        )

    # 调用总结生成器
    summary = await asyncio.to_thread(
        summary_generator.generate_task_summary,
        all_sessions,
        task_id
    )

    # 覆盖保存到任务笔记（不保留原有用户笔记内容）
    memory.save_task_note(task_id=task_id, content=summary)

    return TaskSummaryResponse(
        task_id=task_id,
        summary=summary,
        created_at=memory._file_updated_at(memory._get_task_note_path(task_id))
    )
