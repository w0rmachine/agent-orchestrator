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
    Set TASK_STORE_PATH to persist tasks (default: ./tasks.json)
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)
from pydantic import BaseModel, Field

from backend.ai_manager import (
    analyze_task_complexity,
    analyze_task_batch,
    format_analysis_for_display,
    format_batch_analysis_for_display,
)

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
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    order: int = 0


class TaskStore:
    """Simple JSON-backed task store."""

    def __init__(self, path: str = "./tasks.json"):
        self.path = Path(path)
        self.tasks: dict[str, Task] = {}
        self.load()

    def load(self):
        """Load tasks from disk."""
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            for task_data in data.get("tasks", []):
                task = Task(**task_data)
                self.tasks[task.id] = task
        except Exception as e:
            print(f"Warning: Could not load tasks from {self.path}: {e}")

    def save(self):
        """Persist tasks to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tasks": [task.model_dump(mode="json") for task in self.tasks.values()],
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        self.path.write_text(json.dumps(data, indent=2))

    def create_task(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = "normal",
        tags: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> Task:
        """Create a new task."""
        task = Task(
            title=title,
            description=description,
            priority=priority,
            tags=tags or [],
            context=context or {},
        )
        self.tasks[task.id] = task
        self.save()
        return task

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        tags: list[str] | None = None,
    ) -> list[Task]:
        """List tasks with optional filters."""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if priority:
            tasks = [t for t in tasks if t.priority == priority]
        if tags:
            tasks = [t for t in tasks if any(tag in t.tags for tag in tags)]
        return sorted(tasks, key=lambda t: (t.order, t.created))

    def update_task(
        self,
        task_id: str,
        **updates,
    ) -> Task | None:
        """Update a task."""
        task = self.tasks.get(task_id)
        if not task:
            return None

        for field, value in updates.items():
            if hasattr(task, field) and value is not None:
                setattr(task, field, value)

        task.updated = datetime.now(timezone.utc)
        self.save()
        return task

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        if task_id in self.tasks:
            self.tasks.pop(task_id)
            self.save()
            return True
        return False


# ── MCP Server ────────────────────────────────────────────────────────────────
app = Server("agent-orchestrator")
store = TaskStore(os.getenv("TASK_STORE_PATH", "./tasks.json"))


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
                        "description": "Additional context (repo, branch, files, etc.)",
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
                    "context": {"type": "object"},
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
            return [
                TextContent(
                    type="text",
                    text=f"Updated task {task.id}:\n\n{task.model_dump_json(indent=2)}",
                )
            ]

        elif name == "start_task":
            task = store.update_task(arguments["task_id"], status="in_progress")
            if not task:
                return [
                    TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
                ]
            return [
                TextContent(
                    type="text",
                    text=f"Started task {task.id}: {task.title}",
                )
            ]

        elif name == "complete_task":
            task = store.update_task(arguments["task_id"], status="done")
            if not task:
                return [
                    TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
                ]
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
                context={"blocked_reason": reason},
            )
            if not task:
                return [
                    TextContent(type="text", text=f"Task {arguments['task_id']} not found.")
                ]
            return [
                TextContent(
                    type="text",
                    text=f"Blocked task {task.id}: {task.title}\nReason: {reason}",
                )
            ]

        elif name == "delete_task":
            if store.delete_task(arguments["task_id"]):
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
                )
                subtask.parent_id = parent_task.id
                subtask_ids.append(subtask.id)
                store.save()

            parent_task.subtask_ids = subtask_ids
            parent_task.tags = list(set(parent_task.tags + ["parent"]))
            store.save()

            result = f"Split task {parent_task.id} into {len(subtask_ids)} subtasks:\n\n"
            for subtask_id in subtask_ids:
                subtask = store.get_task(subtask_id)
                if subtask:
                    result += f"  - [{subtask.id}] {subtask.title}\n"

            return [TextContent(type="text", text=result)]

        elif name == "reorganize_tasks":
            results = []
            for update in arguments["updates"]:
                task_id = update.pop("task_id")
                task = store.update_task(task_id, **update)
                if task:
                    results.append(f"  ✓ Updated {task.id}: {task.title}")
                else:
                    results.append(f"  ✗ Task {task_id} not found")

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
