"""
Radar·Runway — ADHD-friendly task manager with FastAPI + HTMX + Obsidian sync.

Architecture:
  - Radar: Unmanaged backlog for rapid task capture
  - Runway: AI-analyzed managed tasks (todo, in_progress, done)
  - Obsidian: Bidirectional markdown sync (headers = columns)
  - MCP Server: External tool integration
  - HTMX: Server-rendered HTML partials (no React)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field


# ── Config ────────────────────────────────────────────────────────────────────
@dataclass
class Config:
    obsidian_todo_path: str = "~/Documents/notes/Work/TODO.md"
    simulate: bool = True
    anthropic_api_key: str = ""


def _load_simple_yaml(path: str) -> dict[str, str]:
    data: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return data
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        data[key.strip()] = val.strip().strip("'").strip('"')
    return data


def load_config() -> Config:
    cfg = Config()
    data = _load_simple_yaml("config.yaml")
    if "obsidian_todo_path" in data:
        cfg.obsidian_todo_path = data["obsidian_todo_path"]
    if "simulate" in data:
        cfg.simulate = data["simulate"].lower() in ("1", "true", "yes", "y", "on")
    if "anthropic_api_key" in data:
        cfg.anthropic_api_key = data["anthropic_api_key"]
    cfg.obsidian_todo_path = os.path.expanduser(cfg.obsidian_todo_path)
    return cfg


cfg = load_config()


# ── Types ─────────────────────────────────────────────────────────────────────
TaskLocation = Literal["radar", "runway"]
TaskStatus = Literal["todo", "in_progress", "done"]
TaskSource = Literal["obsidian", "manual"]


# ── Models ────────────────────────────────────────────────────────────────────
class Task(BaseModel):
    """Core task model for Radar·Runway."""

    id: str
    title: str
    description: str = ""
    tags: list[str] = []

    # Radar vs Runway
    location: TaskLocation = "radar"

    # Runway states (only when location == "runway")
    status: TaskStatus = "todo"

    # AI-analyzed fields (populated when promoted to runway)
    priority: int | None = None  # 0-4 (0=critical, 4=backlog)
    complexity: int | None = None  # 1-13 (fibonacci story points)
    estimated_minutes: int | None = None  # AI time estimate
    ai_notes: str = ""  # Why this priority/complexity?

    # Metadata
    source: TaskSource = "obsidian"
    external_id: str | None = None
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    order: int = 0  # Preserves position in markdown
    details: list[str] = []  # Indented lines below task


class TaskUpdate(BaseModel):
    """Partial task update."""

    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    location: TaskLocation | None = None
    status: TaskStatus | None = None
    priority: int | None = None
    complexity: int | None = None
    estimated_minutes: int | None = None
    ai_notes: str | None = None


class LogEntry(BaseModel):
    """Log entry for debugging."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    level: Literal["DEBUG", "INFO", "WARN", "ERROR"] = "INFO"
    message: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Store ─────────────────────────────────────────────────────────────────────
class Store:
    """In-memory task store (easily swappable for SQLite/Postgres)."""

    def __init__(self):
        self.tasks: dict[str, Task] = {}
        self.logs: list[LogEntry] = []
        self.next_obsidian_id: int = 1
        self.obsidian_template: ObsidianTemplate | None = None

    def add_log(self, message: str, level: str = "INFO") -> LogEntry:
        entry = LogEntry(message=message, level=level)
        self.logs.append(entry)
        self.logs = self.logs[-2000:]
        return entry


store = Store()


# ── WebSocket manager ─────────────────────────────────────────────────────────
class WsManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, payload: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


ws_mgr = WsManager()


# ── Obsidian Markdown parsing ─────────────────────────────────────────────────
TASK_RE = re.compile(r"^- \[( |x|X)\] (.+)$")
ID_RE = re.compile(r"\b(YT-\d+|O-\d+)\b")

# Map markdown headers to task location/status
HEADER_TO_LOCATION_STATUS = {
    "radar": ("radar", None),
    "todo": ("runway", "todo"),
    "in progress": ("runway", "in_progress"),
    "done": ("runway", "done"),
}


def _normalize_header(h: str) -> str:
    return h.strip().lower()


@dataclass
class ObsidianSection:
    header: str
    lines: list[str]


@dataclass
class ObsidianTemplate:
    preamble: list[str]
    sections: list[ObsidianSection]
    tail: list[str]


def _extract_id_and_title(text: str) -> tuple[str | None, str]:
    match = ID_RE.search(text)
    if not match:
        return None, text.strip()
    tid = match.group(1)
    cleaned = re.sub(rf"\[?\b{re.escape(tid)}\b\]?", "", text).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return tid, cleaned


def _assign_obsidian_id() -> str:
    tid = f"O-{store.next_obsidian_id:03d}"
    store.next_obsidian_id += 1
    return tid


def _split_settings(lines: list[str]) -> tuple[list[str], list[str]]:
    for idx, line in enumerate(lines):
        if line.strip().startswith("%% kanban:settings"):
            return lines[:idx], lines[idx:]
    return lines, []


def _parse_todo_file(path: str) -> tuple[list[Task], ObsidianTemplate, bool]:
    """Parse Obsidian markdown file into tasks."""
    p = Path(path)
    if not p.exists():
        return [], ObsidianTemplate([], [], []), False

    lines = p.read_text(encoding="utf-8").splitlines()
    preamble: list[str] = []
    sections: list[ObsidianSection] = []
    tail: list[str] = []

    current: ObsidianSection | None = None
    for line in lines:
        if line.startswith("## "):
            header = line[3:].strip()
            current = ObsidianSection(header=header, lines=[])
            sections.append(current)
            continue
        if current is None:
            preamble.append(line)
        else:
            current.lines.append(line)

    if not sections:
        tail = preamble
        preamble = []

    tasks: list[Task] = []
    dirty = False
    order_counter = 0
    max_obsidian = 0

    for section in sections:
        normalized = _normalize_header(section.header)
        location_status = HEADER_TO_LOCATION_STATUS.get(normalized)
        if not location_status:
            continue

        location, status = location_status

        if section is sections[-1]:
            kept, tail_lines = _split_settings(section.lines)
            section.lines = kept
            tail = tail_lines

        i = 0
        while i < len(section.lines):
            line = section.lines[i]
            match = TASK_RE.match(line)
            if not match:
                i += 1
                continue

            is_done = match.group(1) in ("x", "X")
            text = match.group(2).strip()
            tid, title = _extract_id_and_title(text)

            if tid and tid.startswith("O-"):
                try:
                    max_obsidian = max(max_obsidian, int(tid.split("-", 1)[1]))
                except ValueError:
                    pass

            if not tid:
                tid = _assign_obsidian_id()
                dirty = True

            # Extract details (indented lines)
            details: list[str] = []
            j = i + 1
            while j < len(section.lines):
                nxt = section.lines[j]
                if nxt.startswith("## ") or TASK_RE.match(nxt):
                    break
                if nxt.startswith(" ") or nxt.startswith("\t"):
                    details.append(nxt)
                    j += 1
                    continue
                break

            # Parse AI fields from details if in runway
            priority = None
            complexity = None
            estimated_minutes = None
            ai_notes = ""

            if location == "runway":
                for detail in details:
                    if "priority:" in detail.lower():
                        try:
                            priority = int(
                                re.search(r"priority:\s*(\d)", detail, re.IGNORECASE).group(1)
                            )
                        except (AttributeError, ValueError):
                            pass
                    if "complexity:" in detail.lower():
                        try:
                            complexity = int(
                                re.search(r"complexity:\s*(\d+)", detail, re.IGNORECASE).group(1)
                            )
                        except (AttributeError, ValueError):
                            pass
                    if "est:" in detail.lower() or "estimated:" in detail.lower():
                        try:
                            estimated_minutes = int(
                                re.search(r"(?:est|estimated):\s*(\d+)", detail, re.IGNORECASE).group(
                                    1
                                )
                            )
                        except (AttributeError, ValueError):
                            pass
                    if "ai:" in detail.lower():
                        ai_notes = detail.split(":", 1)[1].strip() if ":" in detail else ""

            order_counter += 1
            source: TaskSource = "obsidian"
            task = Task(
                id=tid,
                source=source,
                external_id=None,
                title=title,
                location=location,  # type: ignore
                status=status or "todo",  # type: ignore
                order=order_counter,
                details=details,
                priority=priority,
                complexity=complexity,
                estimated_minutes=estimated_minutes,
                ai_notes=ai_notes,
            )
            tasks.append(task)
            i = max(j, i + 1)

    if max_obsidian >= store.next_obsidian_id:
        store.next_obsidian_id = max_obsidian + 1

    return tasks, ObsidianTemplate(preamble, sections, tail), dirty


def _render_task_line(task: Task) -> list[str]:
    """Render a task as markdown lines."""
    checked = "x" if task.status == "done" else " "
    title = task.title.strip()
    tags_str = " ".join(task.tags) if task.tags else ""
    tags_suffix = f" {tags_str}" if tags_str else ""

    line = f"- [{checked}] [{task.id}] {title}{tags_suffix}".rstrip()
    lines = [line]

    # Add AI analysis details for runway tasks
    if task.location == "runway":
        if task.priority is not None:
            priority_names = {
                0: "Critical",
                1: "High",
                2: "Medium",
                3: "Low",
                4: "Backlog",
            }
            lines.append(f"  Priority: P{task.priority} ({priority_names.get(task.priority, '?')})")
        if task.complexity is not None:
            lines.append(f"  Complexity: {task.complexity} points")
        if task.estimated_minutes is not None:
            hours = task.estimated_minutes // 60
            mins = task.estimated_minutes % 60
            time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
            lines.append(f"  Est: {time_str}")
        if task.ai_notes:
            lines.append(f"  AI: {task.ai_notes}")

    lines.extend(task.details)
    return lines


def _write_todo_file(path: str, template: ObsidianTemplate, tasks: list[Task]) -> None:
    """Write tasks back to Obsidian markdown file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.extend(template.preamble)

    tasks_by_location_status: dict[tuple[str, str | None], list[Task]] = {}
    for t in tasks:
        key = (t.location, t.status if t.location == "runway" else None)
        tasks_by_location_status.setdefault(key, []).append(t)

    for task_list in tasks_by_location_status.values():
        task_list.sort(key=lambda t: t.order)

    for section in template.sections:
        lines.append(f"## {section.header}")
        normalized = _normalize_header(section.header)
        location_status = HEADER_TO_LOCATION_STATUS.get(normalized)

        if not location_status:
            lines.extend(section.lines)
            continue

        location, status = location_status
        key = (location, status)
        for task in tasks_by_location_status.get(key, []):
            lines.extend(_render_task_line(task))
        lines.append("")

    if template.tail:
        lines.extend(template.tail)

    p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


async def sync_from_obsidian() -> int:
    """Sync tasks from Obsidian markdown file."""
    tasks, template, dirty = _parse_todo_file(cfg.obsidian_todo_path)
    store.obsidian_template = template
    seen = {t.id for t in tasks}

    added = 0
    for t in tasks:
        if t.id in store.tasks:
            existing = store.tasks[t.id]
            existing.title = t.title
            existing.location = t.location
            existing.status = t.status
            existing.details = t.details
            existing.order = t.order
            existing.priority = t.priority
            existing.complexity = t.complexity
            existing.estimated_minutes = t.estimated_minutes
            existing.ai_notes = t.ai_notes
            existing.updated = datetime.now(timezone.utc)
        else:
            store.tasks[t.id] = t
            added += 1

    # Remove tasks that were deleted from the file
    for tid in list(store.tasks.keys()):
        t = store.tasks[tid]
        if t.source == "obsidian" and tid not in seen:
            store.tasks.pop(tid)

    if dirty:
        _write_todo_file(cfg.obsidian_todo_path, template, list(store.tasks.values()))

    if added:
        await ws_mgr.broadcast({"type": "sync_complete", "added": added})

    return added


async def persist_obsidian() -> None:
    """Write tasks back to Obsidian file."""
    if not store.obsidian_template:
        return
    _write_todo_file(cfg.obsidian_todo_path, store.obsidian_template, list(store.tasks.values()))


async def analyze_task_with_ai(task_id: str) -> Task:
    """Analyze a single task with Claude API (if not simulating)."""
    task = store.tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    if cfg.simulate:
        # Simulate AI analysis
        priority_map = {"#critical": 0, "#urgent": 0, "#fasttask": 4, "#backlog": 4}
        priority = next((priority_map[t] for t in task.tags if t in priority_map), 2)

        complexity_map = {
            "#physical": 5,
            "#fasttask": 1,
            "#laptop": 3,
        }
        complexity = next((complexity_map[t] for t in task.tags if t in complexity_map), 3)

        time_map = {"#fasttask": 30, "#physical": 60}
        estimated_minutes = next((time_map[t] for t in task.tags if t in time_map), 120)

        task.priority = priority
        task.complexity = complexity
        task.estimated_minutes = estimated_minutes
        task.ai_notes = f"Simulated analysis based on tags: {', '.join(task.tags)}"
    else:
        # Call Claude API (stub for now)
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=cfg.anthropic_api_key)
            prompt = f"""Analyze this task for an ADHD-friendly workflow:

Title: {task.title}
Description: {task.description}
Tags: {', '.join(task.tags)}

Provide JSON with:
1. priority (0-4): 0=critical, 1=high, 2=medium, 3=low, 4=backlog
2. complexity (1-13): fibonacci story points
3. estimated_minutes: your best time guess
4. reasoning: brief explanation

Return ONLY valid JSON."""

            response = client.messages.create(
                model="claude-opus-4-5-20251101",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )

            result = json.loads(response.content[0].text)
            task.priority = result.get("priority", 2)
            task.complexity = result.get("complexity", 3)
            task.estimated_minutes = result.get("estimated_minutes", 120)
            task.ai_notes = result.get("reasoning", "")
        except Exception as e:
            store.add_log(f"AI analysis failed: {e}", level="ERROR")
            # Fall back to simulation
            task.priority = 2
            task.complexity = 3
            task.estimated_minutes = 120
            task.ai_notes = "Analysis failed, using defaults"

    task.location = "runway"
    task.status = "todo"
    task.updated = datetime.now(timezone.utc)
    return task


# ── Logging helpers ───────────────────────────────────────────────────────────
def emit_log(message: str, level: str = "INFO"):
    entry = store.add_log(message, level=level)
    asyncio.create_task(ws_mgr.broadcast({"type": "log", "log": entry.model_dump(mode="json")}))


# ── Jinja2 template setup ─────────────────────────────────────────────────────
template_dir = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)


# ── FastAPI app ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await sync_from_obsidian()
    yield


app = FastAPI(title="Radar·Runway", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if they exist
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ── Routes: Main UI ────────────────────────────────────────────────────────────
@app.get("/")
async def index():
    """Main kanban view."""
    template = jinja_env.get_template("kanban.html")
    radar_tasks = [t for t in store.tasks.values() if t.location == "radar"]
    todo_tasks = [t for t in store.tasks.values() if t.location == "runway" and t.status == "todo"]
    in_progress_tasks = [
        t for t in store.tasks.values() if t.location == "runway" and t.status == "in_progress"
    ]
    done_tasks = [t for t in store.tasks.values() if t.location == "runway" and t.status == "done"]

    context = {
        "radar_tasks": sorted(radar_tasks, key=lambda t: t.order),
        "todo_tasks": sorted(todo_tasks, key=lambda t: t.order),
        "in_progress_tasks": sorted(in_progress_tasks, key=lambda t: t.order),
        "done_tasks": sorted(done_tasks, key=lambda t: t.order),
    }
    return template.render(**context)


# ── Routes: Tasks (HTMX API) ──────────────────────────────────────────────────
@app.get("/tasks", response_model=list[Task])
def list_tasks(location: TaskLocation | None = None, status: TaskStatus | None = None):
    """List tasks (JSON API)."""
    out = list(store.tasks.values())
    if location:
        out = [t for t in out if t.location == location]
    if status:
        out = [t for t in out if t.status == status]
    return sorted(out, key=lambda t: t.order)


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str):
    """Get a single task."""
    t = store.tasks.get(task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    return t


@app.post("/tasks", response_model=Task)
async def create_task(data: dict[str, Any]):
    """Create a new task in Radar."""
    title = data.get("title", "Untitled")
    description = data.get("description", "")
    tags = data.get("tags", [])

    # Auto-assign ID
    task_id = f"O-{store.next_obsidian_id:03d}"
    store.next_obsidian_id += 1

    task = Task(
        id=task_id,
        title=title,
        description=description,
        tags=tags,
        source="manual",
        location="radar",
    )
    store.tasks[task.id] = task
    await ws_mgr.broadcast({"type": "task_created", "task": task.model_dump(mode="json")})
    await persist_obsidian()
    emit_log(f"Created task {task.id}: {task.title}")
    return task


@app.patch("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, data: TaskUpdate):
    """Update a task."""
    t = store.tasks.get(task_id)
    if not t:
        raise HTTPException(404)

    for field, val in data.model_dump(exclude_none=True).items():
        setattr(t, field, val)

    t.updated = datetime.now(timezone.utc)
    await ws_mgr.broadcast({"type": "task_updated", "task": t.model_dump(mode="json")})
    await persist_obsidian()
    return t


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task."""
    if task_id not in store.tasks:
        raise HTTPException(404)
    task = store.tasks.pop(task_id)
    await ws_mgr.broadcast({"type": "task_deleted", "task_id": task_id})
    await persist_obsidian()
    emit_log(f"Deleted task {task_id}: {task.title}")
    return {"deleted": task_id}


@app.post("/tasks/{task_id}/move")
async def move_task(task_id: str, body: dict[str, Any]):
    """Move task to different location/status."""
    t = store.tasks.get(task_id)
    if not t:
        raise HTTPException(404)

    location = body.get("location")
    status = body.get("status")

    if location:
        t.location = location
    if status:
        t.status = status

    t.updated = datetime.now(timezone.utc)
    await ws_mgr.broadcast({"type": "task_updated", "task": t.model_dump(mode="json")})
    await persist_obsidian()
    return t


@app.post("/tasks/reevaluate")
async def reevaluate_tasks(body: dict[str, Any], background_tasks: BackgroundTasks):
    """Analyze selected Radar tasks with AI."""
    task_ids = body.get("task_ids", [])

    async def analyze_batch():
        for task_id in task_ids:
            try:
                await analyze_task_with_ai(task_id)
                await persist_obsidian()
            except Exception as e:
                emit_log(f"Failed to analyze {task_id}: {e}", level="ERROR")

    background_tasks.add_task(analyze_batch)
    return {"status": "analysis_started", "task_ids": task_ids}


# ── Routes: Sync ───────────────────────────────────────────────────────────────
@app.post("/sync")
async def sync_tasks(background_tasks: BackgroundTasks):
    """Sync from Obsidian."""
    background_tasks.add_task(sync_from_obsidian)
    return {"status": "sync_started"}


@app.get("/export/obsidian")
def export_obsidian():
    """Export tasks as Obsidian markdown."""
    if not store.obsidian_template:
        return PlainTextResponse("", media_type="text/markdown")
    _write_todo_file(cfg.obsidian_todo_path, store.obsidian_template, list(store.tasks.values()))
    content = Path(cfg.obsidian_todo_path).read_text(encoding="utf-8")
    return PlainTextResponse(content, media_type="text/markdown")


# ── Routes: Stats ──────────────────────────────────────────────────────────────
@app.get("/stats")
def get_stats():
    """Get task statistics."""
    radar_count = len([t for t in store.tasks.values() if t.location == "radar"])
    todo_count = len([t for t in store.tasks.values() if t.location == "runway" and t.status == "todo"])
    in_progress_count = len(
        [t for t in store.tasks.values() if t.location == "runway" and t.status == "in_progress"]
    )
    done_count = len([t for t in store.tasks.values() if t.location == "runway" and t.status == "done"])

    # Calculate totals
    total_time = sum(
        (t.estimated_minutes or 0)
        for t in store.tasks.values()
        if t.location == "runway" and t.status != "done"
    )

    return {
        "radar": radar_count,
        "todo": todo_count,
        "in_progress": in_progress_count,
        "done": done_count,
        "total_estimated_minutes": total_time,
    }


@app.get("/logs")
def get_logs(limit: int = 200):
    """Get recent logs."""
    return store.logs[-limit:]


# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket(ws: WebSocket):
    """WebSocket connection for real-time updates."""
    await ws_mgr.connect(ws)
    await ws.send_json(
        {
            "type": "init",
            "tasks": [t.model_dump(mode="json") for t in store.tasks.values()],
            "logs": [l.model_dump(mode="json") for l in store.logs[-200:]],
        }
    )
    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "sync":
                asyncio.create_task(sync_from_obsidian())
            elif msg_type == "analyze":
                task_id = msg.get("task_id")
                if task_id:
                    try:
                        await analyze_task_with_ai(task_id)
                        await persist_obsidian()
                    except Exception as e:
                        emit_log(f"Analysis failed: {e}", level="ERROR")
    except WebSocketDisconnect:
        ws_mgr.disconnect(ws)
