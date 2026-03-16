"""Tests for MCP server (DB-backed task store)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

import backend.models  # Ensure all SQLModel tables are registered
from backend.mcp_server import Task, TaskStore, call_tool, list_tools
from backend.models.task import Task as DBTask


@pytest.fixture
def mcp_test_db(monkeypatch):
    """Provide isolated in-memory DB and disable markdown side effects."""
    from backend import mcp_server

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    async def _noop_sync() -> None:
        return None

    monkeypatch.setattr(mcp_server, "engine", engine)
    monkeypatch.setattr(mcp_server, "_sync_markdown", _noop_sync)

    return engine


class TestTaskModel:
    def test_defaults(self):
        task = Task(title="Test")

        assert task.id.startswith("T-")
        assert task.status == "todo"
        assert task.priority == "normal"
        assert task.tags == []
        assert task.context == {}
        assert isinstance(task.created, datetime)
        assert isinstance(task.updated, datetime)


class TestTaskStore:
    def test_create_and_get_task_by_code_and_uuid(self, mcp_test_db):
        store = TaskStore()
        created = store.create_task(
            title="Implement endpoint",
            description="Add /health check",
            priority="high",
            tags=["backend", "api"],
            context={"phase": "analyze", "due_date": "2026-03-20", "repo_path": "/repo"},
        )

        assert created.id.startswith("MCP-")
        assert created.status == "todo"
        assert created.priority == "high"
        assert created.phase == "analyze"
        assert created.due_date == "2026-03-20"
        assert created.repo_path == "/repo"

        by_code = store.get_task(created.id)
        assert by_code is not None
        assert by_code.title == "Implement endpoint"

        with Session(mcp_test_db) as session:
            row = session.exec(select(DBTask).where(DBTask.task_code == created.id)).first()
            assert row is not None
            by_uuid = store.get_task(str(row.id))

        assert by_uuid is not None
        assert by_uuid.id == created.id

    def test_list_and_filters(self, mcp_test_db):
        store = TaskStore()
        first = store.create_task(
            title="Analyze bug",
            priority="critical",
            tags=["bug", "backend"],
            context={"phase": "analyze"},
        )
        second = store.create_task(
            title="Implement fix",
            priority="normal",
            tags=["backend"],
            context={"phase": "active"},
        )
        third = store.create_task(
            title="Release",
            priority="low",
            tags=["ops"],
            context={"phase": "deploy"},
        )

        store.update_task(second.id, status="in_progress")
        store.update_task(third.id, status="done")

        assert len(store.list_tasks()) == 3
        assert [task.id for task in store.list_tasks(status="todo")] == [first.id]
        assert [task.id for task in store.list_tasks(status="in_progress")] == [second.id]
        assert [task.id for task in store.list_tasks(status="done")] == [third.id]
        assert [task.id for task in store.list_tasks(priority="critical")] == [first.id]
        assert {task.id for task in store.list_tasks(tags=["backend"])} == {first.id, second.id}
        assert [task.id for task in store.list_tasks(phase="active")] == [second.id]

    def test_update_and_delete(self, mcp_test_db):
        store = TaskStore()
        created = store.create_task(title="Refactor parser", tags=["techdebt"])

        updated = store.update_task(
            created.id,
            title="Refactor parser module",
            description="Make parser incremental",
            status="blocked",
            priority="critical",
            tags=["backend", "techdebt"],
            context={"phase": "blocked", "due_date": "2026-04-01", "repo_path": "/mono"},
        )

        assert updated is not None
        assert updated.title == "Refactor parser module"
        assert updated.status == "blocked"
        assert updated.priority == "critical"
        assert updated.phase == "blocked"
        assert updated.due_date == "2026-04-01"
        assert updated.repo_path == "/mono"

        assert store.delete_task(created.id) is True
        assert store.get_task(created.id) is None
        assert store.delete_task(created.id) is False

    def test_reserved_role_tags_removed_on_create_and_update(self, mcp_test_db):
        store = TaskStore()
        created = store.create_task(
            title="Sanitize role tags",
            tags=["backend", "manager", "coder", "analyzer"],
            context={"phase": "analyze"},
        )

        assert created.tags == ["backend"]
        assert created.phase == "analyze"

        updated = store.update_task(
            created.id,
            tags=["manager", "qa", "analyzer"],
            context={"phase": "testing"},
        )

        assert updated is not None
        assert updated.tags == ["qa"]
        assert updated.phase == "testing"


class TestMcpTools:
    @pytest.mark.asyncio
    async def test_list_tools_contains_expected_tools(self, mcp_test_db):
        tools = await list_tools()
        names = {tool.name for tool in tools}

        assert "create_task" in names
        assert "list_tasks" in names
        assert "get_task" in names
        assert "update_task" in names
        assert "start_task" in names
        assert "complete_task" in names
        assert "block_task" in names
        assert "delete_task" in names
        assert "split_task" in names
        assert "reorganize_tasks" in names

    @pytest.mark.asyncio
    async def test_create_list_get_update_delete_flow(self, mcp_test_db):
        created_response = await call_tool(
            "create_task",
            {
                "title": "Wire MCP",
                "description": "Integrate tooling",
                "priority": "high",
                "tags": ["mcp", "backend"],
                "context": {
                    "phase": "analyze",
                    "due_date": "2026-03-31",
                    "repo_path": "/home/mwu/Work/projects/agent-orchestrator",
                },
            },
        )
        create_text = created_response[0].text
        assert "Created task" in create_text

        created_id = create_text.split("Created task ", 1)[1].split(":", 1)[0].strip()
        assert created_id.startswith("MCP-")

        listed = await call_tool("list_tasks", {"phase": "analyze"})
        assert f"[{created_id}] Wire MCP" in listed[0].text

        task_details = await call_tool("get_task", {"task_id": created_id})
        assert f"Task {created_id}" in task_details[0].text
        assert '"phase": "analyze"' in task_details[0].text

        updated = await call_tool(
            "update_task",
            {
                "task_id": created_id,
                "status": "in_progress",
                "priority": "critical",
                "context": {"phase": "active"},
            },
        )
        assert f"Updated task {created_id}" in updated[0].text

        deleted = await call_tool("delete_task", {"task_id": created_id})
        assert f"Deleted task {created_id}" in deleted[0].text

        missing = await call_tool("get_task", {"task_id": created_id})
        assert "not found" in missing[0].text

    @pytest.mark.asyncio
    async def test_status_helper_tools_and_filters(self, mcp_test_db):
        created_response = await call_tool("create_task", {"title": "Helper flow"})
        created_id = created_response[0].text.split("Created task ", 1)[1].split(":", 1)[0].strip()

        started = await call_tool("start_task", {"task_id": created_id})
        assert "Started task" in started[0].text

        in_progress = await call_tool("list_tasks", {"status": "in_progress"})
        assert created_id in in_progress[0].text

        completed = await call_tool("complete_task", {"task_id": created_id})
        assert "Completed task" in completed[0].text

        done = await call_tool("list_tasks", {"status": "done"})
        assert created_id in done[0].text

        blocked_missing = await call_tool("block_task", {"task_id": "MCP-9999", "reason": "waiting"})
        assert "not found" in blocked_missing[0].text

    @pytest.mark.asyncio
    async def test_split_reorganize_unknown_and_empty_paths(self, mcp_test_db):
        parent_response = await call_tool("create_task", {"title": "Parent", "tags": ["planning"]})
        parent_id = parent_response[0].text.split("Created task ", 1)[1].split(":", 1)[0].strip()

        split = await call_tool(
            "split_task",
            {
                "task_id": parent_id,
                "subtasks": [
                    {"title": "Child one", "priority": "high"},
                    {"title": "Child two"},
                ],
            },
        )
        assert "into 2 subtasks" in split[0].text

        todo_list = await call_tool("list_tasks", {"status": "todo"})
        assert "Child one" in todo_list[0].text
        assert "Child two" in todo_list[0].text

        reorganize = await call_tool(
            "reorganize_tasks",
            {
                "updates": [
                    {"task_id": parent_id, "priority": "critical", "tags": ["planning", "top"]},
                    {"task_id": "MCP-4040", "priority": "low"},
                ]
            },
        )
        assert "Updated" in reorganize[0].text
        assert "not found" in reorganize[0].text

        unknown = await call_tool("does_not_exist", {})
        assert "Unknown tool" in unknown[0].text

        empty = await call_tool("list_tasks", {"tags": ["tag-that-does-not-exist"]})
        assert "No tasks found." in empty[0].text

    @pytest.mark.asyncio
    async def test_analysis_tools_safe_paths(self, mcp_test_db):
        analyze_missing = await call_tool("analyze_task", {"task_id": "MCP-0000"})
        assert "not found" in analyze_missing[0].text

        backlog_empty = await call_tool("analyze_backlog", {})
        assert "No tasks to analyze." in backlog_empty[0].text
