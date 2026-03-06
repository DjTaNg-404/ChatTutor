from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional

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
    nextSteps: Optional[List[str]] = None
    updated_at: str


class TaskNoteUpsertRequest(BaseModel):
    task_id: str
    content: str


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
