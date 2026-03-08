from typing import List, Optional
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import memory
from app.core import task_plan_agent

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
        task_plan_agent.generate_task_plan_from_state,
        plan_state,
        plan_query,
        existing_plan,
    )
    return memory.save_task_plan(task_id=request.task_id, plan=plan)


@router.post("/task-plan/confirm")
async def confirm_task_plan(request: TaskPlanConfirmRequest):
    plan = dict(request.plan or {})
    plan["task_id"] = request.task_id
    plan.pop(task_plan_agent.PLAN_SESSION_KEY, None)
    if not plan.get("_plan_sig"):
        plan["_plan_sig"] = task_plan_agent.plan_signature(plan)
    return memory.save_task_plan(task_id=request.task_id, plan=plan)
