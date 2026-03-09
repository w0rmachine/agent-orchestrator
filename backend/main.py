"""
Radar·Runway — Minimal FastAPI backend with Obsidian Kanban sync.
Reads Work/TODO.md, assigns IDs, keeps tickets in memory, and writes
updates back to the kanban on every change.
"""

from __future__ import annotations

import asyncio
import hashlib
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
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field


# ── Config ────────────────────────────────────────────────────────────────────
@dataclass
class Config:
    obsidian_todo_path: str = "~/Documents/notes/Work/TODO.md"
    simulate: bool = True
    codex_command: str = "codex"


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
    if "codex_command" in data:
        cfg.codex_command = data["codex_command"]
    cfg.obsidian_todo_path = os.path.expanduser(cfg.obsidian_todo_path)
    return cfg


cfg = load_config()


# ── Types ─────────────────────────────────────────────────────────────────────
TicketSource = Literal["youtrack", "obsidian", "manual"]
TicketStage = Literal["inbox", "backlog", "analysis", "active", "testing", "done", "blocked"]
TicketPriority = Literal["critical", "high", "normal", "low"]
SessionStatus = Literal[
    "initializing",
    "running",
    "awaiting_permission",
    "testing",
    "done",
    "failed",
    "cancelled",
]


# ── Models ────────────────────────────────────────────────────────────────────
class Ticket(BaseModel):
    id: str
    source: TicketSource = "obsidian"
    external_id: str | None = None
    title: str
    description: str = ""
    tags: list[str] = []
    priority: TicketPriority = "normal"
    stage: TicketStage = "inbox"
    session_id: str | None = None
    parent_id: str | None = None
    subtask_ids: list[str] = []
    context: dict[str, Any] = {}
    manager_notes: str = ""
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    order: int = 0
    details: list[str] = []


class TicketUpdate(BaseModel):
    title: str | None = None
    stage: TicketStage | None = None
    tags: list[str] | None = None
    priority: TicketPriority | None = None
    description: str | None = None
    manager_notes: str | None = None
    context: dict[str, Any] | None = None


class ActivateRequest(BaseModel):
    git_repo: str | None = None
    branch_hint: str | None = None


class Session(BaseModel):
    id: str
    ticket_id: str
    status: SessionStatus = "initializing"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    current_step: str = "initializing"
    steps_done: list[str] = []


class LogEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    session_id: str | None = None
    level: Literal["DEBUG", "INFO", "WARN", "ERROR"] = "INFO"
    message: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Store ─────────────────────────────────────────────────────────────────────
class Store:
    def __init__(self):
        self.tickets: dict[str, Ticket] = {}
        self.sessions: dict[str, Session] = {}
        self.logs: list[LogEntry] = []
        self.next_obsidian_id: int = 1
        self.obsidian_template: ObsidianTemplate | None = None

    def add_log(self, message: str, session_id: str | None = None, level: str = "INFO") -> LogEntry:
        entry = LogEntry(message=message, session_id=session_id, level=level)  # type: ignore
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


# ── Obsidian Kanban parsing ───────────────────────────────────────────────────
TASK_RE = re.compile(r"^- \[( |x|X)\] (.+)$")
ID_RE = re.compile(r"\b(YT-\d+|O-\d+)\b")

HEADER_TO_STAGE = {
    "ticket needed": "inbox",
    "backlog": "backlog",
    "in progress": "active",
    "waiting / blocked": "blocked",
    "done": "done",
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


def _parse_todo_file(path: str) -> tuple[list[Ticket], ObsidianTemplate, bool]:
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

    tickets: list[Ticket] = []
    dirty = False
    order_counter = 0
    max_obsidian = 0

    for section in sections:
        stage = HEADER_TO_STAGE.get(_normalize_header(section.header))
        if not stage:
            continue
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

            order_counter += 1
            source: TicketSource = "youtrack" if tid.startswith("YT-") else "obsidian"
            ticket = Ticket(
                id=tid,
                source=source,
                external_id=tid if source == "youtrack" else None,
                title=title,
                stage=stage,  # type: ignore
                order=order_counter,
                details=details,
            )
            tickets.append(ticket)
            i = max(j, i + 1)

    if max_obsidian >= store.next_obsidian_id:
        store.next_obsidian_id = max_obsidian + 1

    return tickets, ObsidianTemplate(preamble, sections, tail), dirty


def _render_task_line(ticket: Ticket) -> list[str]:
    checked = "x" if ticket.stage == "done" else " "
    title = ticket.title.strip()
    line = f"- [{checked}] [{ticket.id}] {title}".rstrip()
    lines = [line]
    lines.extend(ticket.details)
    return lines


def _write_todo_file(path: str, template: ObsidianTemplate, tickets: list[Ticket]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.extend(template.preamble)

    tickets_by_stage: dict[str, list[Ticket]] = {}
    for t in tickets:
        tickets_by_stage.setdefault(t.stage, []).append(t)
    for stage in tickets_by_stage:
        tickets_by_stage[stage].sort(key=lambda t: t.order)

    for section in template.sections:
        lines.append(f"## {section.header}")
        stage = HEADER_TO_STAGE.get(_normalize_header(section.header))
        if not stage:
            lines.extend(section.lines)
            continue
        for ticket in tickets_by_stage.get(stage, []):
            lines.extend(_render_task_line(ticket))
        lines.append("")

    if template.tail:
        lines.extend(template.tail)

    p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


async def sync_from_obsidian() -> int:
    tickets, template, dirty = _parse_todo_file(cfg.obsidian_todo_path)
    store.obsidian_template = template
    seen = {t.id for t in tickets}

    added = 0
    for t in tickets:
        if t.id in store.tickets:
            existing = store.tickets[t.id]
            existing.title = t.title
            existing.stage = t.stage
            existing.details = t.details
            existing.order = t.order
            existing.updated = datetime.now(timezone.utc)
        else:
            store.tickets[t.id] = t
            added += 1

    # Remove obsidian tickets that were deleted from the file
    for tid in list(store.tickets.keys()):
        t = store.tickets[tid]
        if t.source == "obsidian" and tid not in seen:
            store.tickets.pop(tid)

    if dirty:
        _write_todo_file(cfg.obsidian_todo_path, template, list(store.tickets.values()))

    if added:
        await ws_mgr.broadcast({"type": "sync_complete", "added": added})
    return added


async def persist_obsidian() -> None:
    if not store.obsidian_template:
        return
    _write_todo_file(cfg.obsidian_todo_path, store.obsidian_template, list(store.tickets.values()))


# ── Session runner (codex placeholder) ────────────────────────────────────────
def _make_session_id(ticket_id: str) -> str:
    raw = f"{ticket_id}-{uuid.uuid4()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def run_session(session_id: str):
    session = store.sessions[session_id]
    session.status = "running"
    await ws_mgr.broadcast({"type": "session_updated", "session": session.model_dump(mode="json")})
    await emit(session_id, f"[codex] Starting session for ticket {session.ticket_id}")
    await asyncio.sleep(0.5)
    session.steps_done.append("codex_start")
    session.current_step = "codex_run"
    await emit(session_id, f"[codex] (simulate) Would run: {cfg.codex_command}")
    await asyncio.sleep(1.0)
    session.steps_done.append("codex_done")
    session.current_step = "done"
    session.status = "done"
    session.finished_at = datetime.now(timezone.utc)
    await ws_mgr.broadcast({"type": "session_updated", "session": session.model_dump(mode="json")})


# ── Logging helpers ───────────────────────────────────────────────────────────
async def emit(session_id: str | None, message: str, level: str = "INFO"):
    entry = store.add_log(message, session_id=session_id, level=level)
    await ws_mgr.broadcast({"type": "log", "log": entry.model_dump(mode="json")})


# ── FastAPI app ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await sync_from_obsidian()
    yield


app = FastAPI(title="Radar·Runway Orchestrator", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes: tickets ───────────────────────────────────────────────────────────
@app.get("/tickets", response_model=list[Ticket])
def list_tickets(stage: TicketStage | None = None):
    out = list(store.tickets.values())
    if stage:
        out = [t for t in out if t.stage == stage]
    return sorted(out, key=lambda t: t.order)


@app.get("/tickets/{tid}", response_model=Ticket)
def get_ticket(tid: str):
    t = store.tickets.get(tid)
    if not t:
        raise HTTPException(404, "Ticket not found")
    return t


@app.patch("/tickets/{tid}", response_model=Ticket)
async def update_ticket(tid: str, data: TicketUpdate):
    t = store.tickets.get(tid)
    if not t:
        raise HTTPException(404)
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(t, field, val)
    t.updated = datetime.now(timezone.utc)
    await ws_mgr.broadcast({"type": "ticket_updated", "ticket": t.model_dump(mode="json")})
    await persist_obsidian()
    return t


@app.post("/tickets/{tid}/activate", response_model=Session)
async def activate_ticket(tid: str, body: ActivateRequest, background_tasks: BackgroundTasks):
    t = store.tickets.get(tid)
    if not t:
        raise HTTPException(404)
    if t.session_id:
        raise HTTPException(409, "Ticket already has an active session")

    session = Session(id=_make_session_id(tid), ticket_id=tid)
    store.sessions[session.id] = session
    t.session_id = session.id
    t.stage = "active"
    t.updated = datetime.now(timezone.utc)
    await ws_mgr.broadcast({"type": "session_created", "session": session.model_dump(mode="json")})
    await ws_mgr.broadcast({"type": "ticket_updated", "ticket": t.model_dump(mode="json")})
    await persist_obsidian()
    background_tasks.add_task(run_session, session.id)
    return session


@app.post("/sync")
async def sync_tickets(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_from_obsidian)
    return {"status": "sync_started"}


@app.get("/export/obsidian")
def export_obsidian():
    if not store.obsidian_template:
        return PlainTextResponse("", media_type="text/markdown")
    _write_todo_file(cfg.obsidian_todo_path, store.obsidian_template, list(store.tickets.values()))
    content = Path(cfg.obsidian_todo_path).read_text(encoding="utf-8")
    return PlainTextResponse(content, media_type="text/markdown")


# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws_mgr.connect(ws)
    await ws.send_json(
        {
            "type": "init",
            "tickets": [t.model_dump(mode="json") for t in store.tickets.values()],
            "sessions": [s.model_dump(mode="json") for s in store.sessions.values()],
            "logs": [l.model_dump(mode="json") for l in store.logs[-200:]],
        }
    )
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "activate":
                tid = msg.get("ticket_id")
                if tid in store.tickets and not store.tickets[tid].session_id:
                    session = Session(id=_make_session_id(tid), ticket_id=tid)
                    store.sessions[session.id] = session
                    t = store.tickets[tid]
                    t.session_id = session.id
                    t.stage = "active"
                    t.updated = datetime.now(timezone.utc)
                    await ws_mgr.broadcast(
                        {"type": "session_created", "session": session.model_dump(mode="json")}
                    )
                    await ws_mgr.broadcast(
                        {"type": "ticket_updated", "ticket": t.model_dump(mode="json")}
                    )
                    await persist_obsidian()
                    asyncio.create_task(run_session(session.id))
            if msg.get("type") == "sync":
                asyncio.create_task(sync_from_obsidian())
    except WebSocketDisconnect:
        ws_mgr.disconnect(ws)
