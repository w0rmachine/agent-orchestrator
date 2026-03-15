"""Conflict resolution rules for markdown sync.

Per roadmap section 9:

|Field                      |Winner                                        |
|---------------------------|----------------------------------------------|
|Status                     |**DB wins**                                   |
|Task code / ID             |**DB wins**                                   |
|AI-generated fields        |**DB wins**                                   |
|Subtasks created by AI     |**DB wins**                                   |
|Title text edits           |**Markdown wins**                             |
|New tasks created by hand  |**Markdown wins**                             |
|Checkbox ticked in markdown|**Markdown wins** (triggers `task_done` event)|
"""
from typing import Any

from backend.models.task import Task, TaskStatus


def merge_task(db_task: Task | None, md_task: dict[str, Any]) -> dict[str, Any]:
    """Merge markdown task data with database task.

    Args:
        db_task: Existing task from database (None if new task)
        md_task: Task data parsed from markdown

    Returns:
        Merged task data to save to database
    """
    if db_task is None:
        # New task from markdown: markdown wins all fields
        return md_task

    # Task exists in both: apply merge rules
    merged = {}

    # Markdown wins: Title
    merged["title"] = md_task["title"]

    # Markdown wins: Checkbox status
    if md_task["completed"]:
        merged["status"] = TaskStatus.DONE
    else:
        # DB wins: Status (if not marked done in markdown)
        merged["status"] = db_task.status

    # Markdown wins: Tags
    merged["tags"] = md_task["tags"]

    # DB wins: Task code
    merged["task_code"] = db_task.task_code

    # DB wins: AI-generated fields
    merged["priority"] = db_task.priority
    merged["estimated_minutes"] = db_task.estimated_minutes
    merged["ai_generated"] = db_task.ai_generated

    # Markdown wins: Order
    merged["order"] = md_task["order"]

    # DB wins: Parent task ID (AI-generated subtasks)
    # But use markdown's parent if the task is not AI-generated
    if db_task.ai_generated:
        merged["parent_task_id"] = db_task.parent_task_id
    else:
        merged["parent_task_code"] = md_task.get("parent_task_code")

    return merged


def should_delete_task(db_task: Task) -> bool:
    """Check if a task should be deleted.

    A task should be deleted if:
    - It was manually created (not AI-generated)
    - It was removed from the markdown file

    Args:
        db_task: Task from database

    Returns:
        True if task should be deleted
    """
    # AI-generated tasks are never deleted by markdown sync
    # They can only be deleted via API
    return not db_task.ai_generated
