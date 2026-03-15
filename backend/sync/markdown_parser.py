"""Markdown parser for Obsidian Kanban format."""
import re
from typing import Any

from backend.models.task import TaskStatus

# Regex patterns
TASK_RE = re.compile(r"^(\s*)- \[([x ])\] (.+)$")
# Match TASK-001, TASK-001-A, TASK-001-B-1, etc.
ID_RE = re.compile(r"<!--\s*([A-Z]+-\d+(?:-[A-Z0-9]+)*)\s*-->")
TAG_RE = re.compile(r"#(\w+)")

# Map section headers to task status
HEADER_TO_STATUS = {
    "radar": TaskStatus.RADAR,
    "runway": TaskStatus.RUNWAY,
    "flight": TaskStatus.FLIGHT,
    "blocked": TaskStatus.BLOCKED,
    "done": TaskStatus.DONE,
}


def extract_task_id(line: str) -> str | None:
    """Extract task ID from HTML comment."""
    match = ID_RE.search(line)
    return match.group(1) if match else None


def extract_tags(line: str) -> list[str]:
    """Extract hashtags from line."""
    return TAG_RE.findall(line)


def parse_markdown_file(filepath: str) -> list[dict[str, Any]]:
    """Parse Obsidian markdown file into task dictionaries.

    Args:
        filepath: Path to markdown file

    Returns:
        List of task dictionaries with structure:
        {
            'task_code': 'TASK-001',
            'title': 'Task title',
            'description': '',
            'status': TaskStatus.RADAR,
            'tags': ['backend', 'urgent'],
            'order': 0,
            'parent_task_code': None,  # or 'TASK-001' for subtasks
            'completed': False,
        }
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []

    tasks = []
    current_status: TaskStatus | None = None
    order_counter = 0
    parent_stack: list[tuple[int, str]] = []  # (indent_level, task_code)

    for line in lines:
        line = line.rstrip("\n")

        # Check for section headers
        if line.startswith("## "):
            header = line[3:].strip().lower()
            current_status = HEADER_TO_STATUS.get(header)
            continue

        # Skip if not in a recognized section
        if current_status is None:
            continue

        # Check for task line
        match = TASK_RE.match(line)
        if not match:
            continue

        indent_str, checkbox, content = match.groups()
        # Calculate indent level (2 spaces per level)
        indent_level = len(indent_str) // 2

        # Extract task ID
        task_code = extract_task_id(content)
        if not task_code:
            continue

        # Remove ID comment from content
        title = ID_RE.sub("", content).strip()

        # Extract tags
        tags = extract_tags(title)

        # Remove tags from title
        title = TAG_RE.sub("", title).strip()

        # Determine parent task based on indentation
        parent_task_code = None
        if indent_level > 0:
            # Find parent (task with lesser indent)
            # Filter to keep only ancestors
            ancestors = [
                (lvl, code) for lvl, code in parent_stack if lvl < indent_level
            ]
            if ancestors:
                parent_task_code = ancestors[-1][1]

        # Update parent stack: remove tasks at same or greater level, then add current
        parent_stack = [
            (lvl, code) for lvl, code in parent_stack if lvl < indent_level
        ]
        parent_stack.append((indent_level, task_code))

        # Parse completed status
        completed = checkbox.lower() == "x"

        task_dict = {
            "task_code": task_code,
            "title": title,
            "description": "",
            "status": TaskStatus.DONE if completed else current_status,
            "tags": tags,
            "order": order_counter,
            "parent_task_code": parent_task_code,
            "completed": completed,
        }

        tasks.append(task_dict)
        order_counter += 1

    return tasks
