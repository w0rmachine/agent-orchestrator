"""Unit tests for task API handlers (without TestClient)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from backend.api import tasks as tasks_api
from backend.models.task import TaskStatus


@pytest.mark.asyncio
async def test_create_and_list_tasks(session: Session, monkeypatch):
    async def _noop_sync() -> None:
        return None

    monkeypatch.setattr(tasks_api, "_sync_markdown", _noop_sync)

    created = await tasks_api.create_task(
        tasks_api.TaskCreate(
            task_code="TASK-001",
            title="Implement parser",
            description="Parse markdown into DB model",
            status=TaskStatus.RADAR,
            tags=["backend", "parser"],
            phase="analyze",
            due_date="2026-03-31",
            repo_path="/home/mwu/Work/projects/agent-orchestrator",
        ),
        session,
    )

    assert created.task_code == "TASK-001"
    assert created.status == TaskStatus.RADAR
    assert created.phase == "analyze"
    assert created.due_date == "2026-03-31"

    listed = tasks_api.list_tasks(
        session,
        status=None,
        environment_id=None,
        parent_task_id=None,
    )
    assert len(listed) == 1
    assert listed[0].task_code == "TASK-001"


@pytest.mark.asyncio
async def test_reserved_role_tags_are_removed_on_create_and_update(session: Session, monkeypatch):
    async def _noop_sync() -> None:
        return None

    monkeypatch.setattr(tasks_api, "_sync_markdown", _noop_sync)

    created = await tasks_api.create_task(
        tasks_api.TaskCreate(
            task_code="TASK-ROLE-001",
            title="Role tag scrub",
            status=TaskStatus.RADAR,
            tags=["backend", "manager", "coder", "analyzer"],
            phase="backlog",
        ),
        session,
    )

    assert created.tags == ["backend"]
    assert created.phase == "backlog"

    updated = await tasks_api.update_task(
        created.id,
        tasks_api.TaskUpdate(
            tags=["manager", "frontend", "analyzer"],
            phase="active",
        ),
        session,
    )

    assert updated.tags == ["frontend"]
    assert updated.phase == "active"


@pytest.mark.asyncio
async def test_get_update_move_and_delete_task(session: Session, monkeypatch):
    async def _noop_sync() -> None:
        return None

    monkeypatch.setattr(tasks_api, "_sync_markdown", _noop_sync)

    created = await tasks_api.create_task(
        tasks_api.TaskCreate(task_code="TASK-002", title="Original", status=TaskStatus.RADAR),
        session,
    )

    fetched = tasks_api.get_task(created.id, session)
    assert fetched.task_code == "TASK-002"

    updated = await tasks_api.update_task(
        created.id,
        tasks_api.TaskUpdate(
            title="Updated",
            status=TaskStatus.RUNWAY,
            phase="active",
            due_date="2026-04-15",
        ),
        session,
    )
    assert updated.title == "Updated"
    assert updated.status == TaskStatus.RUNWAY
    assert updated.phase == "active"

    moved = await tasks_api.move_task(created.id, TaskStatus.DONE, session)
    assert moved.status == TaskStatus.DONE
    assert moved.completed_at is not None

    await tasks_api.delete_task(created.id, session)

    with pytest.raises(HTTPException) as error:
        tasks_api.get_task(created.id, session)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_task_code_is_rejected(session: Session, monkeypatch):
    async def _noop_sync() -> None:
        return None

    monkeypatch.setattr(tasks_api, "_sync_markdown", _noop_sync)

    await tasks_api.create_task(
        tasks_api.TaskCreate(task_code="TASK-003", title="First", status=TaskStatus.RADAR),
        session,
    )

    with pytest.raises(HTTPException) as error:
        await tasks_api.create_task(
            tasks_api.TaskCreate(task_code="TASK-003", title="Duplicate", status=TaskStatus.RADAR),
            session,
        )

    assert error.value.status_code == 400
    assert "already exists" in error.value.detail


def test_list_tasks_with_status_filter(session: Session):
    task_one = tasks_api.TaskCreate(task_code="TASK-004", title="A", status=TaskStatus.RADAR)
    task_two = tasks_api.TaskCreate(task_code="TASK-005", title="B", status=TaskStatus.DONE)

    session.add(
        tasks_api.Task(
            task_code=task_one.task_code,
            title=task_one.title,
            status=task_one.status,
            description="",
        )
    )
    session.add(
        tasks_api.Task(
            task_code=task_two.task_code,
            title=task_two.title,
            status=task_two.status,
            description="",
        )
    )
    session.commit()

    radar_tasks = tasks_api.list_tasks(
        session,
        status=TaskStatus.RADAR,
        environment_id=None,
        parent_task_id=None,
    )
    done_tasks = tasks_api.list_tasks(
        session,
        status=TaskStatus.DONE,
        environment_id=None,
        parent_task_id=None,
    )

    assert [task.task_code for task in radar_tasks] == ["TASK-004"]
    assert [task.task_code for task in done_tasks] == ["TASK-005"]
