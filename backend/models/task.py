"""Task model."""
import enum
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Column, Enum, Field, JSON, SQLModel


class TaskStatus(str, enum.Enum):
    """Task status enum matching Kanban columns."""

    RADAR = "radar"
    RUNWAY = "runway"
    FLIGHT = "flight"
    BLOCKED = "blocked"
    DONE = "done"


class Task(SQLModel, table=True):
    """Task model with AI analysis fields."""

    __tablename__ = "tasks"

    # Primary fields
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_code: str = Field(index=True, unique=True)  # e.g. TASK-001, TASK-001-A
    title: str
    description: str = ""

    # Status and priority
    status: TaskStatus = Field(
        sa_column=Column(Enum(TaskStatus), nullable=False, index=True),
        default=TaskStatus.RADAR,
    )
    priority: int | None = Field(default=None, ge=1, le=5)  # 1-5, AI-assigned

    # Tags stored as JSON arrays
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    location_tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Environment relationship (foreign key only, no ORM relationship for simplicity)
    environment_id: UUID | None = Field(default=None, foreign_key="environments.id")

    # Parent-child relationship for subtasks (foreign key only)
    parent_task_id: UUID | None = Field(default=None, foreign_key="tasks.id")

    # AI-generated metadata
    ai_generated: bool = False
    estimated_minutes: int | None = None

    # Sync metadata
    file_hash: str | None = None  # Hash of last written markdown state
    order: int = 0  # Position in markdown file
    source: str = Field(default="manual", index=True)
    external_id: str | None = Field(default=None, index=True)
    external_url: str | None = None
    external_project: str | None = Field(default=None, index=True)
    external_updated_at: datetime | None = None
    external_deleted: bool = False

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
