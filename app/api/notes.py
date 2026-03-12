from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional, Dict

from app.core import memory

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
async def get_daily_note(task_id: str = Query(...), date: str = Query(...)):
    return DailyNoteResponse(**memory.get_daily_note(task_id=task_id, date=date))


@router.put("/daily", response_model=DailyNoteResponse)
async def put_daily_note(request: DailyNoteUpsertRequest):
    return DailyNoteResponse(
        **memory.save_daily_note(task_id=request.task_id, date=request.date, content=request.content)
    )


@router.get("/task", response_model=TaskNoteResponse)
async def get_task_note(task_id: str = Query(...)):
    return TaskNoteResponse(**memory.get_task_note(task_id=task_id))


@router.put("/task", response_model=TaskNoteResponse)
async def put_task_note(request: TaskNoteUpsertRequest):
    return TaskNoteResponse(**memory.save_task_note(task_id=request.task_id, content=request.content))


@router.put("/task/plan-checklist", response_model=PlanChecklistResponse)
async def put_plan_checklist(request: PlanChecklistRequest):
    """保存学习计划的打勾状态"""
    plan_data = memory._load_task_plan(request.task_id)
    plan_data["planChecklist"] = request.checklist
    plan_data["task_id"] = request.task_id

    # 保存到文件
    from app.utils import file_io
    plan_path = memory._get_task_plan_path(request.task_id)
    file_io.save_json(plan_data, plan_path)

    return PlanChecklistResponse(task_id=request.task_id, checklist=request.checklist)
