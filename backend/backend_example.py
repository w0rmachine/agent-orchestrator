"""
Radar·Runway — Session Orchestration Backend v2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Install : pip install fastapi uvicorn aiofiles pydantic-settings httpx
Run     : uvicorn main:app --reload --port 8000
Docs    : http://localhost:8000/docs

Recommended split as the project grows:
  config.py          ← Settings
  models.py          ← all Pydantic models
  store.py           ← Store + WsManager
  agents/
    manager.py       ← ticket analysis & splitting (Claude API)
    session.py       ← session lifecycle (git, workspace, logs)
    tester.py        ← test-session runner
  integrations/
    youtrack.py      ← YouTrack REST client
    obsidian.py      ← Obsidian vault reader
"""

# ── Imports ───────────────────────────────────────────────────────────────────
import asyncio
import hashlib
import random
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import aiofiles
from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  CONFIG
# ╚══════════════════════════════════════════════════════════════════════════════
class Settings(BaseSettings):
    youtrack_url: str = "https://your-org.youtrack.cloud"
    youtrack_token: str = ""
    youtrack_project: str = ""  # e.g. "PROJ"
    obsidian_vault: str = "./vault"  # absolute path to Obsidian vault root
    workspace_root: str = "./sessions"
    logs_root: str = "./logs"
    git_remote: str = ""  # fallback remote when ticket has none
    anthropic_api_key: str = ""
    simulate: bool = True  # set False to use real APIs

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


cfg = Settings()


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  TYPES
# ╚══════════════════════════════════════════════════════════════════════════════
TicketSource = Literal["youtrack", "obsidian", "manual"]
TicketStage = Literal[
    "inbox", "backlog", "analysis", "active", "testing", "done", "blocked"
]
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
PermLevel = Literal["elevated", "sudo", "destructive"]


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  MODELS
# ╚══════════════════════════════════════════════════════════════════════════════
class Ticket(BaseModel):
    id: str = Field(default_factory=lambda: f"T-{uuid.uuid4().hex[:6].upper()}")
    source: TicketSource = "manual"
    external_id: str | None = None  # "YT-123" | "research/auth.md"
    title: str
    description: str = ""
    tags: list[str] = []
    priority: TicketPriority = "normal"
    stage: TicketStage = "inbox"
    session_id: str | None = None
    parent_id: str | None = None  # set when split from parent ticket
    subtask_ids: list[str] = []
    context: dict[str, Any] = {}  # {repo, branch_hint, youtrack_info, …}
    manager_notes: str = ""
    needs_split: bool = False
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PermissionRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    session_id: str
    action: str  # machine-readable key, e.g. "run_db_migration"
    description: str  # human-readable, shown in dashboard
    level: PermLevel
    command: str | None = None  # exact shell command if applicable
    status: Literal["pending", "approved", "denied"] = "pending"
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None


class SessionReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    session_id: str
    ticket_id: str
    summary: str
    files_changed: list[str] = []
    tests_passed: int = 0
    tests_failed: int = 0
    commits: list[str] = []
    duration_seconds: float = 0.0
    test_session_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Session(BaseModel):
    id: str  # sha256 hex prefix — also the workspace folder name
    ticket_id: str
    status: SessionStatus = "initializing"
    workspace_dir: str  # sessions/{id}/
    log_path: str  # logs/{id}/coding.log
    git_repo: str | None = None
    branch_name: str | None = None
    youtrack_id: str | None = None
    context: dict[str, Any] = {}
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    current_step: str = "initializing"
    steps_done: list[str] = []
    perm_ids: list[str] = []  # PermissionRequest.id references
    report_id: str | None = None
    is_test_session: bool = False
    parent_session: str | None = None  # for test sessions

    @computed_field
    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at or datetime.now(timezone.utc)
        return round((end - self.started_at).total_seconds(), 1)


class LogEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    session_id: str | None = None  # None → global log
    level: Literal["DEBUG", "INFO", "WARN", "ERROR"] = "INFO"
    message: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Request/Create schemas ────────────────────────────────────────────────────
class TicketCreate(BaseModel):
    title: str
    source: TicketSource = "manual"
    external_id: str | None = None
    description: str = ""
    tags: list[str] = []
    priority: TicketPriority = "normal"
    context: dict[str, Any] = {}


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
    branch_hint: str | None = None  # used as branch prefix; ticket-id appended


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  STORE  (swap internals for SQLAlchemy + Postgres without touching routes)
# ╚══════════════════════════════════════════════════════════════════════════════
class Store:
    def __init__(self):
        self.tickets: dict[str, Ticket] = {}
        self.sessions: dict[str, Session] = {}
        self.perms: dict[str, PermissionRequest] = {}
        self.reports: dict[str, SessionReport] = {}
        self.logs: list[LogEntry] = []
        # asyncio.Event keyed by PermissionRequest.id — used to pause sessions
        self._perm_events: dict[str, asyncio.Event] = {}

        if cfg.simulate:
            self._seed()

    # ── Seed ──
    def _seed(self):
        seeds: list[tuple] = [
            (
                "youtrack",
                "YT-101",
                "Implement OAuth2 PKCE flow",
                "high",
                "active",
                "git@github.com:org/auth-service.git",
            ),
            (
                "youtrack",
                "YT-102",
                "Migrate auth service to OAuth2",
                "critical",
                "analysis",
                "git@github.com:org/auth-service.git",
            ),
            (
                "youtrack",
                "YT-103",
                "Fix flaky CI on main branch",
                "high",
                "backlog",
                "",
            ),
            (
                "obsidian",
                "auth/rate-limit.md",
                "Research rate-limiting strategies",
                "normal",
                "inbox",
                "",
            ),
            (
                "youtrack",
                "YT-105",
                "DB migration for user table v3",
                "high",
                "blocked",
                "git@github.com:org/backend.git",
            ),
            (
                "manual",
                None,
                "Add OpenTelemetry spans to all routes",
                "normal",
                "inbox",
                "",
            ),
            (
                "youtrack",
                "YT-107",
                "Payment webhook retry logic",
                "normal",
                "backlog",
                "git@github.com:org/payments.git",
            ),
            (
                "youtrack",
                "YT-108",
                "Patch datetime UTC conversion bug",
                "high",
                "done",
                "",
            ),
        ]
        for source, ext_id, title, priority, stage, repo in seeds:
            ctx = {"repo": repo} if repo else {}
            t = Ticket(
                source=source,
                external_id=ext_id,
                title=title,  # type: ignore
                priority=priority,
                stage=stage,
                context=ctx,
            )  # type: ignore
            self.tickets[t.id] = t

    # ── Log helpers ──
    def add_log(
        self, msg: str, session_id: str | None = None, level: str = "INFO"
    ) -> LogEntry:
        e = LogEntry(session_id=session_id, message=msg, level=level)  # type: ignore
        self.logs.append(e)
        self.logs = self.logs[-2000:]
        return e

    def get_logs(
        self, session_id: str | None = None, limit: int = 200
    ) -> list[LogEntry]:
        src = (
            [l for l in self.logs if l.session_id == session_id]
            if session_id
            else self.logs
        )
        return src[-limit:]

    # ── Stats ──
    def stats(self) -> dict:
        t_all = list(self.tickets.values())
        s_all = list(self.sessions.values())
        return {
            "tickets": {
                "total": len(t_all),
                "by_stage": {
                    s: sum(1 for t in t_all if t.stage == s)
                    for s in (
                        "inbox",
                        "backlog",
                        "analysis",
                        "active",
                        "testing",
                        "done",
                        "blocked",
                    )
                },
                "by_source": {
                    s: sum(1 for t in t_all if t.source == s)
                    for s in ("youtrack", "obsidian", "manual")
                },
            },
            "sessions": {
                "total": len(s_all),
                "running": sum(1 for s in s_all if s.status == "running"),
                "awaiting": sum(1 for s in s_all if s.status == "awaiting_permission"),
                "done": sum(1 for s in s_all if s.status == "done"),
                "by_status": {
                    st: sum(1 for s in s_all if s.status == st)
                    for st in (
                        "initializing",
                        "running",
                        "awaiting_permission",
                        "testing",
                        "done",
                        "failed",
                        "cancelled",
                    )
                },
            },
            "permissions": {
                "pending": sum(1 for p in self.perms.values() if p.status == "pending"),
                "approved": sum(
                    1 for p in self.perms.values() if p.status == "approved"
                ),
                "denied": sum(1 for p in self.perms.values() if p.status == "denied"),
            },
        }


store = Store()


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  WEBSOCKET MANAGER
# ╚══════════════════════════════════════════════════════════════════════════════
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


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LOG UTILITIES
# ╚══════════════════════════════════════════════════════════════════════════════
async def write_log_file(log_path: str, message: str, level: str = "INFO"):
    """Append a line to the session log file on disk."""
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    async with aiofiles.open(path, "a") as f:
        await f.write(f"[{ts}] [{level:<5}] {message}\n")


async def emit(session_id: str | None, message: str, level: str = "INFO"):
    """Store entry + write to disk (if session) + broadcast over WebSocket."""
    entry = store.add_log(message, session_id=session_id, level=level)
    if session_id and (s := store.sessions.get(session_id)):
        await write_log_file(s.log_path, message, level)
    await ws_mgr.broadcast({"type": "log", "log": entry.model_dump(mode="json")})


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  SESSION LIFECYCLE
# ╚══════════════════════════════════════════════════════════════════════════════
def _make_session_id(ticket_id: str) -> str:
    raw = f"{ticket_id}-{uuid.uuid4()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def create_session(
    ticket: Ticket,
    is_test: bool = False,
    parent_session: str | None = None,
) -> Session:
    sid = _make_session_id(ticket.id)
    safe = (ticket.external_id or ticket.id).replace("/", "-").replace(" ", "_").lower()
    branch = f"{safe}-impl" if not is_test else f"{safe}-test"
    repo = ticket.context.get("repo") or cfg.git_remote or "git@github.com:org/repo.git"

    session = Session(
        id=sid,
        ticket_id=ticket.id,
        workspace_dir=str(Path(cfg.workspace_root) / sid),
        log_path=str(Path(cfg.logs_root) / sid / "coding.log"),
        git_repo=repo,
        branch_name=branch,
        youtrack_id=ticket.external_id if ticket.source == "youtrack" else None,
        context={
            **ticket.context,
            "ticket_title": ticket.title,
            "ticket_description": ticket.description,
        },
        is_test_session=is_test,
        parent_session=parent_session,
    )
    store.sessions[sid] = session
    ticket.session_id = sid
    ticket.stage = "active" if not is_test else "testing"

    await emit(sid, f"Session {sid} created for ticket {ticket.id} ({ticket.title})")
    await ws_mgr.broadcast(
        {"type": "session_created", "session": session.model_dump(mode="json")}
    )
    return session


# ── Step definitions ──────────────────────────────────────────────────────────
# (step_id, log_message, simulated_duration_s, perm_level|None, perm_action|None)
CODING_STEPS: list[tuple] = [
    ("setup_workspace", "Setting up workspace directory", 0.6, None, None),
    ("clone_repo", "Cloning repository", 2.0, None, None),
    ("create_branch", "Creating feature branch", 0.8, None, None),
    ("index_codebase", "Indexing codebase for context", 1.5, None, None),
    ("fetch_ticket_ctx", "Fetching YouTrack context and history", 1.0, None, None),
    ("plan", "Planning implementation strategy", 2.5, None, None),
    ("write_code", "Writing implementation", 4.5, None, None),
    ("lint", "Running linter checks", 0.8, None, None),
    ("unit_tests", "Running unit tests", 1.5, None, None),
    (
        "db_migration",
        "Requesting permission: run DB migration",
        0.3,
        "elevated",
        "run_db_migration",
    ),
    ("run_migration", "Executing database migration", 1.2, None, None),
    ("integration_tests", "Running integration test suite", 2.0, None, None),
    ("commit", "Committing changes", 0.5, None, None),
    (
        "push",
        "Requesting permission: push branch to remote",
        0.3,
        "elevated",
        "git_push_remote",
    ),
    ("push_exec", "Pushing branch to origin", 0.8, None, None),
    ("generate_report", "Generating completion report", 0.8, None, None),
]

TEST_STEPS: list[tuple] = [
    ("checkout", "Checking out branch from coding session", 0.8, None, None),
    ("install_deps", "Installing test dependencies", 1.0, None, None),
    ("full_suite", "Running full test suite", 3.5, None, None),
    ("coverage", "Generating coverage report", 1.0, None, None),
    (
        "security_scan",
        "Requesting permission: run security scanner",
        0.3,
        "elevated",
        "run_security_scan",
    ),
    ("scan_exec", "Running security vulnerability scan", 1.5, None, None),
    ("finalize", "Finalizing test report", 0.5, None, None),
]


async def run_session(session_id: str, is_test: bool = False):
    """
    Core coroutine: runs one session through all its steps.
    Pauses at permission gates via asyncio.Event — resumes when user
    clicks Approve/Deny in the dashboard.

    In production: replace the asyncio.sleep() calls with real agent
    invocations (Claude API, subprocess git commands, pytest runner, etc.)
    """
    session = store.sessions[session_id]
    session.status = "running"
    steps = TEST_STEPS if is_test else CODING_STEPS
    await ws_mgr.broadcast(
        {"type": "session_updated", "session": session.model_dump(mode="json")}
    )

    for step_id, msg, duration, perm_level, perm_action in steps:
        session.current_step = step_id

        # ── Log and broadcast each step ──
        full_msg = f"[{step_id}] {msg}"
        if step_id in ("clone_repo", "create_branch") and session.git_repo:
            full_msg += f" ({session.git_repo})"
        if step_id == "create_branch" and session.branch_name:
            full_msg = f"[{step_id}] Creating branch: {session.branch_name}"

        await emit(session_id, full_msg)
        await ws_mgr.broadcast(
            {
                "type": "session_step",
                "session_id": session_id,
                "step": step_id,
                "message": full_msg,
            }
        )

        # ── Permission gate ──────────────────────────────────────────────────
        if perm_level:
            perm = PermissionRequest(
                session_id=session_id,
                action=perm_action or step_id,
                description=msg,
                level=perm_level,
                command=f"exec:{step_id}",
            )
            store.perms[perm.id] = perm
            session.perm_ids.append(perm.id)
            session.status = "awaiting_permission"

            # Create the event BEFORE broadcasting so the approve handler
            # never races ahead of the await below.
            event = asyncio.Event()
            store._perm_events[perm.id] = event

            await emit(
                session_id,
                f"⚠ PERMISSION REQUIRED [{perm_level.upper()}]: {perm_action}",
                level="WARN",
            )
            await ws_mgr.broadcast(
                {
                    "type": "permission_required",
                    "session_id": session_id,
                    "permission": perm.model_dump(mode="json"),
                    "session": session.model_dump(mode="json"),
                }
            )

            await event.wait()  # ← session coroutine is paused here

            perm = store.perms[perm.id]  # re-fetch (status may have changed)
            if perm.status == "denied":
                session.status = "failed"
                session.finished_at = datetime.now(timezone.utc)
                await emit(
                    session_id,
                    f"✗ Permission denied for '{perm_action}' — session failed.",
                    level="ERROR",
                )
                await ws_mgr.broadcast(
                    {
                        "type": "session_failed",
                        "session_id": session_id,
                        "session": session.model_dump(mode="json"),
                    }
                )
                return

            session.status = "running"
            await emit(session_id, f"✓ Permission approved: {perm_action}")
            await ws_mgr.broadcast(
                {"type": "session_updated", "session": session.model_dump(mode="json")}
            )
        # ── /Permission gate ─────────────────────────────────────────────────

        # Simulated work; replace with real agent call
        await asyncio.sleep(duration)
        session.steps_done.append(step_id)
        await ws_mgr.broadcast(
            {"type": "session_updated", "session": session.model_dump(mode="json")}
        )

    # ── Session complete ──────────────────────────────────────────────────────
    session.finished_at = datetime.now(timezone.utc)
    session.current_step = "done"
    session.status = "done"
    ticket = store.tickets.get(session.ticket_id)

    if not is_test:
        report = SessionReport(
            session_id=session_id,
            ticket_id=session.ticket_id,
            summary=(
                f"Implementation complete for '{ticket.title if ticket else session.ticket_id}'. "
                "All lint, unit, and integration checks passed. Branch ready for review."
            ),
            files_changed=[
                "src/auth/token.py",
                "src/auth/pkce.py",
                "tests/test_auth.py",
                "migrations/0012_auth.sql",
            ],
            tests_passed=random.randint(18, 32),
            tests_failed=0,
            commits=[
                f"feat({session.branch_name}): implement core logic",
                "test: add unit coverage",
                "chore: run migration",
            ],
            duration_seconds=session.elapsed_seconds,
        )
        store.reports[session_id] = report
        session.report_id = report.id
        if ticket:
            ticket.stage = "testing"

        await emit(session_id, "✓ Coding session complete. Report generated.")
        await ws_mgr.broadcast(
            {
                "type": "session_done",
                "session_id": session_id,
                "report": report.model_dump(mode="json"),
                "session": session.model_dump(mode="json"),
            }
        )

        # Spawn test session automatically
        if ticket and random.random() < 0.85:
            await emit(None, f"Spawning test session for coding session {session_id}")
            test_sess = await create_session(
                ticket, is_test=True, parent_session=session_id
            )
            report.test_session_id = test_sess.id
            asyncio.create_task(run_session(test_sess.id, is_test=True))

    else:
        # ── Test session report ──
        tests_total = random.randint(28, 45)
        report = SessionReport(
            session_id=session_id,
            ticket_id=session.ticket_id,
            summary=(
                f"Test session complete. {tests_total} tests passed, "
                "coverage 94%, no security vulnerabilities found."
            ),
            tests_passed=tests_total,
            tests_failed=0,
            duration_seconds=session.elapsed_seconds,
        )
        store.reports[session_id] = report
        session.report_id = report.id
        if ticket:
            ticket.stage = "done"
            ticket.updated = datetime.now(timezone.utc)

        await emit(session_id, "✓ Test session complete. Ticket marked DONE.")
        await ws_mgr.broadcast(
            {
                "type": "session_done",
                "session_id": session_id,
                "report": report.model_dump(mode="json"),
                "session": session.model_dump(mode="json"),
            }
        )

    await ws_mgr.broadcast(
        {"type": "session_updated", "session": session.model_dump(mode="json")}
    )
    if ticket:
        await ws_mgr.broadcast(
            {"type": "ticket_updated", "ticket": ticket.model_dump(mode="json")}
        )
    await ws_mgr.broadcast({"type": "stats", "stats": store.stats()})


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  MANAGER AGENT
# ╚══════════════════════════════════════════════════════════════════════════════
# Production: replace simulate_* functions with real calls to:
#   - httpx client → YouTrack REST API  (GET /api/issues?project=…)
#   - pathlib glob → Obsidian vault      (*.md files with frontmatter)
#   - anthropic.Anthropic().messages.create(…) for analysis + splitting

_SAMPLE_YT = [
    (
        "YT-201",
        "Add rate limiting to /api/users",
        "high",
        "git@github.com:org/backend.git",
    ),
    (
        "YT-202",
        "Investigate memory leak in job worker",
        "high",
        "git@github.com:org/worker.git",
    ),
    (
        "YT-203",
        "Refactor payment service for testability",
        "critical",
        "git@github.com:org/payments.git",
    ),
    (
        "YT-204",
        "Add Prometheus metrics to auth routes",
        "normal",
        "git@github.com:org/auth-service.git",
    ),
]

_SAMPLE_OB = [
    ("research/graphql-pagination.md", "Research GraphQL cursor pagination", "normal"),
    ("tasks/opentelemetry-setup.md", "OpenTelemetry: trace all API calls", "high"),
]


async def sync_sources() -> int:
    """
    Pull tickets from YouTrack + Obsidian vault and add new ones to inbox.

    Production replacement:
        yt_issues  = await youtrack_client.get_issues(project=cfg.youtrack_project)
        ob_tickets = obsidian_reader.scan_vault(cfg.obsidian_vault, tag="task")
    """
    existing = {t.external_id for t in store.tickets.values()}
    added = 0

    for ext_id, title, priority, repo in _SAMPLE_YT:
        if ext_id not in existing:
            t = Ticket(
                source="youtrack",
                external_id=ext_id,
                title=title,  # type: ignore
                priority=priority,
                stage="inbox",
                context={"repo": repo},
            )
            store.tickets[t.id] = t
            await emit(None, f"Synced from YouTrack: {ext_id} — {title}")
            await ws_mgr.broadcast(
                {"type": "ticket_created", "ticket": t.model_dump(mode="json")}
            )
            added += 1

    for ext_id, title, priority in _SAMPLE_OB:
        if ext_id not in existing:
            t = Ticket(
                source="obsidian",
                external_id=ext_id,
                title=title,  # type: ignore
                priority=priority,
                stage="inbox",
                context={"vault_path": str(Path(cfg.obsidian_vault) / ext_id)},
            )
            store.tickets[t.id] = t
            await emit(None, f"Synced from Obsidian: {ext_id} — {title}")
            await ws_mgr.broadcast(
                {"type": "ticket_created", "ticket": t.model_dump(mode="json")}
            )
            added += 1

    await ws_mgr.broadcast(
        {"type": "sync_complete", "added": added, "stats": store.stats()}
    )
    return added


async def analyze_ticket(ticket_id: str):
    """
    Manager agent: enrich tags, decide if the ticket needs splitting.

    Production replacement:
        response = anthropic_client.messages.create(
            model  = "claude-sonnet-4",
            system = MANAGER_SYSTEM_PROMPT,
            messages = [{"role":"user","content": ticket.model_dump_json()}],
        )
        result = parse_json(response.content[0].text)
    """
    ticket = store.tickets.get(ticket_id)
    if not ticket:
        return

    ticket.stage = "analysis"
    await emit(None, f"Manager analyzing: {ticket.id} — {ticket.title}")
    await ws_mgr.broadcast(
        {"type": "ticket_updated", "ticket": ticket.model_dump(mode="json")}
    )

    await asyncio.sleep(2.0)  # simulate LLM round-trip

    # Heuristic split decision (replace with actual LLM output)
    needs_split = any(
        kw in ticket.title.lower() for kw in ("migrate", "refactor", "implement", "add")
    )

    if needs_split:
        subtitles = [
            f"[Analysis]      {ticket.title}",
            f"[Implementation]{ticket.title}",
            f"[Tests & Docs]  {ticket.title}",
        ]
        subtask_ids = []
        for sub in subtitles:
            child = Ticket(
                source=ticket.source,
                title=sub,
                priority=ticket.priority,
                stage="backlog",
                parent_id=ticket.id,
                context=ticket.context.copy(),
                tags=ticket.tags + ["split", "manager-generated"],
            )
            store.tickets[child.id] = child
            subtask_ids.append(child.id)
            await ws_mgr.broadcast(
                {"type": "ticket_created", "ticket": child.model_dump(mode="json")}
            )

        ticket.needs_split = True
        ticket.subtask_ids = subtask_ids
        ticket.stage = "backlog"
        ticket.manager_notes = f"Split into {len(subtitles)} subtasks by manager agent."
        await emit(None, f"Ticket {ticket.id} → split into {len(subtitles)} subtasks")
    else:
        ticket.stage = "backlog"
        ticket.tags = list(set(ticket.tags + ["analyzed", "ready"]))
        ticket.manager_notes = "Analyzed by manager agent. No split needed."
        await emit(None, f"Ticket {ticket.id} analyzed → backlog (no split)")

    ticket.updated = datetime.now(timezone.utc)
    await ws_mgr.broadcast(
        {"type": "ticket_updated", "ticket": ticket.model_dump(mode="json")}
    )
    await ws_mgr.broadcast({"type": "stats", "stats": store.stats()})


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  APP + LIFESPAN
# ╚══════════════════════════════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    if cfg.simulate:
        # Auto-activate the seeded "active" ticket so the dashboard has live data
        for t in list(store.tickets.values()):
            if t.stage == "active" and not t.session_id:
                session = await create_session(t)
                asyncio.create_task(run_session(session.id))
                break
    yield


app = FastAPI(title="Radar·Runway Orchestrator", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ROUTES — Tickets
# ╚══════════════════════════════════════════════════════════════════════════════
@app.get("/tickets", response_model=list[Ticket])
def list_tickets(
    stage: TicketStage | None = None,
    source: TicketSource | None = None,
    priority: TicketPriority | None = None,
):
    out = list(store.tickets.values())
    if stage:
        out = [t for t in out if t.stage == stage]
    if source:
        out = [t for t in out if t.source == source]
    if priority:
        out = [t for t in out if t.priority == priority]
    return sorted(out, key=lambda t: t.created)


@app.post("/tickets", response_model=Ticket, status_code=201)
async def create_ticket(data: TicketCreate):
    t = Ticket(**data.model_dump())
    store.tickets[t.id] = t
    e = store.add_log(f"Ticket created manually: {t.id} — {t.title}")
    await ws_mgr.broadcast(
        {
            "type": "ticket_created",
            "ticket": t.model_dump(mode="json"),
            "log": e.model_dump(mode="json"),
        }
    )
    return t


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
    await ws_mgr.broadcast(
        {"type": "ticket_updated", "ticket": t.model_dump(mode="json")}
    )
    return t


@app.delete("/tickets/{tid}", status_code=204)
async def delete_ticket(tid: str):
    if tid not in store.tickets:
        raise HTTPException(404)
    store.tickets.pop(tid)
    await ws_mgr.broadcast({"type": "ticket_deleted", "ticket_id": tid})


@app.post("/tickets/{tid}/analyze")
async def trigger_analysis(tid: str, background_tasks: BackgroundTasks):
    if tid not in store.tickets:
        raise HTTPException(404)
    background_tasks.add_task(analyze_ticket, tid)
    return {"status": "analysis_started", "ticket_id": tid}


@app.post("/tickets/{tid}/activate", response_model=Session)
async def activate_ticket(
    tid: str,
    body: ActivateRequest,
    background_tasks: BackgroundTasks,
):
    t = store.tickets.get(tid)
    if not t:
        raise HTTPException(404)
    if t.session_id:
        raise HTTPException(409, "Ticket already has an active session")
    if body.git_repo:
        t.context["repo"] = body.git_repo
    if body.branch_hint:
        t.context["branch_hint"] = body.branch_hint

    session = await create_session(t)
    background_tasks.add_task(run_session, session.id)
    return session


@app.post("/sync")
async def sync_tickets(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_sources)
    return {"status": "sync_started"}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ROUTES — Sessions
# ╚══════════════════════════════════════════════════════════════════════════════
@app.get("/sessions", response_model=list[Session])
def list_sessions(status: SessionStatus | None = None):
    out = list(store.sessions.values())
    if status:
        out = [s for s in out if s.status == status]
    return sorted(out, key=lambda s: s.started_at, reverse=True)


@app.get("/sessions/{sid}", response_model=Session)
def get_session(sid: str):
    s = store.sessions.get(sid)
    if not s:
        raise HTTPException(404)
    return s


@app.get("/sessions/{sid}/logs", response_model=list[LogEntry])
def session_logs(sid: str, limit: int = 500):
    if sid not in store.sessions:
        raise HTTPException(404)
    return store.get_logs(session_id=sid, limit=limit)


@app.get("/sessions/{sid}/logfile")
async def session_logfile(sid: str):
    """Return raw log file content (as written to disk)."""
    s = store.sessions.get(sid)
    if not s:
        raise HTTPException(404)
    path = Path(s.log_path)
    if not path.exists():
        return PlainTextResponse("(log file not yet created)")
    async with aiofiles.open(path, "r") as f:
        content = await f.read()
    return PlainTextResponse(content, media_type="text/plain")


@app.post("/sessions/{sid}/cancel", status_code=200)
async def cancel_session(sid: str):
    s = store.sessions.get(sid)
    if not s:
        raise HTTPException(404)
    s.status = "cancelled"
    s.finished_at = datetime.now(timezone.utc)
    # Unblock any pending permission so the coroutine can exit
    for perm_id in s.perm_ids:
        if perm_id in store._perm_events:
            p = store.perms.get(perm_id)
            if p and p.status == "pending":
                p.status = "denied"
            store._perm_events.pop(perm_id).set()
    await ws_mgr.broadcast(
        {"type": "session_updated", "session": s.model_dump(mode="json")}
    )
    return {"status": "cancelled"}


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ROUTES — Permissions
# ╚══════════════════════════════════════════════════════════════════════════════
@app.get("/permissions", response_model=list[PermissionRequest])
def list_permissions(
    status: Literal["pending", "approved", "denied"] | None = None,
    session_id: str | None = None,
):
    out = list(store.perms.values())
    if status:
        out = [p for p in out if p.status == status]
    if session_id:
        out = [p for p in out if p.session_id == session_id]
    return out


@app.get("/permissions/{pid}", response_model=PermissionRequest)
def get_permission(pid: str):
    p = store.perms.get(pid)
    if not p:
        raise HTTPException(404)
    return p


@app.post("/permissions/{pid}/approve", response_model=PermissionRequest)
async def approve_permission(pid: str):
    p = store.perms.get(pid)
    if not p:
        raise HTTPException(404)
    if p.status != "pending":
        raise HTTPException(409, "Permission already resolved")
    p.status = "approved"
    p.resolved_at = datetime.now(timezone.utc)
    event = store._perm_events.pop(pid, None)
    if event:
        event.set()  # ← unblocks the session coroutine
    await emit(p.session_id, f"✓ Permission approved by operator: {p.action}")
    await ws_mgr.broadcast(
        {"type": "permission_resolved", "permission": p.model_dump(mode="json")}
    )
    return p


@app.post("/permissions/{pid}/deny", response_model=PermissionRequest)
async def deny_permission(pid: str):
    p = store.perms.get(pid)
    if not p:
        raise HTTPException(404)
    if p.status != "pending":
        raise HTTPException(409, "Permission already resolved")
    p.status = "denied"
    p.resolved_at = datetime.now(timezone.utc)
    event = store._perm_events.pop(pid, None)
    if event:
        event.set()  # ← unblocks the session coroutine (will then fail gracefully)
    await emit(
        p.session_id, f"✗ Permission denied by operator: {p.action}", level="WARN"
    )
    await ws_mgr.broadcast(
        {"type": "permission_resolved", "permission": p.model_dump(mode="json")}
    )
    return p


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ROUTES — Reports
# ╚══════════════════════════════════════════════════════════════════════════════
@app.get("/reports", response_model=list[SessionReport])
def list_reports():
    return list(store.reports.values())


@app.get("/reports/{sid}", response_model=SessionReport)
def get_report(sid: str):
    r = store.reports.get(sid)
    if not r:
        raise HTTPException(404)
    return r


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  ROUTES — Utility
# ╚══════════════════════════════════════════════════════════════════════════════
@app.get("/stats")
def get_stats():
    return store.stats()


@app.get("/logs", response_model=list[LogEntry])
def get_logs(limit: int = 200, session_id: str | None = None):
    return store.get_logs(session_id=session_id, limit=min(limit, 1000))


@app.get("/export/obsidian")
def export_obsidian():
    """Export current ticket state as Obsidian Kanban plugin markdown."""
    stage_labels = {
        "inbox": "📥 Inbox",
        "backlog": "📋 Backlog",
        "analysis": "🔍 Analysis",
        "active": "⚡ Active",
        "testing": "🧪 Testing",
        "done": "✅ Done",
        "blocked": "🚧 Blocked",
    }
    lines = ["---", "kanban-plugin: board", "---", ""]
    for stage, label in stage_labels.items():
        lines += [f"## {label}", ""]
        for t in store.tickets.values():
            if t.stage != stage:
                continue
            done = "x" if stage == "done" else " "
            prio = " 🔴" if t.priority in ("high", "critical") else ""
            ext = f" [{t.external_id}]" if t.external_id else ""
            sess = f" 🔗{t.session_id[:8]}" if t.session_id else ""
            lines.append(
                f"- [{done}] **{t.id}**{ext} {t.title}{prio}{sess}"
                f" #{t.source}/{t.stage}"
            )
        lines.append("")
    lines += ["", "%% kanban:settings", "```", '{"kanban-plugin":"board"}', "```", "%%"]
    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  WEBSOCKET
# ╚══════════════════════════════════════════════════════════════════════════════
@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws_mgr.connect(ws)

    # Deliver full current state on connect
    await ws.send_json(
        {
            "type": "init",
            "tickets": [t.model_dump(mode="json") for t in store.tickets.values()],
            "sessions": [s.model_dump(mode="json") for s in store.sessions.values()],
            "permissions": [p.model_dump(mode="json") for p in store.perms.values()],
            "reports": [r.model_dump(mode="json") for r in store.reports.values()],
            "logs": [l.model_dump(mode="json") for l in store.get_logs(limit=100)],
            "stats": store.stats(),
        }
    )

    try:
        while True:
            # Accept client-initiated actions over the same socket
            msg = await ws.receive_json()
            match msg.get("type"):
                case "approve":
                    await approve_permission(msg["perm_id"])
                case "deny":
                    await deny_permission(msg["perm_id"])
                case "activate":
                    t = store.tickets.get(msg["ticket_id"])
                    if t and not t.session_id:
                        s = await create_session(t)
                        asyncio.create_task(run_session(s.id))
                case "sync":
                    asyncio.create_task(sync_sources())
                case "analyze":
                    asyncio.create_task(analyze_ticket(msg["ticket_id"]))
    except WebSocketDisconnect:
        ws_mgr.disconnect(ws)
