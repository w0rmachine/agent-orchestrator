"""MCP HTTP router implementation."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.mcp.tools import get_all_tool_schemas
from backend.models.environment import Environment
from backend.models.task import Task, TaskStatus
from backend.workers.ai_worker import enqueue_task_analysis

router = APIRouter(prefix="/mcp", tags=["mcp"])


class ToolListResponse(BaseModel):
    """Response from tools/list endpoint."""

    tools: list[dict[str, Any]]


class ToolCallRequest(BaseModel):
    """Request to call an MCP tool."""

    tool: str
    arguments: dict[str, Any]


class ToolCallResponse(BaseModel):
    """Response from tool call."""

    result: Any
    error: str | None = None


@router.post("/tools/list", response_model=ToolListResponse)
def list_tools() -> ToolListResponse:
    """List all available MCP tools with their JSON schemas."""
    return ToolListResponse(tools=get_all_tool_schemas())


@router.post("/tools/call", response_model=ToolCallResponse)
def call_tool(
    request: ToolCallRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ToolCallResponse:
    """Call an MCP tool.

    Args:
        request: Tool name and arguments
        session: Database session

    Returns:
        Tool execution result
    """
    try:
        result = execute_tool(request.tool, request.arguments, session)
        return ToolCallResponse(result=result)
    except Exception as e:
        return ToolCallResponse(result=None, error=str(e))


def execute_tool(
    tool_name: str,
    args: dict[str, Any],
    session: Session,
) -> Any:
    """Execute a specific MCP tool.

    Args:
        tool_name: Name of tool to execute
        args: Tool arguments
        session: Database session

    Returns:
        Tool execution result
    """
    if tool_name == "get_tasks_for_repo":
        return get_tasks_for_repo(args["repo_path"], session)

    elif tool_name == "get_recommended_next_task":
        return get_recommended_next_task(
            args["energy_level"],
            args["location"],
            args.get("repo_path"),
            session,
        )

    elif tool_name == "move_task":
        return move_task(args["task_code"], args["status"], session)

    elif tool_name == "mark_done":
        return mark_done(args["task_code"], session)

    elif tool_name == "add_context":
        return add_context(args["task_code"], args["note"], session)

    elif tool_name == "split_task":
        return split_task(args["task_code"], session)

    elif tool_name == "list_environments":
        return list_environments(session)

    elif tool_name == "get_ai_activity":
        return get_ai_activity(args.get("limit", 50))

    else:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")


# Tool implementations


def get_tasks_for_repo(repo_path: str, session: Session) -> dict:
    """Get all tasks for a repository."""
    # Find environment by repo_path
    env = session.exec(
        select(Environment).where(Environment.repo_path == repo_path)
    ).first()

    if not env:
        return {"tasks": [], "environment": None}

    tasks = session.exec(select(Task).where(Task.environment_id == env.id)).all()

    return {
        "environment": {
            "id": str(env.id),
            "name": env.name,
            "repo_path": env.repo_path,
        },
        "tasks": [
            {
                "task_code": t.task_code,
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "estimated_minutes": t.estimated_minutes,
            }
            for t in tasks
        ],
    }


def get_recommended_next_task(
    energy_level: str,
    location: str,
    repo_path: str | None,
    session: Session,
) -> dict:
    """Recommend next task based on context."""
    query = select(Task).where(
        Task.status.in_([TaskStatus.RUNWAY, TaskStatus.FLIGHT])  # type: ignore
    )

    # Filter by environment if repo_path provided
    if repo_path:
        env = session.exec(
            select(Environment).where(Environment.repo_path == repo_path)
        ).first()
        if env:
            query = query.where(Task.environment_id == env.id)

    tasks = session.exec(query).all()

    if not tasks:
        return {"recommended_task": None, "reason": "No tasks available"}

    # Score tasks based on context
    scored_tasks = []
    for task in tasks:
        score = 0

        # Energy-based scoring
        if energy_level == "low" and "lowenergy" in task.tags:
            score += 10
        elif energy_level == "high" and "deepwork" in task.tags:
            score += 10
        elif energy_level == "medium":
            score += 5

        # Location-based scoring
        if location in task.location_tags or "anywhere" in task.location_tags:
            score += 5

        # Priority-based scoring
        if task.priority:
            score += (6 - task.priority) * 2  # Higher priority = higher score

        # Fast task bonus for low energy
        if energy_level == "low" and "fasttask" in task.tags:
            score += 15

        scored_tasks.append((task, score))

    # Sort by score and get top recommendation
    scored_tasks.sort(key=lambda x: x[1], reverse=True)
    best_task, best_score = scored_tasks[0]

    return {
        "recommended_task": {
            "task_code": best_task.task_code,
            "title": best_task.title,
            "status": best_task.status,
            "priority": best_task.priority,
            "estimated_minutes": best_task.estimated_minutes,
            "tags": best_task.tags,
        },
        "reason": f"Best match for {energy_level} energy at {location} (score: {best_score})",
    }


def move_task(task_code: str, status: str, session: Session) -> dict:
    """Move task to new status."""
    task = session.exec(select(Task).where(Task.task_code == task_code)).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_status = task.status
    task.status = TaskStatus(status)
    session.add(task)
    session.commit()

    return {
        "task_code": task.task_code,
        "old_status": old_status,
        "new_status": task.status,
    }


def mark_done(task_code: str, session: Session) -> dict:
    """Mark task as done."""
    return move_task(task_code, "done", session)


def add_context(task_code: str, note: str, session: Session) -> dict:
    """Add context note to task."""
    task = session.exec(select(Task).where(Task.task_code == task_code)).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Append to description
    task.description = f"{task.description}\n\n{note}".strip()
    session.add(task)
    session.commit()

    return {
        "task_code": task.task_code,
        "note_added": True,
    }


def split_task(task_code: str, session: Session) -> dict:
    """Manually trigger AI split on task."""
    task = session.exec(select(Task).where(Task.task_code == task_code)).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Enqueue AI analysis
    job_id = enqueue_task_analysis(str(task.id))

    return {
        "task_code": task.task_code,
        "job_id": job_id,
        "status": "AI analysis queued",
    }


def list_environments(session: Session) -> dict:
    """List all environments."""
    environments = session.exec(select(Environment)).all()

    return {
        "environments": [
            {
                "id": str(env.id),
                "name": env.name,
                "repo_path": env.repo_path,
                "tech_stack": env.tech_stack,
            }
            for env in environments
        ]
    }


def get_ai_activity(limit: int = 50) -> dict:
    """Get recent AI activity logs."""
    # Placeholder - would connect to actual logging system
    return {
        "logs": [],
        "limit": limit,
        "note": "AI activity logging not yet implemented",
    }
