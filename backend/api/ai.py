"""AI job trigger endpoints."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from backend.database import get_session
from backend.models.task import Task
from backend.workers.ai_worker import enqueue_task_analysis

router = APIRouter(prefix="/ai", tags=["ai"])


class AnalyzeTaskRequest(BaseModel):
    """Request to analyze a task."""

    task_id: UUID


class AnalyzeTaskResponse(BaseModel):
    """Response from task analysis request."""

    job_id: str
    task_id: str
    message: str


@router.post("/analyze", response_model=AnalyzeTaskResponse)
def analyze_task(
    request: AnalyzeTaskRequest,
    session: Annotated[Session, Depends(get_session)],
) -> AnalyzeTaskResponse:
    """Trigger AI analysis for a task.

    This enqueues a background job to:
    1. Classify and prioritize the task with Claude Haiku
    2. Split the task into subtasks with Claude Sonnet (if complex)

    Args:
        request: Task ID to analyze
        session: Database session

    Returns:
        Job information
    """
    # Verify task exists
    task = session.get(Task, request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Enqueue AI analysis job
    job_id = enqueue_task_analysis(str(task.id))

    return AnalyzeTaskResponse(
        job_id=job_id,
        task_id=str(task.id),
        message=f"AI analysis queued for task {task.task_code}",
    )


@router.post("/analyze-batch")
def analyze_batch(
    task_ids: list[UUID],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Trigger AI analysis for multiple tasks.

    Args:
        task_ids: List of task IDs to analyze
        session: Database session

    Returns:
        Batch job information
    """
    job_ids = []

    for task_id in task_ids:
        task = session.get(Task, task_id)
        if not task:
            continue

        job_id = enqueue_task_analysis(str(task.id))
        job_ids.append({"task_id": str(task.id), "job_id": job_id})

    return {
        "queued": len(job_ids),
        "jobs": job_ids,
    }
