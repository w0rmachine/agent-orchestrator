"""
MCP Server for Task Orchestration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Exposes task management tools for Claude Code sessions.

Two modes of operation:
1. Work mode: Track and work on tasks (AI-free)
2. Management mode: AI-assisted task organization

Usage:
    uv run mcp-server

Configuration:
    Uses the main application database (same source as Kanban dashboard)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.ai_manager import (
    analyze_task_complexity,
    analyze_task_batch,
    format_analysis_for_display,
    format_batch_analysis_for_display,
)
from backend.database import engine
from backend.models.task import Task as DBTask
from backend.models.task import TaskStatus as DBTaskStatus
from backend.tagging import sanitize_tags

# ── Types ─────────────────────────────────────────────────────────────────────
TaskStatus = Literal["todo", "in_progress", "done", "blocked"]
TaskPriority = Literal["critical", "high", "normal", "low"]


# ── Models ────────────────────────────────────────────────────────────────────
class Task(BaseModel):
    id: str = Field(default_factory=lambda: f"T-{uuid.uuid4().hex[:6].upper()}")
    title: str
    description: str = ""
    status: TaskStatus = "todo"
    priority: TaskPriority = "normal"
    tags: list[str] = []
    parent_id: str | None = None
    subtask_ids: list[str] = []
    context: dict[str, Any] = {}
    phase: str | None = None
    due_date: str | None = None
    repo_path: str | None = None
    app_stage: str | None = None
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    order: int = 0


STATUS_TO_DB: dict[TaskStatus, list[DBTaskStatus]] = {
    "todo": [DBTaskStatus.RADAR, DBTaskStatus.RUNWAY],
    "in_progress": [DBTaskStatus.FLIGHT],
    "done": [DBTaskStatus.DONE],
    "blocked": [DBTaskStatus.BLOCKED],
}

DB_TO_STATUS: dict[DBTaskStatus, TaskStatus] = {
    DBTaskStatus.RADAR: "todo",
    DBTaskStatus.RUNWAY: "todo",
    DBTaskStatus.FLIGHT: "in_progress",
    DBTaskStatus.DONE: "done",
    DBTaskStatus.BLOCKED: "blocked",
}

PRIORITY_TO_DB: dict[TaskPriority, int] = {
    "critical": 1,
    "high": 2,
    "normal": 3,
    "low": 5,
}


def _db_to_priority(value: int | None) -> TaskPriority:
    if value is None:
        return "normal"
    if value <= 1:
        return "critical"
    if value <= 2:
        return "high"
    if value <= 3:
        return "normal"
    return "low"


META_PREFIXES = ("phase:", "due:", "repo:")


def _extract_meta(location_tags: list[str]) -> tuple[str | None, str | None, str | None]:
    phase = None
    due_date = None
    repo_path = None
    for tag in location_tags or []:
        if tag.startswith("phase:"):
            phase = tag.removeprefix("phase:")
        elif tag.startswith("due:"):
            due_date = tag.removeprefix("due:")
        elif tag.startswith("repo:"):
            repo_path = tag.removeprefix("repo:")
    return phase, due_date, repo_path


def _merge_location_tags(
    current: list[str],
    phase: str | None,
    due_date: str | None,
    repo_path: str | None,
) -> list[str]:
    base = [t for t in (current or []) if not t.startswith(META_PREFIXES)]
    if phase:
        base.append(f"phase:{phase}")
    if due_date:
        base.append(f"due:{due_date}")
    if repo_path:
        base.append(f"repo:{repo_path}")
    return base


def _derive_app_stage(status: DBTaskStatus) -> str:
    if status in (DBTaskStatus.RADAR, DBTaskStatus.RUNWAY):
        return "backlog"
    if status == DBTaskStatus.FLIGHT:
        return "active"
    if status == DBTaskStatus.DONE:
        return "done"
    return "blocked"


class TaskStore:
    """Database-backed task store (shared with Kanban dashboard)."""

    def _find_db_task(self, session: Session, task_id: str) -> DBTask | None:
        """Find task by UUID or task_code."""
        try:
            task_uuid = UUID(task_id)
            task = session.get(DBTask, task_uuid)
            if task:
                return task
        except ValueError:
            pass

        return session.exec(select(DBTask).where(DBTask.task_code == task_id)).first()

    def _next_task_code(self, session: Session) -> str:
        existing = session.exec(select(DBTask.task_code)).all()
        max_num = 0
        for code in existing:
            if not code.startswith("MCP-"):
                continue
            try:
                max_num = max(max_num, int(code.split("-")[1]))
            except Exception:
                continue
        return f"MCP-{max_num + 1:04d}"

    def _to_mcp_task(self, session: Session, db_task: DBTask) -> Task:
        subtasks = session.exec(
            select(DBTask).where(DBTask.parent_task_id == db_task.id)
        ).all()
        parent_code = None
        if db_task.parent_task_id:
            parent = session.get(DBTask, db_task.parent_task_id)
            if parent:
                parent_code = parent.task_code

        phase, due_date, repo_path = _extract_meta(db_task.location_tags or [])
        return Task(
            id=db_task.task_code,
            title=db_task.title,
            description=db_task.description,
            status=DB_TO_STATUS.get(db_task.status, "todo"),
            priority=_db_to_priority(db_task.priority),
            tags=db_task.tags or [],
            parent_id=parent_code,
            subtask_ids=[t.task_code for t in subtasks],
            context={"phase": phase, "due_date": due_date, "repo_path": repo_path},
            phase=phase,
            due_date=due_date,
            repo_path=repo_path,
            app_stage=_derive_app_stage(db_task.status),
            created=db_task.created_at,
            updated=db_task.updated_at,
            order=db_task.order,
        )

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = "normal",
        tags: list[str] | None = None,
        context: dict[str, Any] | None = None,
        parent_id: str | None = None,
    ) -> Task:
        """Create a new task in DB."""
        with Session(engine) as session:
            parent_task_id: UUID | None = None
            if parent_id:
                parent_task = self._find_db_task(session, parent_id)
                if parent_task:
                    parent_task_id = parent_task.id

            db_task = DBTask(
                task_code=self._next_task_code(session),
                title=title,
                description=description,
                status=DBTaskStatus.RUNWAY,
                priority=PRIORITY_TO_DB.get(priority, 3),
                tags=sanitize_tags(tags),
                location_tags=_merge_location_tags(
                    [],
                    (context or {}).get("phase"),
                    (context or {}).get("due_date"),
                    (context or {}).get("repo_path"),
                ),
                parent_task_id=parent_task_id,
            )
            session.add(db_task)
            session.commit()
            session.refresh(db_task)
            return self._to_mcp_task(session, db_task)

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        with Session(engine) as session:
            db_task = self._find_db_task(session, task_id)
            if not db_task:
                return None
            return self._to_mcp_task(session, db_task)

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        tags: list[str] | None = None,
        phase: str | None = None,
    ) -> list[Task]:
        """List tasks with optional filters."""
        with Session(engine) as session:
            query = select(DBTask)
            if status:
                query = query.where(DBTask.status.in_(STATUS_TO_DB[status]))  # type: ignore[arg-type]
            if priority:
                query = query.where(DBTask.priority == PRIORITY_TO_DB[priority])
            db_tasks = session.exec(query).all()

            tasks = [self._to_mcp_task(session, task) for task in db_tasks]
            if tags:
                tasks = [t for t in tasks if any(tag in (t.tags or []) for tag in tags)]
            if phase:
                tasks = [t for t in tasks if t.phase == phase]
            return sorted(tasks, key=lambda t: (t.order, t.created))

    def update_task(
        self,
        task_id: str,
        **updates,
    ) -> Task | None:
        """Update a task."""
        with Session(engine) as session:
            db_task = self._find_db_task(session, task_id)
            if not db_task:
                return None

            if updates.get("title") is not None:
                db_task.title = updates["title"]
            if updates.get("description") is not None:
                db_task.description = updates["description"]
            if updates.get("status") is not None:
                status = updates["status"]
                db_task.status = STATUS_TO_DB[status][0]
            if updates.get("priority") is not None:
                db_task.priority = PRIORITY_TO_DB[updates["priority"]]
            if updates.get("tags") is not None:
                db_task.tags = sanitize_tags(updates["tags"])

            if updates.get("context") is not None and isinstance(updates["context"], dict):
                context = updates["context"]
                db_task.location_tags = _merge_location_tags(
                    db_task.location_tags,
                    context.get("phase"),
                    context.get("due_date"),
                    context.get("repo_path"),
                )

            db_task.updated_at = datetime.now(timezone.utc)
            session.add(db_task)
            session.commit()
            session.refresh(db_task)
            return self._to_mcp_task(session, db_task)

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        with Session(engine) as session:
            db_task = self._find_db_task(session, task_id)
            if not db_task:
                return False
            session.delete(db_task)
            session.commit()
            return True


# ── MCP Server ────────────────────────────────────────────────────────────────
app = Server("agent-orchestrator")
store = TaskStore()


async def _sync_markdown() -> None:
    """Sync DB changes to markdown vault when MCP mutates tasks."""
    from backend.sync.sync_service import sync_service
    await sync_service.sync_to_vault()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available task management tools."""
    return [
        Tool(
            name="create_task",
            description="Create a new task. Returns the created task with its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title (required)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed task description",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "high", "normal", "low"],
                        "description": "Task priority (default: normal)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for categorization",
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context. Supported keys: phase, due_date (YYYY-MM-DD), repo_path",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="list_tasks",
            description="List tasks with optional filters. Returns tasks sorted by order and creation date.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "done", "blocked"],
                        "description": "Filter by status",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "high", "normal", "low"],
                        "description": "Filter by priority",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (matches any)",
                    },
                    "phase": {
                        "type": "string",
                        "enum": ["backlog", "analyze", "active", "testing", "done", "blocked"],
                        "description": "Filter by workflow phase",
                    },
                },
            },
        ),
        Tool(
            name="get_task",
            description="Get detailed information about a specific task by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="update_task",
            description="Update task fields (title, description, status, priority, tags, context).",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to update",
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "done", "blocked"],
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "high", "normal", "low"],
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "context": {
                        "type": "object",
                        "description": "Context updates. Supported keys: phase, due_date (YYYY-MM-DD), repo_path",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="start_task",
            description="Mark a task as in_progress. Convenience wrapper around update_task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to start",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="complete_task",
            description="Mark a task as done. Convenience wrapper around update_task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to complete",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="block_task",
            description="Mark a task as blocked (needs external action).",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to block",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for blocking (added to context)",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="delete_task",
            description="Delete a task permanently.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to delete",
                    },
                },
                "required": ["task_id"],
            },
        ),
        # Management tools (AI-assisted)
        Tool(
            name="split_task",
            description="Split a task into subtasks. Use this in management sessions to break down complex tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Parent task ID",
                    },
                    "subtasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "priority": {
                                    "type": "string",
                                    "enum": ["critical", "high", "normal", "low"],
                                },
                            },
                            "required": ["title"],
                        },
                        "description": "List of subtasks to create",
                    },
                },
                "required": ["task_id", "subtasks"],
            },
        ),
        Tool(
            name="reorganize_tasks",
            description="Update task priorities and ordering. Use in management sessions to reorganize backlog.",
            inputSchema={
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "string"},
                                "priority": {
                                    "type": "string",
                                    "enum": ["critical", "high", "normal", "low"],
                                },
                                "order": {"type": "number"},
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["task_id"],
                        },
                    },
                },
                "required": ["updates"],
            },
        ),
        # AI-powered analysis tools (for management sessions)
        Tool(
            name="analyze_task",
            description="Get AI analysis of a task: complexity, split recommendations, priority suggestions. Use in management sessions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to analyze",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="analyze_backlog",
            description="Get AI analysis of multiple tasks with reorganization recommendations. Use in management sessions for planning.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of task IDs to analyze (leave empty for all todo tasks)",
                    },
                    "goal": {
                        "type": "string",
                        "description": "Optimization goal (e.g., 'prioritize bugs', 'quick wins first')",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "create_task":
            task = store.create_task(
                title=arguments["title"],
                description=arguments.get("description", ""),
                priority=arguments.get("priority", "normal"),
                tags=arguments.get("tags", []),
                context=arguments.get("context", {}),
            )
            await _sync_markdown()
            return [
                TextContent(
                    type="text",
                    text=f"Created task {task.id}: {task.title}\n\n{task.model_dump_json(indent=2)}",
                )
            ]

        elif name == "list_tasks":
            tasks = store.list_tasks(
                status=arguments.get("status"),
                priority=arguments.get("priority"),
                tags=arguments.get("tags"),
                phase=arguments.get("phase"),
            )
            if not tasks:
                return [TextContent(type="text", text="No tasks found.")]

            result = f"Found {len(tasks)} task(s):\n\n"
            for task in tasks:
                status_icon = {
                    "todo": "⭕",
                    "in_progress": "🔄",
                    "done": "✅",
                    "blocked": "🚫",
                }[task.status]
                priority_icon = {
                    "critical": "🔴",
                    "high": "🟠",
                    "normal": "🟡",
                    "low": "🟢",
                }[task.priority]

                tags_str = " ".join(f"#{tag}" for tag in task.tags) if task.tags else ""
                result += f"{status_icon} {priority_icon} [{task.id}] {task.title}\n"
                if task.description:
                    result += f"   {task.description[:100]}{'...' if len(task.description) > 100 else ''}\n"
                if tags_str:
                    result += f"   {tags_str}\n"
                result += "\n"

            return [TextContent(type="text", text=result)]

        elif name == "get_task":
            task = store.get_task(arguments["task_id"])
            if not task:
                return [
                    TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
                ]
            return [
                TextContent(
                    type="text",
                    text=f"Task {task.id}:\n\n{task.model_dump_json(indent=2)}",
                )
            ]

        elif name == "update_task":
            task_id = arguments.pop("task_id")
            task = store.update_task(task_id, **arguments)
            if not task:
                return [TextContent(type="text", text=f"Task {task_id} not found.")]
            await _sync_markdown()
            return [
                TextContent(
                    type="text",
                    text=f"Updated task {task.id}:\n\n{task.model_dump_json(indent=2)}",
                )
            ]

        elif name == "start_task":
            task = store.update_task(
                arguments["task_id"],
                status="in_progress",
                context={"phase": "active"},
            )
            if not task:
                return [
                    TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
                ]
            await _sync_markdown()
            return [
                TextContent(
                    type="text",
                    text=f"Started task {task.id}: {task.title}",
                )
            ]

        elif name == "complete_task":
            task = store.update_task(
                arguments["task_id"],
                status="done",
                context={"phase": "done"},
            )
            if not task:
                return [
                    TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
                ]
            await _sync_markdown()
            return [
                TextContent(
                    type="text",
                    text=f"Completed task {task.id}: {task.title}",
                )
            ]

        elif name == "block_task":
            reason = arguments.get("reason", "Blocked")
            task = store.update_task(
                arguments["task_id"],
                status="blocked",
                context={"phase": "blocked", "blocked_reason": reason},
            )
            if not task:
                return [
                    TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
                ]
            await _sync_markdown()
            return [
                TextContent(
                    type="text",
                    text=f"Blocked task {task.id}: {task.title}\nReason: {reason}",
                )
            ]

        elif name == "delete_task":
            if store.delete_task(arguments["task_id"]):
                await _sync_markdown()
                return [
                    TextContent(type="text", text=f"Deleted task {arguments['task_id']}")
                ]
            return [
                TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
            ]

        elif name == "split_task":
            parent_task = store.get_task(arguments["task_id"])
            if not parent_task:
                return [
                    TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
                ]

            subtask_ids = []
            for subtask_data in arguments["subtasks"]:
                subtask = store.create_task(
                    title=subtask_data["title"],
                    description=subtask_data.get("description", ""),
                    priority=subtask_data.get("priority", parent_task.priority),
                    tags=parent_task.tags + ["split"],
                    context={"parent_id": parent_task.id},
                    parent_id=parent_task.id,
                )
                subtask_ids.append(subtask.id)

            await _sync_markdown()

            result = f"Split task {parent_task.id} into {len(subtask_ids)} subtasks:\n\n"
            for subtask_id in subtask_ids:
                subtask = store.get_task(subtask_id)
                if subtask:
                    result += f"  - [{subtask.id}] {subtask.title}\n"

            return [TextContent(type="text", text=result)]

        elif name == "reorganize_tasks":
            results = []
            mutated = False
            for update in arguments["updates"]:
                task_id = update.pop("task_id")
                task = store.update_task(task_id, **update)
                if task:
                    results.append(f"  ✓ Updated {task.id}: {task.title}")
                    mutated = True
                else:
                    results.append(f"  ✗ Task {task_id} not found")

            if mutated:
                await _sync_markdown()

            return [
                TextContent(
                    type="text",
                    text=f"Reorganized {len(results)} task(s):\n\n" + "\n".join(results),
                )
            ]

        elif name == "analyze_task":
            task = store.get_task(arguments["task_id"])
            if not task:
                return [
                    TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
                ]

            analysis = await analyze_task_complexity(
                title=task.title,
                description=task.description,
                tags=task.tags,
            )

            formatted = format_analysis_for_display(analysis)
            return [TextContent(type="text", text=formatted)]

        elif name == "analyze_backlog":
            task_ids = arguments.get("task_ids", [])
            if not task_ids:
                # Default to all todo tasks
                todo_tasks = store.list_tasks(status="todo")
                task_ids = [t.id for t in todo_tasks]

            tasks = []
            for task_id in task_ids:
                task = store.get_task(task_id)
                if task:
                    tasks.append(task.model_dump())

            if not tasks:
                return [TextContent(type="text", text="No tasks to analyze.")]

            goal = arguments.get("goal", "Optimize for efficiency and priority")
            analysis = await analyze_task_batch(tasks, goal=goal)

            formatted = format_batch_analysis_for_display(analysis)
            return [TextContent(type="text", text=formatted)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def run_server():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def main():
    """Entry point."""
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
