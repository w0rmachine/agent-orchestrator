"""Tests for context-aware task suggestions."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

from backend.app import app
from backend.database import get_session
from backend.models.environment import Environment
from backend.models.task import Task, TaskStatus


@pytest.fixture(name="session")
def session_fixture():
    """Create test database session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create test client with database dependency override."""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_environment(session: Session):
    """Create a test environment."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = Environment(
            name="test-repo",
            repo_path=tmpdir,
            tech_stack=["Python", "FastAPI"],
        )
        session.add(env)
        session.commit()
        session.refresh(env)
        yield env


def test_suggest_tasks_by_repo_path(client: TestClient, test_environment: Environment, session: Session):
    """Test suggesting tasks for a specific repository."""
    # Create tasks for the environment
    tasks = [
        Task(
            task_code="T-001",
            title="High priority runway task",
            status=TaskStatus.RUNWAY,
            priority=1,
            environment_id=test_environment.id,
        ),
        Task(
            task_code="T-002",
            title="Low priority runway task",
            status=TaskStatus.RUNWAY,
            priority=3,
            environment_id=test_environment.id,
        ),
        Task(
            task_code="T-003",
            title="Radar task",
            status=TaskStatus.RADAR,
            priority=2,
            environment_id=test_environment.id,
        ),
        Task(
            task_code="T-004",
            title="Flight task",
            status=TaskStatus.FLIGHT,
            priority=1,
            environment_id=test_environment.id,
        ),
        Task(
            task_code="T-005",
            title="Blocked task (should not appear)",
            status=TaskStatus.BLOCKED,
            priority=1,
            environment_id=test_environment.id,
        ),
        Task(
            task_code="T-006",
            title="Done task (should not appear)",
            status=TaskStatus.DONE,
            priority=1,
            environment_id=test_environment.id,
        ),
    ]

    for task in tasks:
        session.add(task)
    session.commit()

    # Request suggestions
    response = client.get(
        "/tasks/suggest",
        params={"repo_path": test_environment.repo_path}
    )

    assert response.status_code == 200
    suggestions = response.json()

    # Should return 4 tasks (exclude BLOCKED and DONE)
    assert len(suggestions) == 4

    # Check ordering: RUNWAY tasks first, ordered by priority
    codes = [t["task_code"] for t in suggestions]
    assert codes[0] == "T-001"  # RUNWAY, priority 1
    assert codes[1] == "T-002"  # RUNWAY, priority 3
    assert codes[2] == "T-003"  # RADAR, priority 2
    assert codes[3] == "T-004"  # FLIGHT, priority 1


def test_suggest_tasks_with_limit(client: TestClient, test_environment: Environment, session: Session):
    """Test limiting number of suggestions."""
    # Create 10 tasks
    for i in range(10):
        task = Task(
            task_code=f"T-{i:03d}",
            title=f"Task {i}",
            status=TaskStatus.RUNWAY,
            environment_id=test_environment.id,
        )
        session.add(task)
    session.commit()

    # Request only 3 suggestions
    response = client.get(
        "/tasks/suggest",
        params={"repo_path": test_environment.repo_path, "limit": 3}
    )

    assert response.status_code == 200
    suggestions = response.json()
    assert len(suggestions) == 3


def test_suggest_tasks_no_environment(client: TestClient, session: Session):
    """Test suggestions when repository has no environment."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a task with no environment
        task = Task(
            task_code="T-GLOBAL",
            title="Global task",
            status=TaskStatus.RUNWAY,
            environment_id=None,
        )
        session.add(task)
        session.commit()

        # Request suggestions for unregistered repo
        response = client.get(
            "/tasks/suggest",
            params={"repo_path": tmpdir}
        )

        assert response.status_code == 200
        suggestions = response.json()

        # Should return global tasks (no environment_id)
        assert len(suggestions) == 1
        assert suggestions[0]["task_code"] == "T-GLOBAL"


def test_suggest_tasks_empty(client: TestClient, test_environment: Environment, session: Session):
    """Test suggestions when no tasks match."""
    # Only create DONE tasks
    task = Task(
        task_code="T-DONE",
        title="Completed task",
        status=TaskStatus.DONE,
        environment_id=test_environment.id,
    )
    session.add(task)
    session.commit()

    response = client.get(
        "/tasks/suggest",
        params={"repo_path": test_environment.repo_path}
    )

    assert response.status_code == 200
    suggestions = response.json()
    assert len(suggestions) == 0


def test_suggest_tasks_path_normalization(client: TestClient, session: Session):
    """Test that repo paths are normalized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir).resolve()

        env = Environment(
            name="test",
            repo_path=str(repo_path),
            tech_stack=[],
        )
        session.add(env)

        task = Task(
            task_code="T-001",
            title="Test task",
            status=TaskStatus.RUNWAY,
            environment_id=env.id,
        )
        session.add(task)
        session.commit()

        # Request with different path representations
        # All should normalize to the same path
        for path_variant in [str(repo_path), str(repo_path) + "/"]:
            response = client.get(
                "/tasks/suggest",
                params={"repo_path": path_variant}
            )
            assert response.status_code == 200
            suggestions = response.json()
            assert len(suggestions) == 1


def test_suggest_tasks_priority_ordering(client: TestClient, test_environment: Environment, session: Session):
    """Test that tasks are ordered by priority within same status."""
    tasks = [
        Task(task_code="T-P1", title="Priority 1", status=TaskStatus.RUNWAY, priority=1, environment_id=test_environment.id),
        Task(task_code="T-P2", title="Priority 2", status=TaskStatus.RUNWAY, priority=2, environment_id=test_environment.id),
        Task(task_code="T-P5", title="Priority 5", status=TaskStatus.RUNWAY, priority=5, environment_id=test_environment.id),
        Task(task_code="T-PN", title="No priority", status=TaskStatus.RUNWAY, priority=None, environment_id=test_environment.id),
    ]

    for task in tasks:
        session.add(task)
    session.commit()

    response = client.get(
        "/tasks/suggest",
        params={"repo_path": test_environment.repo_path}
    )

    suggestions = response.json()
    codes = [t["task_code"] for t in suggestions]

    # Lower priority number = higher priority
    # Tasks without priority should come last
    assert codes == ["T-P1", "T-P2", "T-P5", "T-PN"]


def test_suggest_tasks_includes_estimated_time(client: TestClient, test_environment: Environment, session: Session):
    """Test that suggestions include time estimates."""
    task = Task(
        task_code="T-001",
        title="Task with estimate",
        status=TaskStatus.RUNWAY,
        estimated_minutes=120,
        environment_id=test_environment.id,
    )
    session.add(task)
    session.commit()

    response = client.get(
        "/tasks/suggest",
        params={"repo_path": test_environment.repo_path}
    )

    suggestions = response.json()
    assert len(suggestions) == 1
    assert suggestions[0]["estimated_minutes"] == 120


def test_suggest_tasks_missing_repo_path(client: TestClient):
    """Test that repo_path is required."""
    response = client.get("/tasks/suggest")
    assert response.status_code == 422  # Validation error


def test_suggest_tasks_invalid_limit(client: TestClient):
    """Test that limit must be within bounds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Limit too high
        response = client.get(
            "/tasks/suggest",
            params={"repo_path": tmpdir, "limit": 100}
        )
        assert response.status_code == 422

        # Limit too low
        response = client.get(
            "/tasks/suggest",
            params={"repo_path": tmpdir, "limit": 0}
        )
        assert response.status_code == 422
