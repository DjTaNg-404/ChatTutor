from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import memory

router = APIRouter()


class TaskItem(BaseModel):
    id: str
    title: str
    icon: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: List[TaskItem]


class TaskUpsertRequest(BaseModel):
    task_id: str
    title: str
    icon: str = "✨"
    status: Optional[str] = "active"


class TaskStatusRequest(BaseModel):
    status: str


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    icon: Optional[str] = None


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(status: Optional[str] = None):
    tasks = memory.list_tasks(status=status)
    return TaskListResponse(tasks=tasks)


@router.post("/tasks", response_model=TaskItem)
async def upsert_task(request: TaskUpsertRequest):
    if not request.task_id:
        raise HTTPException(status_code=400, detail="task_id is required")
    if not request.title:
        raise HTTPException(status_code=400, detail="title is required")
    status = request.status or "active"
    task = memory.upsert_task(
        task_id=request.task_id,
        title=request.title,
        icon=request.icon or "✨",
        status=status,
    )
    return TaskItem(**task)


@router.patch("/tasks/{task_id}", response_model=TaskItem)
async def update_task(task_id: str, request: TaskUpdateRequest):
    """更新任务的名称和/或图标"""
    if not request.title and not request.icon:
        raise HTTPException(status_code=400, detail="At least one of title or icon must be provided")

    task = memory.update_task(task_id, title=request.title, icon=request.icon)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskItem(**task)


@router.patch("/tasks/{task_id}/status", response_model=TaskItem)
async def update_task_status(task_id: str, request: TaskStatusRequest):
    """更新任务的状态（归档/恢复）"""
    task = memory.update_task_status(task_id, request.status)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskItem(**task)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    deleted = memory.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True}
