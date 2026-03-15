"""Task path model for file associations."""
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class TaskPath(SQLModel, table=True):
    """Task path associations (which files are relevant to a task)."""

    __tablename__ = "task_paths"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    path: str  # e.g. "/backend/services/ai_service.py"
    description: str = ""  # Why this path is relevant
