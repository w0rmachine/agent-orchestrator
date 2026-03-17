"""YouTrack API client helpers (read-only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx


def _extract_custom_field(
    issue: dict[str, Any], *names: str, default: str | None = None
) -> str | None:
    fields = issue.get("customFields") or []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = field.get("name")
        if not name:
            continue
        if name not in names:
            continue
        value = field.get("value")
        if isinstance(value, dict):
            for key in ("localizedName", "name"):
                if value.get(key):
                    return str(value[key])
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("name"):
                    return str(item["name"])
        if isinstance(value, str):
            return value
    return default


def _map_status(value: str | None) -> str:
    if not value:
        return "runway"
    normalized = value.strip().lower()
    if normalized in {"done", "fixed", "resolved", "closed", "complete", "completed"}:
        return "done"
    if normalized in {"blocked", "waiting", "on hold"}:
        return "blocked"
    if normalized in {"in progress", "doing", "active", "development"}:
        return "flight"
    return "runway"


def _map_priority(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"critical", "blocker", "urgent"}:
        return 1
    if normalized in {"high", "major"}:
        return 2
    if normalized in {"normal", "medium"}:
        return 3
    if normalized in {"low", "minor"}:
        return 5
    return None


def _to_datetime(millis: int | None) -> datetime | None:
    if not millis:
        return None
    return datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc)


async def fetch_issues(
    base_url: str,
    token: str,
    query: str,
) -> list[dict[str, Any]]:
    base = base_url.rstrip("/")
    url = f"{base}/api/issues"
    fields = (
        "idReadable,summary,description,updated,created,resolved,"
        "customFields(name,value(name,localizedName))"
    )
    params = {"fields": fields, "query": query}
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json() or []


def normalize_issue(
    issue: dict[str, Any],
    base_url: str,
    project_key: str,
) -> dict[str, Any]:
    issue_id = (issue.get("idReadable") or "").upper()
    summary = issue.get("summary") or ""
    description = issue.get("description") or ""
    status = _map_status(_extract_custom_field(issue, "State", "Status"))
    priority = _map_priority(_extract_custom_field(issue, "Priority"))
    updated_at = _to_datetime(issue.get("updated"))
    external_url = f"{base_url.rstrip('/')}/issue/{issue_id}" if issue_id else None

    return {
        "task_code": issue_id,
        "external_id": issue_id,
        "title": summary,
        "description": description,
        "status": status,
        "priority": priority,
        "external_url": external_url,
        "external_project": project_key,
        "external_updated_at": updated_at,
    }
