"""Task CRUD API."""
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models.task import Task, TaskStatus
from backend.models.task_event import TaskEvent, TaskEventType

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _sync_markdown() -> None:
    """Sync database state back to markdown vault."""
    from backend.sync.sync_service import sync_service
    await sync_service.sync_to_vault()


class TaskCreate(BaseModel):
    """Task creation schema."""

    task_code: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.RADAR
    tags: list[str] = []
    location_tags: list[str] = []
    environment_id: UUID | None = None
    parent_task_id: UUID | None = None


class TaskUpdate(BaseModel):
    """Task update schema."""

    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: int | None = None
    tags: list[str] | None = None
    location_tags: list[str] | None = None
    estimated_minutes: int | None = None


class TaskResponse(BaseModel):
    """Task response schema."""

    id: UUID
    task_code: str
    title: str
    description: str
    status: TaskStatus
    priority: int | None
    tags: list[str]
    location_tags: list[str]
    environment_id: UUID | None
    parent_task_id: UUID | None
    ai_generated: bool
    estimated_minutes: int | None
    order: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@router.get("/", response_model=list[TaskResponse])
def list_tasks(
    session: Annotated[Session, Depends(get_session)],
    status: TaskStatus | None = Query(None),
    environment_id: UUID | None = Query(None),
    parent_task_id: UUID | None = Query(None),
) -> list[Task]:
    """List tasks with optional filters."""
    query = select(Task)

    if status:
        query = query.where(Task.status == status)
    if environment_id:
        query = query.where(Task.environment_id == environment_id)
    if parent_task_id is not None:
        query = query.where(Task.parent_task_id == parent_task_id)

    tasks = session.exec(query).all()
    return list(tasks)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> Task:
    """Get a single task."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreate,
    session: Annotated[Session, Depends(get_session)],
) -> Task:
    """Create a new task."""
    # Check if task_code is unique
    existing = session.exec(
        select(Task).where(Task.task_code == data.task_code)
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, detail=f"Task with code {data.task_code} already exists"
        )

    task = Task(
        task_code=data.task_code,
        title=data.title,
        description=data.description,
        status=data.status,
        tags=data.tags,
        location_tags=data.location_tags,
        environment_id=data.environment_id,
        parent_task_id=data.parent_task_id,
    )

    session.add(task)

    # Log event
    event = TaskEvent(
        task_id=task.id,
        event_type=TaskEventType.TASK_CREATED,
        event_metadata={"status": data.status.value},
    )
    session.add(event)

    session.commit()
    session.refresh(task)
    await _sync_markdown()
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    data: TaskUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> Task:
    """Update a task."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_status = task.status

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    task.updated_at = datetime.now(timezone.utc)

    # If status changed, log event
    if data.status and data.status != old_status:
        if data.status == TaskStatus.DONE:
            task.completed_at = datetime.now(timezone.utc)
            event_type = TaskEventType.TASK_DONE
        elif data.status == TaskStatus.BLOCKED:
            event_type = TaskEventType.TASK_BLOCKED
        else:
            event_type = TaskEventType.TASK_MOVED

        event = TaskEvent(
            task_id=task.id,
            event_type=event_type,
            event_metadata={"from_status": old_status.value, "to_status": data.status.value},
        )
        session.add(event)

    session.add(task)
    session.commit()
    session.refresh(task)
    await _sync_markdown()
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Delete a task."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    session.delete(task)
    session.commit()
    await _sync_markdown()


@router.post("/{task_id}/move", response_model=TaskResponse)
async def move_task(
    task_id: UUID,
    status: TaskStatus,
    session: Annotated[Session, Depends(get_session)],
) -> Task:
    """Move a task to a different status."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_status = task.status
    task.status = status
    task.updated_at = datetime.now(timezone.utc)

    if status == TaskStatus.DONE:
        task.completed_at = datetime.now(timezone.utc)
        event_type = TaskEventType.TASK_DONE
    elif status == TaskStatus.BLOCKED:
        event_type = TaskEventType.TASK_BLOCKED
    else:
        event_type = TaskEventType.TASK_MOVED

    event = TaskEvent(
        task_id=task.id,
        event_type=event_type,
        event_metadata={"from_status": old_status.value, "to_status": status.value},
    )

    session.add(task)
    session.add(event)
    session.commit()
    session.refresh(task)
    await _sync_markdown()
    return task
