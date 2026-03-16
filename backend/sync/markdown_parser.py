"""Markdown parser for Obsidian Kanban format."""
import re
from typing import Any

from backend.models.task import TaskStatus
from backend.tagging import sanitize_tags

# Regex patterns
TASK_RE = re.compile(r"^(\s*)- \[([x ])\] (.+)$")
# Match TASK-001, TASK-001-A, TASK-001-B-1, etc. in HTML comments
ID_RE = re.compile(r"<!--\s*([A-Z]+-\d+(?:-[A-Z0-9]+)*)\s*-->")
# Match [O-001], [TASK-001], etc. in brackets at start of title
BRACKET_ID_RE = re.compile(r"^\[([A-Z]+-\d+(?:-[A-Z0-9]+)*)\]")
# Extract numeric part from task ID (e.g., "O-023" -> 23)
ID_NUMBER_RE = re.compile(r"^([A-Z]+)-(\d+)")
TAG_RE = re.compile(r"#(\w+)")

# Default prefix for auto-generated IDs
DEFAULT_ID_PREFIX = "TASK"

# Map section headers to task status
HEADER_TO_STATUS = {
    "radar": TaskStatus.RADAR,
    "backlog": TaskStatus.RADAR,
    "todo": TaskStatus.RUNWAY,
    "runway": TaskStatus.RUNWAY,
    "in progress": TaskStatus.FLIGHT,
    "flight": TaskStatus.FLIGHT,
    "blocked": TaskStatus.BLOCKED,
    "waiting": TaskStatus.BLOCKED,
    "waiting / blocked": TaskStatus.BLOCKED,
    "done": TaskStatus.DONE,
}


def extract_task_id(line: str) -> str | None:
    """Extract task ID from HTML comment or bracket notation.

    Supports both formats:
    - HTML comment: "Task title <!-- TASK-001 -->"
    - Bracket notation: "[O-001] Task title"
    """
    # Try HTML comment first
    match = ID_RE.search(line)
    if match:
        return match.group(1)

    # Try bracket notation
    match = BRACKET_ID_RE.search(line)
    if match:
        return match.group(1)

    return None


def extract_tags(line: str) -> list[str]:
    """Extract hashtags from line."""
    return TAG_RE.findall(line)


def _scan_existing_ids(lines: list[str]) -> tuple[str, int]:
    """Scan file to find existing ID prefix and max number.

    Args:
        lines: Lines from the markdown file

    Returns:
        Tuple of (prefix, max_number). E.g., ("O", 23) for IDs like O-001 to O-023.
        Returns (DEFAULT_ID_PREFIX, 0) if no existing IDs found.
    """
    prefix = None
    max_number = 0

    for line in lines:
        match = TASK_RE.match(line.rstrip("\n"))
        if not match:
            continue

        content = match.group(3)
        task_id = extract_task_id(content)
        if not task_id:
            continue

        # Extract prefix and number from task ID
        id_match = ID_NUMBER_RE.match(task_id)
        if id_match:
            id_prefix, id_num = id_match.groups()
            if prefix is None:
                prefix = id_prefix
            max_number = max(max_number, int(id_num))

    return (prefix or DEFAULT_ID_PREFIX, max_number)


def parse_markdown_file(filepath: str, auto_generate_ids: bool = True) -> list[dict[str, Any]]:
    """Parse Obsidian markdown file into task dictionaries.

    Args:
        filepath: Path to markdown file
        auto_generate_ids: If True, auto-generate IDs for tasks without them

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

    # Scan for existing IDs to determine prefix and starting number
    id_prefix, max_id_number = _scan_existing_ids(lines)
    next_id_number = max_id_number + 1

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

        # Extract task ID or auto-generate one
        task_code = extract_task_id(content)
        if not task_code:
            if not auto_generate_ids:
                continue
            # Auto-generate ID
            task_code = f"{id_prefix}-{next_id_number:03d}"
            next_id_number += 1

        # Remove ID comment or bracket from content
        title = ID_RE.sub("", content).strip()
        title = BRACKET_ID_RE.sub("", title).strip()

        # Extract tags
        tags = sanitize_tags(extract_tags(title))

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
