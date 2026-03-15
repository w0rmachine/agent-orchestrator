"""Environment model for repo tracking."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Column, Field, JSON, SQLModel


class Environment(SQLModel, table=True):
    """Environment (repository) model."""

    __tablename__ = "environments"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)  # e.g. "ai-kanban"
    repo_path: str  # e.g. "~/repos/ai-kanban"
    git_url: str | None = None  # Remote URL
    tech_stack: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    default_branch: str = "main"

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
