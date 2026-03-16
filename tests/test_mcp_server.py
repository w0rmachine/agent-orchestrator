"""Tests for MCP server task management."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.mcp_server import Task, TaskStore, app, call_tool, list_tools, store


class TestTask:
    """Tests for Task model."""

    def test_task_default_id(self):
        """Test that tasks get auto-generated IDs."""
        task = Task(title="Test task")

        assert task.id.startswith("T-")
        assert len(task.id) == 8  # T- + 6 chars

    def test_task_default_values(self):
        """Test task default values."""
        task = Task(title="Test task")

        assert task.title == "Test task"
        assert task.description == ""
        assert task.status == "todo"
        assert task.priority == "normal"
        assert task.tags == []
        assert task.parent_id is None
        assert task.subtask_ids == []
        assert task.context == {}
        assert task.order == 0

    def test_task_with_all_fields(self):
        """Test creating task with all fields."""
        task = Task(
            id="T-CUSTOM",
            title="Custom task",
            description="A detailed description",
            status="in_progress",
            priority="high",
            tags=["backend", "urgent"],
            parent_id="T-PARENT",
            subtask_ids=["T-SUB1", "T-SUB2"],
            context={"repo": "test/repo", "branch": "main"},
            order=5,
        )

        assert task.id == "T-CUSTOM"
        assert task.title == "Custom task"
        assert task.description == "A detailed description"
        assert task.status == "in_progress"
        assert task.priority == "high"
        assert task.tags == ["backend", "urgent"]
        assert task.parent_id == "T-PARENT"
        assert task.subtask_ids == ["T-SUB1", "T-SUB2"]
        assert task.context == {"repo": "test/repo", "branch": "main"}
        assert task.order == 5


class TestTaskStore:
    """Tests for TaskStore class."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary file for task storage."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            filepath = f.name
        yield filepath
        Path(filepath).unlink(missing_ok=True)

    def test_create_task(self, temp_store_path):
        """Test creating a task."""
        store = TaskStore(temp_store_path)

        task = store.create_task(
            title="New task",
            description="Task description",
            priority="high",
            tags=["backend"],
            context={"branch": "feature/test"},
        )

        assert task.title == "New task"
        assert task.description == "Task description"
        assert task.priority == "high"
        assert task.tags == ["backend"]
        assert task.context == {"branch": "feature/test"}
        assert task.id in store.tasks

    def test_create_task_with_defaults(self, temp_store_path):
        """Test creating a task with default values."""
        store = TaskStore(temp_store_path)

        task = store.create_task(title="Simple task")

        assert task.title == "Simple task"
        assert task.description == ""
        assert task.priority == "normal"
        assert task.tags == []
        assert task.context == {}

    def test_get_task(self, temp_store_path):
        """Test retrieving a task by ID."""
        store = TaskStore(temp_store_path)
        task = store.create_task(title="Test task")

        retrieved = store.get_task(task.id)

        assert retrieved is not None
        assert retrieved.id == task.id
        assert retrieved.title == "Test task"

    def test_get_nonexistent_task(self, temp_store_path):
        """Test retrieving a nonexistent task."""
        store = TaskStore(temp_store_path)

        retrieved = store.get_task("T-NONEXISTENT")

        assert retrieved is None

    def test_list_tasks_all(self, temp_store_path):
        """Test listing all tasks."""
        store = TaskStore(temp_store_path)
        store.create_task(title="Task 1")
        store.create_task(title="Task 2")
        store.create_task(title="Task 3")

        tasks = store.list_tasks()

        assert len(tasks) == 3

    def test_list_tasks_by_status(self, temp_store_path):
        """Test filtering tasks by status."""
        store = TaskStore(temp_store_path)
        task1 = store.create_task(title="Task 1")
        task2 = store.create_task(title="Task 2")
        store.update_task(task2.id, status="in_progress")

        todo_tasks = store.list_tasks(status="todo")
        in_progress_tasks = store.list_tasks(status="in_progress")

        assert len(todo_tasks) == 1
        assert len(in_progress_tasks) == 1

    def test_list_tasks_by_priority(self, temp_store_path):
        """Test filtering tasks by priority."""
        store = TaskStore(temp_store_path)
        store.create_task(title="Normal task", priority="normal")
        store.create_task(title="High task", priority="high")
        store.create_task(title="Critical task", priority="critical")

        high_tasks = store.list_tasks(priority="high")

        assert len(high_tasks) == 1
        assert high_tasks[0].title == "High task"

    def test_list_tasks_by_tags(self, temp_store_path):
        """Test filtering tasks by tags."""
        store = TaskStore(temp_store_path)
        store.create_task(title="Backend task", tags=["backend", "api"])
        store.create_task(title="Frontend task", tags=["frontend", "ui"])
        store.create_task(title="Full stack task", tags=["backend", "frontend"])

        backend_tasks = store.list_tasks(tags=["backend"])

        assert len(backend_tasks) == 2

    def test_list_tasks_sorted_by_order(self, temp_store_path):
        """Test that tasks are sorted by order."""
        store = TaskStore(temp_store_path)
        task1 = store.create_task(title="First")
        task2 = store.create_task(title="Second")
        task3 = store.create_task(title="Third")

        store.update_task(task3.id, order=0)
        store.update_task(task1.id, order=2)
        store.update_task(task2.id, order=1)

        tasks = store.list_tasks()

        assert tasks[0].title == "Third"
        assert tasks[1].title == "Second"
        assert tasks[2].title == "First"

    def test_update_task(self, temp_store_path):
        """Test updating task fields."""
        store = TaskStore(temp_store_path)
        task = store.create_task(title="Original title")

        updated = store.update_task(
            task.id,
            title="Updated title",
            status="in_progress",
            priority="high",
        )

        assert updated is not None
        assert updated.title == "Updated title"
        assert updated.status == "in_progress"
        assert updated.priority == "high"

    def test_update_nonexistent_task(self, temp_store_path):
        """Test updating a nonexistent task."""
        store = TaskStore(temp_store_path)

        result = store.update_task("T-NONEXISTENT", title="New title")

        assert result is None

    def test_update_task_partial(self, temp_store_path):
        """Test partial update (only some fields)."""
        store = TaskStore(temp_store_path)
        task = store.create_task(
            title="Original",
            description="Original desc",
            priority="normal",
        )

        updated = store.update_task(task.id, priority="high")

        assert updated.title == "Original"  # Unchanged
        assert updated.description == "Original desc"  # Unchanged
        assert updated.priority == "high"  # Updated

    def test_delete_task(self, temp_store_path):
        """Test deleting a task."""
        store = TaskStore(temp_store_path)
        task = store.create_task(title="Task to delete")

        result = store.delete_task(task.id)

        assert result is True
        assert store.get_task(task.id) is None

    def test_delete_nonexistent_task(self, temp_store_path):
        """Test deleting a nonexistent task."""
        store = TaskStore(temp_store_path)

        result = store.delete_task("T-NONEXISTENT")

        assert result is False

    def test_persistence_save_and_load(self, temp_store_path):
        """Test that tasks persist across store instances."""
        # Create store and add tasks
        store1 = TaskStore(temp_store_path)
        task1 = store1.create_task(title="Persistent task 1")
        task2 = store1.create_task(title="Persistent task 2", priority="high")

        # Create new store instance pointing to same file
        store2 = TaskStore(temp_store_path)

        assert len(store2.tasks) == 2
        assert store2.get_task(task1.id) is not None
        assert store2.get_task(task2.id) is not None
        assert store2.get_task(task2.id).priority == "high"

    def test_load_empty_file(self, temp_store_path):
        """Test loading from an empty file."""
        Path(temp_store_path).write_text("")

        store = TaskStore(temp_store_path)

        assert len(store.tasks) == 0

    def test_load_nonexistent_file(self):
        """Test loading from a nonexistent file."""
        store = TaskStore("/tmp/nonexistent_task_store_test.json")

        assert len(store.tasks) == 0

    def test_load_invalid_json(self, temp_store_path):
        """Test loading from invalid JSON file."""
        Path(temp_store_path).write_text("invalid json {{{")

        store = TaskStore(temp_store_path)

        # Should handle gracefully
        assert len(store.tasks) == 0

    def test_save_creates_parent_directory(self):
        """Test that save creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "path" / "tasks.json"

            store = TaskStore(str(nested_path))
            store.create_task(title="Test task")

            assert nested_path.exists()

    def test_update_task_updates_timestamp(self, temp_store_path):
        """Test that updating a task updates the 'updated' timestamp."""
        store = TaskStore(temp_store_path)
        task = store.create_task(title="Test")
        original_updated = task.updated

        import time
        time.sleep(0.01)  # Small delay to ensure timestamp changes

        updated = store.update_task(task.id, title="Updated")

        assert updated.updated > original_updated


class TestTaskStoreFilters:
    """Tests for TaskStore filtering combinations."""

    @pytest.fixture
    def populated_store(self):
        """Create a store with various tasks."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            filepath = f.name

        store = TaskStore(filepath)

        # Create diverse tasks
        store.create_task(title="Backend API", tags=["backend"], priority="high")
        store.create_task(title="Frontend UI", tags=["frontend"], priority="normal")
        store.create_task(title="Database migration", tags=["backend", "database"], priority="critical")
        store.create_task(title="Bug fix", tags=["bug"], priority="high")

        # Update some statuses
        tasks = store.list_tasks()
        store.update_task(tasks[0].id, status="in_progress")
        store.update_task(tasks[2].id, status="done")

        yield store

        Path(filepath).unlink(missing_ok=True)

    def test_combined_status_and_priority(self, populated_store):
        """Test filtering by both status and priority."""
        tasks = populated_store.list_tasks(status="todo", priority="high")

        assert len(tasks) == 1
        assert tasks[0].title == "Bug fix"

    def test_combined_status_and_tags(self, populated_store):
        """Test filtering by both status and tags."""
        tasks = populated_store.list_tasks(status="done", tags=["backend"])

        assert len(tasks) == 1
        assert tasks[0].title == "Database migration"

    def test_no_matching_tasks(self, populated_store):
        """Test filter that matches no tasks."""
        tasks = populated_store.list_tasks(status="blocked")

        assert len(tasks) == 0


class TestMCPTools:
    """Tests for MCP tool handlers."""

    @pytest.fixture(autouse=True)
    def setup_store(self):
        """Set up a clean store for each test."""
        # Clear existing tasks
        store.tasks.clear()
        yield
        # Clean up
        store.tasks.clear()

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test listing available tools."""
        tools = await list_tools()

        assert len(tools) > 0
        tool_names = [t.name for t in tools]

        assert "create_task" in tool_names
        assert "list_tasks" in tool_names
        assert "get_task" in tool_names
        assert "update_task" in tool_names
        assert "start_task" in tool_names
        assert "complete_task" in tool_names
        assert "block_task" in tool_names
        assert "delete_task" in tool_names
        assert "split_task" in tool_names
        assert "reorganize_tasks" in tool_names
        assert "analyze_task" in tool_names
        assert "analyze_backlog" in tool_names

    @pytest.mark.asyncio
    async def test_create_task_tool(self):
        """Test create_task tool handler."""
        result = await call_tool("create_task", {
            "title": "Test task",
            "description": "A test task",
            "priority": "high",
            "tags": ["test"],
        })

        assert len(result) == 1
        assert "Created task" in result[0].text
        assert "Test task" in result[0].text

    @pytest.mark.asyncio
    async def test_list_tasks_tool(self):
        """Test list_tasks tool handler."""
        # Create some tasks first
        store.create_task(title="Task 1")
        store.create_task(title="Task 2")

        result = await call_tool("list_tasks", {})

        assert len(result) == 1
        assert "Found 2 task(s)" in result[0].text
        assert "Task 1" in result[0].text
        assert "Task 2" in result[0].text

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self):
        """Test list_tasks with no tasks."""
        result = await call_tool("list_tasks", {})

        assert len(result) == 1
        assert "No tasks found" in result[0].text

    @pytest.mark.asyncio
    async def test_get_task_tool(self):
        """Test get_task tool handler."""
        task = store.create_task(title="Test task", description="Details")

        result = await call_tool("get_task", {"task_id": task.id})

        assert len(result) == 1
        assert task.id in result[0].text
        assert "Test task" in result[0].text

    @pytest.mark.asyncio
    async def test_get_task_not_found(self):
        """Test get_task with nonexistent task."""
        result = await call_tool("get_task", {"task_id": "T-NONEXISTENT"})

        assert len(result) == 1
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_update_task_tool(self):
        """Test update_task tool handler."""
        task = store.create_task(title="Original")

        result = await call_tool("update_task", {
            "task_id": task.id,
            "title": "Updated",
            "priority": "critical",
        })

        assert len(result) == 1
        assert "Updated task" in result[0].text
        assert "Updated" in result[0].text

    @pytest.mark.asyncio
    async def test_update_task_not_found(self):
        """Test update_task with nonexistent task."""
        result = await call_tool("update_task", {
            "task_id": "T-NONEXISTENT",
            "title": "New title",
        })

        assert len(result) == 1
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_start_task_tool(self):
        """Test start_task tool handler."""
        task = store.create_task(title="Task to start")

        result = await call_tool("start_task", {"task_id": task.id})

        assert len(result) == 1
        assert "Started task" in result[0].text

        # Verify status changed
        updated = store.get_task(task.id)
        assert updated.status == "in_progress"

    @pytest.mark.asyncio
    async def test_start_task_not_found(self):
        """Test start_task with nonexistent task."""
        result = await call_tool("start_task", {"task_id": "T-NONEXISTENT"})

        assert len(result) == 1
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_complete_task_tool(self):
        """Test complete_task tool handler."""
        task = store.create_task(title="Task to complete")

        result = await call_tool("complete_task", {"task_id": task.id})

        assert len(result) == 1
        assert "Completed task" in result[0].text

        # Verify status changed
        updated = store.get_task(task.id)
        assert updated.status == "done"

    @pytest.mark.asyncio
    async def test_complete_task_not_found(self):
        """Test complete_task with nonexistent task."""
        result = await call_tool("complete_task", {"task_id": "T-NONEXISTENT"})

        assert len(result) == 1
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_block_task_tool(self):
        """Test block_task tool handler."""
        task = store.create_task(title="Task to block")

        result = await call_tool("block_task", {
            "task_id": task.id,
            "reason": "Waiting for API key",
        })

        assert len(result) == 1
        assert "Blocked task" in result[0].text
        assert "Waiting for API key" in result[0].text

        # Verify status changed
        updated = store.get_task(task.id)
        assert updated.status == "blocked"

    @pytest.mark.asyncio
    async def test_block_task_not_found(self):
        """Test block_task with nonexistent task."""
        result = await call_tool("block_task", {"task_id": "T-NONEXISTENT"})

        assert len(result) == 1
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_delete_task_tool(self):
        """Test delete_task tool handler."""
        task = store.create_task(title="Task to delete")

        result = await call_tool("delete_task", {"task_id": task.id})

        assert len(result) == 1
        assert "Deleted task" in result[0].text

        # Verify task is gone
        assert store.get_task(task.id) is None

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self):
        """Test delete_task with nonexistent task."""
        result = await call_tool("delete_task", {"task_id": "T-NONEXISTENT"})

        assert len(result) == 1
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_split_task_tool(self):
        """Test split_task tool handler."""
        task = store.create_task(title="Complex task", tags=["backend"])

        result = await call_tool("split_task", {
            "task_id": task.id,
            "subtasks": [
                {"title": "Subtask 1", "description": "First part"},
                {"title": "Subtask 2", "description": "Second part"},
            ],
        })

        assert len(result) == 1
        assert "Split task" in result[0].text
        assert "2 subtasks" in result[0].text
        assert "Subtask 1" in result[0].text
        assert "Subtask 2" in result[0].text

    @pytest.mark.asyncio
    async def test_split_task_not_found(self):
        """Test split_task with nonexistent task."""
        result = await call_tool("split_task", {
            "task_id": "T-NONEXISTENT",
            "subtasks": [{"title": "Subtask"}],
        })

        assert len(result) == 1
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_reorganize_tasks_tool(self):
        """Test reorganize_tasks tool handler."""
        task1 = store.create_task(title="Task 1")
        task2 = store.create_task(title="Task 2")

        result = await call_tool("reorganize_tasks", {
            "updates": [
                {"task_id": task1.id, "priority": "high", "order": 1},
                {"task_id": task2.id, "priority": "low", "order": 2},
            ],
        })

        assert len(result) == 1
        assert "Reorganized 2 task(s)" in result[0].text

        # Verify updates
        assert store.get_task(task1.id).priority == "high"
        assert store.get_task(task2.id).priority == "low"

    @pytest.mark.asyncio
    async def test_reorganize_tasks_partial_not_found(self):
        """Test reorganize_tasks with some nonexistent tasks."""
        task = store.create_task(title="Task 1")

        result = await call_tool("reorganize_tasks", {
            "updates": [
                {"task_id": task.id, "priority": "high"},
                {"task_id": "T-NONEXISTENT", "priority": "low"},
            ],
        })

        assert len(result) == 1
        assert "not found" in result[0].text

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """Test calling an unknown tool."""
        result = await call_tool("unknown_tool", {})

        assert len(result) == 1
        assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Test that tool errors are handled gracefully."""
        # This should trigger an error due to missing required field
        result = await call_tool("create_task", {})  # Missing 'title'

        assert len(result) == 1
        assert "Error" in result[0].text
