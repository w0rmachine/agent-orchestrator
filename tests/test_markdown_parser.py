"""Tests for markdown parser."""
import tempfile
from pathlib import Path

from backend.models.task import TaskStatus
from backend.sync.markdown_parser import parse_markdown_file


def test_parse_basic_tasks():
    """Test parsing basic tasks from markdown."""
    markdown = """# AI Kanban

## Radar

- [ ] Setup authentication #backend <!-- TASK-001 -->
- [ ] Add logging #infrastructure <!-- TASK-002 -->

## Runway

- [ ] Implement task API <!-- TASK-003 -->
- [ ] Build sync engine <!-- TASK-004 -->

## Flight

- [ ] Deploy to production #deploy <!-- TASK-005 -->

## Blocked

- [ ] Waiting for API key <!-- TASK-006 -->

## Done

- [x] Initial project setup <!-- TASK-000 -->
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath)

        assert len(tasks) == 7

        # Check task codes
        assert tasks[0]["task_code"] == "TASK-001"
        assert tasks[1]["task_code"] == "TASK-002"
        assert tasks[6]["task_code"] == "TASK-000"

        # Check statuses
        assert tasks[0]["status"] == TaskStatus.RADAR
        assert tasks[2]["status"] == TaskStatus.RUNWAY
        assert tasks[4]["status"] == TaskStatus.FLIGHT
        assert tasks[5]["status"] == TaskStatus.BLOCKED
        assert tasks[6]["status"] == TaskStatus.DONE

        # Check tags
        assert "backend" in tasks[0]["tags"]
        assert "infrastructure" in tasks[1]["tags"]
        assert "deploy" in tasks[4]["tags"]

        # Check titles
        assert tasks[0]["title"] == "Setup authentication"
        assert tasks[6]["title"] == "Initial project setup"

        # Check completed
        assert not tasks[0]["completed"]
        assert tasks[6]["completed"]

    finally:
        Path(filepath).unlink()


def test_parse_subtasks():
    """Test parsing tasks with subtasks."""
    # Use explicit space characters to ensure proper indentation
    lines = [
        "## Runway",
        "",
        "- [ ] Implement task API <!-- TASK-001 -->",
        "  - [ ] Create task model <!-- TASK-001-A -->",
        "  - [ ] Add CRUD endpoints <!-- TASK-001-B -->",
        "    - [ ] POST endpoint <!-- TASK-001-B-1 -->",
        "    - [ ] GET endpoint <!-- TASK-001-B-2 -->",
    ]
    markdown = "\n".join(lines) + "\n"

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath)

        assert len(tasks) == 5

        # Check parent relationships
        assert tasks[0]["parent_task_code"] is None
        assert tasks[1]["parent_task_code"] == "TASK-001"
        assert tasks[2]["parent_task_code"] == "TASK-001"
        assert tasks[3]["parent_task_code"] == "TASK-001-B"
        assert tasks[4]["parent_task_code"] == "TASK-001-B"

    finally:
        Path(filepath).unlink()


def test_parse_empty_file():
    """Test parsing empty file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("")
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath)
        assert tasks == []
    finally:
        Path(filepath).unlink()


def test_parse_nonexistent_file():
    """Test parsing nonexistent file."""
    tasks = parse_markdown_file("/nonexistent/file.md")
    assert tasks == []
