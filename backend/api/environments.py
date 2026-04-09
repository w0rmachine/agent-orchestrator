"""Environment CRUD API."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models.environment import Environment
from backend.repo_analyzer import RepoAnalyzer

router = APIRouter(prefix="/environments", tags=["environments"])


class EnvironmentCreate(BaseModel):
    """Environment creation schema."""

    name: str
    repo_path: str
    git_url: str | None = None
    tech_stack: list[str] = []
    default_branch: str = "main"


class EnvironmentUpdate(BaseModel):
    """Environment update schema."""

    name: str | None = None
    repo_path: str | None = None
    git_url: str | None = None
    tech_stack: list[str] | None = None
    default_branch: str | None = None


@router.get("/")
def list_environments(
    session: Annotated[Session, Depends(get_session)],
) -> list[Environment]:
    """List all environments."""
    environments = session.exec(select(Environment)).all()
    return list(environments)


@router.get("/{environment_id}")
def get_environment(
    environment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> Environment:
    """Get a single environment."""
    environment = session.get(Environment, environment_id)
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    return environment


@router.post("/", status_code=201)
def create_environment(
    data: EnvironmentCreate,
    session: Annotated[Session, Depends(get_session)],
) -> Environment:
    """Create a new environment."""
    # Auto-detect tech stack if not provided
    tech_stack = data.tech_stack
    if not tech_stack:
        analyzer = RepoAnalyzer(data.repo_path)
        tech_stack = analyzer.detect_tech_stack()

    environment = Environment(
        name=data.name,
        repo_path=data.repo_path,
        git_url=data.git_url,
        tech_stack=tech_stack,
        default_branch=data.default_branch,
    )

    session.add(environment)
    session.commit()
    session.refresh(environment)
    return environment


@router.patch("/{environment_id}")
def update_environment(
    environment_id: UUID,
    data: EnvironmentUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> Environment:
    """Update an environment."""
    environment = session.get(Environment, environment_id)
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(environment, field, value)

    session.add(environment)
    session.commit()
    session.refresh(environment)
    return environment


@router.delete("/{environment_id}", status_code=204)
def delete_environment(
    environment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Delete an environment."""
    environment = session.get(Environment, environment_id)
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")

    session.delete(environment)
    session.commit()


@router.post("/{environment_id}/analyze")
def analyze_environment(
    environment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> Environment:
    """Re-analyze environment to update tech stack and file tree."""
    environment = session.get(Environment, environment_id)
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")

    analyzer = RepoAnalyzer(environment.repo_path)
    environment.tech_stack = analyzer.detect_tech_stack()

    session.add(environment)
    session.commit()
    session.refresh(environment)
    return environment
