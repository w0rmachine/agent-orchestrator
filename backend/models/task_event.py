"""Task event model."""
import enum
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Column, Enum, Field, JSON, SQLModel


class TaskEventType(str, enum.Enum):
    """Task event types."""

    TASK_CREATED = "task_created"
    TASK_SPLIT = "task_split"
    TASK_MOVED = "task_moved"
    TASK_DONE = "task_done"
    TASK_BLOCKED = "task_blocked"
    TASK_TAGGED = "task_tagged"
    TASK_PRIORITIZED = "task_prioritized"


class TaskEvent(SQLModel, table=True):
    """Task event log."""

    __tablename__ = "task_events"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    event_type: TaskEventType = Field(
        sa_column=Column(Enum(TaskEventType), nullable=False)
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON))
