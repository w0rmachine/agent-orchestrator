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


def test_parse_bracket_id_format():
    """Test parsing tasks with bracket ID notation [O-001]."""
    markdown = """## Backlog

- [ ] [O-001] Python Registry
- [ ] [O-002] Add coverage to backend
- [ ] [TASK-003] Another task with different prefix
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath)

        assert len(tasks) == 3
        assert tasks[0]["task_code"] == "O-001"
        assert tasks[0]["title"] == "Python Registry"
        assert tasks[1]["task_code"] == "O-002"
        assert tasks[2]["task_code"] == "TASK-003"

    finally:
        Path(filepath).unlink()


def test_auto_generate_ids():
    """Test auto-generating IDs for tasks without them."""
    markdown = """## In Progress

- [ ] Task without ID
- [ ] Another task without ID

## Backlog

- [ ] [O-010] Existing task with ID
- [ ] [O-005] Earlier ID number
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath, auto_generate_ids=True)

        assert len(tasks) == 4

        # First two tasks should have auto-generated IDs
        # They should use the "O" prefix and start from 011 (max is 010)
        assert tasks[0]["task_code"] == "O-011"
        assert tasks[0]["title"] == "Task without ID"
        assert tasks[1]["task_code"] == "O-012"
        assert tasks[1]["title"] == "Another task without ID"

        # Existing tasks keep their IDs
        assert tasks[2]["task_code"] == "O-010"
        assert tasks[3]["task_code"] == "O-005"

    finally:
        Path(filepath).unlink()


def test_auto_generate_ids_disabled():
    """Test that tasks without IDs are skipped when auto_generate_ids=False."""
    markdown = """## In Progress

- [ ] Task without ID
- [ ] [O-001] Task with ID
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath, auto_generate_ids=False)

        assert len(tasks) == 1
        assert tasks[0]["task_code"] == "O-001"

    finally:
        Path(filepath).unlink()


def test_auto_generate_ids_default_prefix():
    """Test that default prefix is used when no existing IDs."""
    markdown = """## Backlog

- [ ] Task without any ID format
- [ ] Another task
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath, auto_generate_ids=True)

        assert len(tasks) == 2
        # Should use default prefix "TASK"
        assert tasks[0]["task_code"] == "TASK-001"
        assert tasks[1]["task_code"] == "TASK-002"

    finally:
        Path(filepath).unlink()


def test_mixed_id_formats():
    """Test parsing with both HTML comment and bracket ID formats."""
    markdown = """## Runway

- [ ] [O-001] Bracket format
- [ ] HTML comment format <!-- TASK-002 -->
- [ ] [PREFIX-003] Different prefix
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath)

        assert len(tasks) == 3
        assert tasks[0]["task_code"] == "O-001"
        assert tasks[1]["task_code"] == "TASK-002"
        assert tasks[2]["task_code"] == "PREFIX-003"

    finally:
        Path(filepath).unlink()


def test_reserved_role_tags_are_filtered_from_markdown():
    """Role labels are UI concerns and should never persist as task tags."""
    markdown = """## Runway

- [ ] Implement endpoint #backend #manager #coder #analyzer <!-- TASK-010 -->
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath)

        assert len(tasks) == 1
        assert tasks[0]["tags"] == ["backend"]

    finally:
        Path(filepath).unlink()


def test_alternative_section_headers():
    """Test parsing with alternative section header names."""
    markdown = """## In Progress

- [ ] Flight task <!-- TASK-001 -->

## Waiting / Blocked

- [ ] Blocked task <!-- TASK-002 -->

## Todo

- [ ] Runway task <!-- TASK-003 -->
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath)

        assert len(tasks) == 3
        assert tasks[0]["status"] == TaskStatus.FLIGHT
        assert tasks[1]["status"] == TaskStatus.BLOCKED
        assert tasks[2]["status"] == TaskStatus.RUNWAY

    finally:
        Path(filepath).unlink()


def test_tags_extracted_from_title():
    """Test that hashtags are extracted from title."""
    markdown = """## Radar

- [ ] Fix bug #urgent #backend #p1 <!-- TASK-001 -->
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(markdown)
        filepath = f.name

    try:
        tasks = parse_markdown_file(filepath)

        assert len(tasks) == 1
        assert tasks[0]["title"] == "Fix bug"  # Tags removed from title
        assert "urgent" in tasks[0]["tags"]
        assert "backend" in tasks[0]["tags"]
        assert "p1" in tasks[0]["tags"]

    finally:
        Path(filepath).unlink()
