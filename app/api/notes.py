from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from uuid import UUID

from app.core import memory
from app.core.deps import get_current_user
from app.db.models import User

router = APIRouter()


class DailyNoteResponse(BaseModel):
    task_id: str
    date: str
    content: str
    updated_at: str


class DailyNoteUpsertRequest(BaseModel):
    task_id: str
    date: str
    content: str


class TaskNoteResponse(BaseModel):
    task_id: str
    content: str
    userNotes: Optional[str] = None
    taskTitle: Optional[str] = None
    taskIcon: Optional[str] = None
    startDate: Optional[str] = None
    totalDays: Optional[int] = None
    totalHours: Optional[float] = None
    progress: Optional[int] = None
    overallSummary: Optional[str] = None
    coreKnowledge: Optional[List[str]] = None
    masteryLevel: Optional[List[dict]] = None
    milestones: Optional[List[dict]] = None
    plan: Optional[List[str]] = None
    planChecklist: Optional[Dict[str, bool]] = None
    draft_plan: Optional[dict] = None
    updated_at: str


class TaskNoteUpsertRequest(BaseModel):
    task_id: str
    content: str


class PlanChecklistRequest(BaseModel):
    task_id: str
    checklist: Dict[str, bool]


class PlanChecklistResponse(BaseModel):
    task_id: str
    checklist: Dict[str, bool]


@router.get("/daily", response_model=DailyNoteResponse)
async def get_daily_note(
    task_id: str = Query(...),
    date: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    return DailyNoteResponse(**memory.get_daily_note(task_id=task_id, date=date, user_id=str(current_user.id)))


@router.put("/daily", response_model=DailyNoteResponse)
async def put_daily_note(
    request: DailyNoteUpsertRequest,
    current_user: User = Depends(get_current_user)
):
    return DailyNoteResponse(
        **memory.save_daily_note(task_id=request.task_id, date=request.date, content=request.content, user_id=str(current_user.id))
    )


@router.get("/task", response_model=TaskNoteResponse)
async def get_task_note(
    task_id: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    return TaskNoteResponse(**memory.get_task_note(task_id=task_id, user_id=str(current_user.id)))


@router.put("/task", response_model=TaskNoteResponse)
async def put_task_note(
    request: TaskNoteUpsertRequest,
    current_user: User = Depends(get_current_user)
):
    return TaskNoteResponse(**memory.save_task_note(task_id=request.task_id, content=request.content, user_id=str(current_user.id)))


@router.put("/task/plan-checklist", response_model=PlanChecklistResponse)
async def put_plan_checklist(
    request: PlanChecklistRequest,
    current_user: User = Depends(get_current_user)
):
    """保存学习计划的打勾状态"""
    user_id = str(current_user.id)
    memory.save_task_plan(
        request.task_id,
        {"planChecklist": request.checklist, "task_id": request.task_id},
        user_id=user_id,
    )

    return PlanChecklistResponse(task_id=request.task_id, checklist=request.checklist)
