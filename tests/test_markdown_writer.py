"""Tests for markdown writer."""
from uuid import uuid4

from backend.models.task import Task, TaskStatus
from backend.sync.markdown_writer import generate_markdown


def test_generate_basic_markdown():
    """Test generating markdown from tasks."""
    tasks = [
        Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Setup authentication",
            status=TaskStatus.RADAR,
            tags=["backend"],
            order=0,
        ),
        Task(
            id=uuid4(),
            task_code="TASK-002",
            title="Add logging",
            status=TaskStatus.RUNWAY,
            tags=["infrastructure"],
            order=1,
        ),
        Task(
            id=uuid4(),
            task_code="TASK-003",
            title="Initial project setup",
            status=TaskStatus.DONE,
            tags=[],
            order=2,
        ),
    ]

    markdown = generate_markdown(tasks)

    # Check structure
    assert "## Radar" in markdown
    assert "## Runway" in markdown
    assert "## Done" in markdown

    # Check tasks
    assert "- [ ] Setup authentication #backend <!-- TASK-001 -->" in markdown
    assert "- [ ] Add logging #infrastructure <!-- TASK-002 -->" in markdown
    assert "- [x] Initial project setup <!-- TASK-003 -->" in markdown


def test_generate_with_subtasks():
    """Test generating markdown with subtasks."""
    parent_id = uuid4()
    tasks = [
        Task(
            id=parent_id,
            task_code="TASK-001",
            title="Implement task API",
            status=TaskStatus.RUNWAY,
            tags=[],
            order=0,
        ),
        Task(
            id=uuid4(),
            task_code="TASK-001-A",
            title="Create task model",
            status=TaskStatus.RUNWAY,
            tags=[],
            order=1,
            parent_task_id=parent_id,
        ),
        Task(
            id=uuid4(),
            task_code="TASK-001-B",
            title="Add CRUD endpoints",
            status=TaskStatus.RUNWAY,
            tags=[],
            order=2,
            parent_task_id=parent_id,
        ),
    ]

    markdown = generate_markdown(tasks)

    # Check parent task is not indented
    assert "- [ ] Implement task API <!-- TASK-001 -->" in markdown

    # Check subtasks are indented
    assert "  - [ ] Create task model <!-- TASK-001-A -->" in markdown
    assert "  - [ ] Add CRUD endpoints <!-- TASK-001-B -->" in markdown


def test_generate_empty_sections():
    """Test generating markdown with empty sections."""
    tasks = [
        Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Only task",
            status=TaskStatus.RADAR,
            tags=[],
            order=0,
        ),
    ]

    markdown = generate_markdown(tasks)

    # All sections should be present
    assert "## Radar" in markdown
    assert "## Runway" in markdown
    assert "## Flight" in markdown
    assert "## Blocked" in markdown
    assert "## Done" in markdown

    # Empty sections should have placeholder
    assert "*No tasks*" in markdown


def test_generate_with_multiple_tags():
    """Test generating tasks with multiple tags."""
    tasks = [
        Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Complex task",
            status=TaskStatus.RUNWAY,
            tags=["backend", "urgent", "api"],
            order=0,
        ),
    ]

    markdown = generate_markdown(tasks)

    # All tags should be present
    assert "#backend" in markdown
    assert "#urgent" in markdown
    assert "#api" in markdown
