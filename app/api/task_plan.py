from typing import List, Optional
import asyncio

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal

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


class PlanSessionActionRequest(BaseModel):
    task_id: str
    action: Literal["resume", "exit"]


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
    plan.pop("draft_plan", None)
    if not plan.get("_plan_sig"):
        plan["_plan_sig"] = plan_signature(plan)

    # 保存计划（只更新结构化数据，不生成笔记内容）
    # 用户的个人笔记由"更新任务笔记"按钮或结束对话时生成
    result = memory.save_task_plan(task_id=request.task_id, plan=plan)
    try:
        memory.save_task_plan(
            task_id=request.task_id,
            plan={"draft_plan": None, PLAN_SESSION_KEY: {"status": "idle"}},
        )
    except Exception:
        pass

    return result


def build_plan_note_content(plan: dict) -> str:
    """根据学习计划构建任务笔记内容"""
    lines = []

    task_title = plan.get("taskTitle", "")
    if task_title:
        lines.append(f"# {task_title}")
        lines.append("")

    overall_summary = plan.get("overallSummary", "")
    if overall_summary:
        lines.append(f"## 概述")
        lines.append(overall_summary)
        lines.append("")

    total_days = plan.get("totalDays", 0)
    total_hours = plan.get("totalHours", 0)
    if total_days or total_hours:
        lines.append(f"## 学习安排")
        if total_days:
            lines.append(f"- 总天数：{total_days} 天")
        if total_hours:
            lines.append(f"- 每日学习：{total_hours} 小时")
        lines.append("")

    # 详细计划步骤
    plan_steps = plan.get("plan", [])
    if isinstance(plan_steps, str):
        plan_steps = [s.strip() for s in plan_steps.split("\n") if s.strip()]

    if plan_steps and len(plan_steps) > 0:
        lines.append(f"## 详细计划")
        for idx, step in enumerate(plan_steps, 1):
            lines.append(f"{idx}. {step}")
        lines.append("")

    # 核心知识点
    core_knowledge = plan.get("coreKnowledge", [])
    if core_knowledge and len(core_knowledge) > 0:
        lines.append(f"## 核心知识点")
        for k in core_knowledge:
            lines.append(f"- {k}")
        lines.append("")

    # 里程碑
    milestones = plan.get("milestones", [])
    if milestones and len(milestones) > 0:
        lines.append(f"## 里程碑")
        for m in milestones:
            date = m.get("date", "")
            achievement = m.get("achievement", "")
            lines.append(f"- {date}: {achievement}")
        lines.append("")

    return "\n".join(lines) if lines else ""


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


@router.post("/task-plan/session")
async def update_plan_session(request: PlanSessionActionRequest):
    try:
        plan_data = memory.get_task_plan_data(request.task_id)
    except Exception:
        plan_data = None

    session = plan_data.get(PLAN_SESSION_KEY) if isinstance(plan_data, dict) else None
    if not isinstance(session, dict):
        session = {"status": "idle"}

    status = session.get("status") or "idle"
    if request.action == "exit":
        session = {
            "status": "idle",
            "mode": "",
            "turns": 0,
            "pending_mode": "",
            "messages": [],
        }
        session.pop("exit_from", None)
    elif request.action == "resume":
        if status == "paused":
            session["status"] = session.get("paused_from") or "collecting"
            session.pop("paused_from", None)
        # 清理退出确认状态
        session.pop("exit_from", None)

    updated_plan = dict(plan_data or {})
    updated_plan[PLAN_SESSION_KEY] = session
    try:
        memory.save_task_plan(task_id=request.task_id, plan=updated_plan)
    except Exception:
        pass

    return {"status": session.get("status") or "idle"}
