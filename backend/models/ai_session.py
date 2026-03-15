"""AI session models."""
import enum
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Column, Enum, Field, JSON, SQLModel


class AISessionStatus(str, enum.Enum):
    """AI session status."""

    RUNNING = "running"
    PAUSED = "paused"
    ACTION_REQUIRED = "action_required"
    COMPLETE = "complete"


class AISession(SQLModel, table=True):
    """AI session for task execution (Phase 6)."""

    __tablename__ = "ai_sessions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    model: str  # Model used (e.g. "claude-sonnet-4-6")
    status: AISessionStatus = Field(
        sa_column=Column(Enum(AISessionStatus), nullable=False),
        default=AISessionStatus.RUNNING,
    )
    conversation_history: dict = Field(default_factory=dict, sa_column=Column(JSON))

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    summary: str = ""


class LogLevel(str, enum.Enum):
    """Log level enum."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AILog(SQLModel, table=True):
    """AI log entry."""

    __tablename__ = "ai_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="ai_sessions.id", index=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    log_message: str
    log_level: LogLevel = Field(
        sa_column=Column(Enum(LogLevel), nullable=False),
        default=LogLevel.INFO,
    )
