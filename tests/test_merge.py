"""Tests for merge conflict resolution."""
from uuid import uuid4

import pytest

from backend.models.task import Task, TaskStatus
from backend.sync.merge import merge_task, should_delete_task


class TestMergeTask:
    """Tests for merge_task function."""

    def test_new_task_from_markdown(self):
        """Test that new tasks from markdown win all fields."""
        md_task = {
            "task_code": "TASK-001",
            "title": "New task from markdown",
            "description": "Description",
            "status": TaskStatus.RADAR,
            "tags": ["backend", "urgent"],
            "order": 5,
            "parent_task_code": None,
            "completed": False,
        }

        result = merge_task(None, md_task)

        assert result == md_task

    def test_markdown_wins_title(self):
        """Test that markdown wins for title changes."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Original title",
            status=TaskStatus.RADAR,
            priority=3,
            tags=["old"],
            order=0,
        )

        md_task = {
            "task_code": "TASK-001",
            "title": "Updated title from markdown",
            "status": TaskStatus.RADAR,
            "tags": ["new", "updated"],
            "order": 1,
            "completed": False,
        }

        result = merge_task(db_task, md_task)

        assert result["title"] == "Updated title from markdown"

    def test_markdown_wins_tags(self):
        """Test that markdown wins for tag changes."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Task",
            status=TaskStatus.RADAR,
            tags=["old-tag"],
            order=0,
        )

        md_task = {
            "task_code": "TASK-001",
            "title": "Task",
            "status": TaskStatus.RADAR,
            "tags": ["new-tag", "another"],
            "order": 0,
            "completed": False,
        }

        result = merge_task(db_task, md_task)

        assert result["tags"] == ["new-tag", "another"]

    def test_markdown_wins_order(self):
        """Test that markdown wins for order changes."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Task",
            status=TaskStatus.RADAR,
            order=0,
        )

        md_task = {
            "task_code": "TASK-001",
            "title": "Task",
            "status": TaskStatus.RADAR,
            "tags": [],
            "order": 10,
            "completed": False,
        }

        result = merge_task(db_task, md_task)

        assert result["order"] == 10

    def test_markdown_checkbox_marks_done(self):
        """Test that checking a checkbox in markdown marks task as done."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Task",
            status=TaskStatus.FLIGHT,
            order=0,
        )

        md_task = {
            "task_code": "TASK-001",
            "title": "Task",
            "status": TaskStatus.FLIGHT,
            "tags": [],
            "order": 0,
            "completed": True,  # Checkbox checked
        }

        result = merge_task(db_task, md_task)

        assert result["status"] == TaskStatus.DONE

    def test_db_wins_status_when_not_completed(self):
        """Test that DB wins for status when markdown checkbox is unchecked."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Task",
            status=TaskStatus.FLIGHT,  # In flight in DB
            order=0,
        )

        md_task = {
            "task_code": "TASK-001",
            "title": "Task",
            "status": TaskStatus.RADAR,  # Different in markdown
            "tags": [],
            "order": 0,
            "completed": False,
        }

        result = merge_task(db_task, md_task)

        assert result["status"] == TaskStatus.FLIGHT  # DB wins

    def test_db_wins_task_code(self):
        """Test that DB wins for task code."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Task",
            status=TaskStatus.RADAR,
            order=0,
        )

        md_task = {
            "task_code": "TASK-999",  # Different code
            "title": "Task",
            "status": TaskStatus.RADAR,
            "tags": [],
            "order": 0,
            "completed": False,
        }

        result = merge_task(db_task, md_task)

        assert result["task_code"] == "TASK-001"  # DB wins

    def test_db_wins_priority(self):
        """Test that DB wins for AI-assigned priority."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Task",
            status=TaskStatus.RADAR,
            priority=5,
            order=0,
        )

        md_task = {
            "task_code": "TASK-001",
            "title": "Task",
            "status": TaskStatus.RADAR,
            "tags": [],
            "order": 0,
            "completed": False,
        }

        result = merge_task(db_task, md_task)

        assert result["priority"] == 5

    def test_db_wins_estimated_minutes(self):
        """Test that DB wins for AI-estimated time."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Task",
            status=TaskStatus.RADAR,
            estimated_minutes=120,
            order=0,
        )

        md_task = {
            "task_code": "TASK-001",
            "title": "Task",
            "status": TaskStatus.RADAR,
            "tags": [],
            "order": 0,
            "completed": False,
        }

        result = merge_task(db_task, md_task)

        assert result["estimated_minutes"] == 120

    def test_db_wins_ai_generated_flag(self):
        """Test that DB wins for ai_generated flag."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Task",
            status=TaskStatus.RADAR,
            ai_generated=True,
            order=0,
        )

        md_task = {
            "task_code": "TASK-001",
            "title": "Task",
            "status": TaskStatus.RADAR,
            "tags": [],
            "order": 0,
            "completed": False,
        }

        result = merge_task(db_task, md_task)

        assert result["ai_generated"] is True

    def test_db_wins_parent_for_ai_generated(self):
        """Test that DB wins for parent_task_id when task is AI-generated."""
        parent_id = uuid4()
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001-A",
            title="Subtask",
            status=TaskStatus.RADAR,
            ai_generated=True,
            parent_task_id=parent_id,
            order=0,
        )

        md_task = {
            "task_code": "TASK-001-A",
            "title": "Subtask",
            "status": TaskStatus.RADAR,
            "tags": [],
            "order": 0,
            "completed": False,
            "parent_task_code": "TASK-999",  # Different parent in markdown
        }

        result = merge_task(db_task, md_task)

        assert result["parent_task_id"] == parent_id

    def test_markdown_wins_parent_for_manual_task(self):
        """Test that markdown wins for parent when task is manually created."""
        db_task = Task(
            id=uuid4(),
            task_code="TASK-001-A",
            title="Subtask",
            status=TaskStatus.RADAR,
            ai_generated=False,
            parent_task_id=None,
            order=0,
        )

        md_task = {
            "task_code": "TASK-001-A",
            "title": "Subtask",
            "status": TaskStatus.RADAR,
            "tags": [],
            "order": 0,
            "completed": False,
            "parent_task_code": "TASK-001",
        }

        result = merge_task(db_task, md_task)

        assert result["parent_task_code"] == "TASK-001"


class TestShouldDeleteTask:
    """Tests for should_delete_task function."""

    def test_manual_task_should_be_deleted(self):
        """Test that manually created tasks can be deleted."""
        task = Task(
            id=uuid4(),
            task_code="TASK-001",
            title="Manual task",
            status=TaskStatus.RADAR,
            ai_generated=False,
        )

        assert should_delete_task(task) is True

    def test_ai_generated_task_should_not_be_deleted(self):
        """Test that AI-generated tasks are not deleted by markdown sync."""
        task = Task(
            id=uuid4(),
            task_code="TASK-001-A",
            title="AI-generated subtask",
            status=TaskStatus.RADAR,
            ai_generated=True,
        )

        assert should_delete_task(task) is False
