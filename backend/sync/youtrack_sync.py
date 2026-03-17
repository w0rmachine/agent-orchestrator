"""YouTrack read-only sync into the local task database."""

from __future__ import annotations

from typing import Iterable

from sqlmodel import Session, select

from backend.config import ProjectConfig
from backend.database import engine
from backend.integrations.youtrack import fetch_issues, normalize_issue
from backend.models.task import Task, TaskStatus


async def sync_youtrack_project(project: ProjectConfig) -> int:
    """Fetch YouTrack issues and upsert into the local DB."""
    yt = project.youtrack
    if not yt.url:
        return 0

    token = yt.resolve_token()
    if not token:
        print(f"YouTrack token missing for project {project.name}")
        return 0

    query = yt.query.strip()
    if not query:
        if yt.project_key:
            query = f"project: {yt.project_key} for: me #Unresolved"
        else:
            query = "for: me #Unresolved"

    issues = await fetch_issues(yt.url, token, query)
    normalized = [
        normalize_issue(issue, yt.url, yt.project_key) for issue in issues
    ]
    seen_ids = {item["external_id"] for item in normalized if item["external_id"]}

    with Session(engine) as session:
        existing = session.exec(
            select(Task).where(
                Task.source == "youtrack",
                Task.external_project == yt.project_key,
            )
        ).all()
        existing_by_external = {
            t.external_id: t for t in existing if t.external_id
        }

        updated_count = 0

        for item in normalized:
            if not item["external_id"]:
                continue
            task = existing_by_external.get(item["external_id"])
            if task is None:
                task = session.exec(
                    select(Task).where(Task.task_code == item["task_code"])
                ).first()

            if task is None:
                task = Task(
                    task_code=item["task_code"],
                    title=item["title"],
                    description=item["description"],
                    status=_map_status_enum(item["status"]),
                    priority=item["priority"],
                    tags=[],
                    order=0,
                    source="youtrack",
                    external_id=item["external_id"],
                    external_url=item["external_url"],
                    external_project=item["external_project"],
                    external_updated_at=item["external_updated_at"],
                    external_deleted=False,
                )
                session.add(task)
                updated_count += 1
                continue

            task.title = item["title"]
            task.description = item["description"]
            task.status = _map_status_enum(item["status"])
            if item["priority"] is not None:
                task.priority = item["priority"]
            task.source = "youtrack"
            task.external_id = item["external_id"]
            task.external_url = item["external_url"]
            task.external_project = item["external_project"]
            task.external_updated_at = item["external_updated_at"]
            task.external_deleted = False
            session.add(task)
            updated_count += 1

        if existing:
            _mark_missing_as_done(session, existing, seen_ids)

        session.commit()
        return updated_count


def _mark_missing_as_done(
    session: Session, existing: Iterable[Task], seen_ids: set[str]
) -> None:
    for task in existing:
        if task.external_id and task.external_id in seen_ids:
            continue
        if task.status != TaskStatus.DONE:
            task.status = TaskStatus.DONE
        task.external_deleted = True
        session.add(task)


def _map_status_enum(value: str) -> TaskStatus:
    mapping = {
        "runway": TaskStatus.RUNWAY,
        "flight": TaskStatus.FLIGHT,
        "blocked": TaskStatus.BLOCKED,
        "done": TaskStatus.DONE,
    }
    return mapping.get(value, TaskStatus.RUNWAY)
