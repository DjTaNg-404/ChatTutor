from typing import List, Optional
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import memory
from app.core.task_plan import (
    PLAN_SESSION_KEY,
    plan_signature,
    generate_task_plan_from_state,
)

router = APIRouter()


class TaskPlanRequest(BaseModel):
    task_id: str
    user_goal: Optional[str] = ""
    current_level: Optional[str] = ""
    constraints: Optional[str] = ""
    target_days: Optional[int] = None
    daily_hours: Optional[float] = None
    focus_topics: Optional[List[str]] = None


class TaskPlanConfirmRequest(BaseModel):
    task_id: str
    plan: dict


class TaskPlanFromChatRequest(BaseModel):
    """从对话历史生成学习计划的请求"""
    task_id: str
    session_id: Optional[str] = None


@router.post("/task-plan")
async def generate_task_plan(request: TaskPlanRequest):
    parts = []
    if request.user_goal:
        parts.append(f"User goal: {request.user_goal}")
    if request.current_level:
        parts.append(f"Current level: {request.current_level}")
    if request.constraints:
        parts.append(f"Constraints: {request.constraints}")
    if request.target_days:
        parts.append(f"Target days: {request.target_days}")
    if request.daily_hours:
        parts.append(f"Daily hours: {request.daily_hours}")
    if request.focus_topics:
        parts.append(f"Focus topics: {', '.join(request.focus_topics)}")
    plan_query = "\n".join(parts) if parts else ""

    try:
        existing_plan = memory.get_task_plan_data(request.task_id)
    except Exception:
        existing_plan = None

    plan_state = {
        "messages": [],
        "conversation_summary": "",
        "task_id": request.task_id,
        "session_id": "",
    }
    plan = await asyncio.to_thread(
        generate_task_plan_from_state,
        plan_state,
        plan_query,
        existing_plan,
    )
    return memory.save_task_plan(task_id=request.task_id, plan=plan)


@router.post("/task-plan/confirm")
async def confirm_task_plan(request: TaskPlanConfirmRequest):
    plan = dict(request.plan or {})
    plan["task_id"] = request.task_id
    plan.pop(PLAN_SESSION_KEY, None)
    if not plan.get("_plan_sig"):
        plan["_plan_sig"] = plan_signature(plan)
    return memory.save_task_plan(task_id=request.task_id, plan=plan)


@router.post("/task-plan/from-chat")
async def generate_task_plan_from_chat(request: TaskPlanFromChatRequest):
    """
    从对话历史生成学习计划（Web 按钮触发）

    此端点用于 Web 界面上的"制定学习计划"按钮，
    它会读取当前会话的对话历史，并基于对话内容生成学习计划。
    """
    task_id = request.task_id
    session_id = request.session_id

    # 从会话中加载对话历史
    if session_id:
        session_data = memory.load_session(session_id)
        messages = session_data.get("messages", []) if session_data else []
        conversation_summary = session_data.get("conversation_summary", "") if session_data else ""
    else:
        messages = []
        conversation_summary = ""

    # 获取现有计划（如果有）
    try:
        existing_plan = memory.get_task_plan_data(task_id)
    except Exception:
        existing_plan = None

    # 构造计划生成状态
    plan_state = {
        "messages": messages,
        "conversation_summary": conversation_summary or "",
        "task_id": task_id,
        "session_id": session_id or "",
    }

    # 生成计划
    plan = await asyncio.to_thread(
        generate_task_plan_from_state,
        plan_state,
        "",  # 不传入额外 query，让 agent 从对话中提取
        existing_plan,
    )

    # 保存并返回
    return memory.save_task_plan(task_id=task_id, plan=plan)
