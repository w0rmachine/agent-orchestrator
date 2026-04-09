"""Tests for environment API with tech stack detection."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

from backend.app import app
from backend.database import get_session


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
def temp_python_repo():
    """Create temporary Python repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)

        # Create requirements.txt
        requirements = repo / "requirements.txt"
        requirements.write_text("fastapi>=0.100.0\nsqlmodel>=0.0.14\npytest>=8.0.0")

        yield str(repo)


@pytest.fixture
def temp_js_repo():
    """Create temporary JavaScript repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)

        # Create package.json
        package_json = repo / "package.json"
        package_json.write_text(json.dumps({
            "name": "test-app",
            "dependencies": {
                "react": "^18.2.0",
                "vite": "^5.0.0",
            }
        }))

        yield str(repo)


def test_create_environment_auto_detects_tech_stack(client: TestClient, temp_python_repo):
    """Test that creating an environment auto-detects tech stack."""
    response = client.post(
        "/environments/",
        json={
            "name": "test-env",
            "repo_path": temp_python_repo,
        }
    )

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "test-env"
    assert data["repo_path"] == temp_python_repo
    assert "tech_stack" in data
    assert "Python" in data["tech_stack"]
    assert "FastAPI" in data["tech_stack"]
    assert "SQLModel" in data["tech_stack"]


def test_create_environment_with_manual_tech_stack(client: TestClient, temp_python_repo):
    """Test creating environment with manually specified tech stack."""
    response = client.post(
        "/environments/",
        json={
            "name": "test-env",
            "repo_path": temp_python_repo,
            "tech_stack": ["Python", "Custom Framework"],
        }
    )

    assert response.status_code == 201
    data = response.json()

    # Should use provided tech stack, not auto-detected
    assert data["tech_stack"] == ["Python", "Custom Framework"]


def test_create_environment_empty_repo(client: TestClient):
    """Test creating environment for repo with no detectable tech."""
    with tempfile.TemporaryDirectory() as tmpdir:
        response = client.post(
            "/environments/",
            json={
                "name": "empty-env",
                "repo_path": tmpdir,
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["tech_stack"] == []


def test_list_environments(client: TestClient, temp_python_repo, temp_js_repo):
    """Test listing environments shows tech stacks."""
    # Create two environments
    client.post(
        "/environments/",
        json={"name": "python-env", "repo_path": temp_python_repo}
    )
    client.post(
        "/environments/",
        json={"name": "js-env", "repo_path": temp_js_repo}
    )

    response = client.get("/environments/")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2

    python_env = next(e for e in data if e["name"] == "python-env")
    assert "Python" in python_env["tech_stack"]
    assert "FastAPI" in python_env["tech_stack"]

    js_env = next(e for e in data if e["name"] == "js-env")
    assert "JavaScript" in js_env["tech_stack"]
    assert "React" in js_env["tech_stack"]


def test_analyze_environment_refreshes_tech_stack(client: TestClient):
    """Test analyzing environment updates tech stack."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)

        # Create environment with no tech stack initially
        response = client.post(
            "/environments/",
            json={"name": "test-env", "repo_path": tmpdir}
        )
        env_id = response.json()["id"]

        # Add requirements.txt after creation
        requirements = repo / "requirements.txt"
        requirements.write_text("django>=4.2.0\npandas>=2.0.0")

        # Analyze to refresh
        response = client.post(f"/environments/{env_id}/analyze")
        assert response.status_code == 200

        data = response.json()
        assert "Python" in data["tech_stack"]
        assert "Django" in data["tech_stack"]
        assert "Pandas" in data["tech_stack"]


def test_update_environment_preserves_tech_stack(client: TestClient, temp_python_repo):
    """Test updating environment preserves tech stack unless explicitly changed."""
    # Create environment
    response = client.post(
        "/environments/",
        json={"name": "test-env", "repo_path": temp_python_repo}
    )
    env_id = response.json()["id"]
    original_tech_stack = response.json()["tech_stack"]

    # Update name only
    response = client.patch(
        f"/environments/{env_id}",
        json={"name": "updated-env"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "updated-env"
    assert data["tech_stack"] == original_tech_stack


def test_update_environment_tech_stack(client: TestClient, temp_python_repo):
    """Test explicitly updating tech stack."""
    # Create environment
    response = client.post(
        "/environments/",
        json={"name": "test-env", "repo_path": temp_python_repo}
    )
    env_id = response.json()["id"]

    # Update tech stack
    response = client.patch(
        f"/environments/{env_id}",
        json={"tech_stack": ["Python", "Flask"]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tech_stack"] == ["Python", "Flask"]


def test_get_environment(client: TestClient, temp_python_repo):
    """Test getting single environment with tech stack."""
    # Create environment
    response = client.post(
        "/environments/",
        json={"name": "test-env", "repo_path": temp_python_repo}
    )
    env_id = response.json()["id"]

    # Get environment
    response = client.get(f"/environments/{env_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == env_id
    assert "Python" in data["tech_stack"]


def test_delete_environment(client: TestClient, temp_python_repo):
    """Test deleting environment."""
    # Create environment
    response = client.post(
        "/environments/",
        json={"name": "test-env", "repo_path": temp_python_repo}
    )
    env_id = response.json()["id"]

    # Delete environment
    response = client.delete(f"/environments/{env_id}")
    assert response.status_code == 204

    # Verify deleted
    response = client.get(f"/environments/{env_id}")
    assert response.status_code == 404


def test_analyze_nonexistent_environment(client: TestClient):
    """Test analyzing non-existent environment returns 404."""
    response = client.post("/environments/00000000-0000-0000-0000-000000000000/analyze")
    assert response.status_code == 404


def test_create_environment_with_git_url(client: TestClient, temp_python_repo):
    """Test creating environment with git URL."""
    response = client.post(
        "/environments/",
        json={
            "name": "test-env",
            "repo_path": temp_python_repo,
            "git_url": "https://github.com/user/repo.git",
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["git_url"] == "https://github.com/user/repo.git"
