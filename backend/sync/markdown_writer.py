"""Markdown writer for generating Obsidian Kanban format."""
from backend.models.task import Task, TaskStatus


def generate_markdown(tasks: list[Task]) -> str:
    """Generate Obsidian Kanban markdown from task list.

    Args:
        tasks: List of Task models from database

    Returns:
        Formatted markdown string
    """
    # Group tasks by status
    tasks_by_status: dict[TaskStatus, list[Task]] = {
        TaskStatus.RADAR: [],
        TaskStatus.RUNWAY: [],
        TaskStatus.FLIGHT: [],
        TaskStatus.BLOCKED: [],
        TaskStatus.DONE: [],
    }

    for task in tasks:
        # Only include top-level tasks, subtasks will be nested
        if task.parent_task_id is None:
            tasks_by_status[task.status].append(task)

    # Sort tasks within each status by order
    for task_list in tasks_by_status.values():
        task_list.sort(key=lambda t: t.order)

    # Build markdown sections
    sections = []

    for status in TaskStatus:
        # Section header
        sections.append(f"## {status.value.upper()}")
        sections.append("")

        status_tasks = tasks_by_status[status]
        if not status_tasks:
            sections.append("*No tasks*")
            sections.append("")
            continue

        # Render tasks
        for task in status_tasks:
            sections.extend(_render_task(task, tasks, indent=0))

        sections.append("")

    return "\n".join(sections).strip() + "\n"


def _render_task(task: Task, all_tasks: list[Task], indent: int = 0) -> list[str]:
    """Render a task and its subtasks as markdown lines.

    Args:
        task: Task to render
        all_tasks: All tasks (to find subtasks)
        indent: Current indentation level

    Returns:
        List of markdown lines
    """
    lines = []

    # Checkbox
    checkbox = "x" if task.status == TaskStatus.DONE else " "

    # Indentation
    indent_str = "  " * indent

    # Tags
    tags_str = " ".join(f"#{tag}" for tag in task.tags) if task.tags else ""
    tags_suffix = f" {tags_str}" if tags_str else ""

    # Task line
    line = f"{indent_str}- [{checkbox}] {task.title}{tags_suffix} <!-- {task.task_code} -->"
    lines.append(line)

    # Find and render subtasks
    subtasks = [t for t in all_tasks if t.parent_task_id == task.id]
    subtasks.sort(key=lambda t: t.order)

    for subtask in subtasks:
        lines.extend(_render_task(subtask, all_tasks, indent=indent + 1))

    return lines
