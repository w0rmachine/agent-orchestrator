"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import backend.app as app_module
import backend.database as db_module
from backend.app import app
from backend.database import get_session


@pytest.fixture(name="test_engine")
def test_engine_fixture():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(test_engine):
    """Create an in-memory SQLite session for testing."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(test_engine, monkeypatch):
    """Create a test client with a database session override."""

    def get_session_override():
        with Session(test_engine) as session:
            yield session

    monkeypatch.setattr(app_module, "engine", test_engine)
    monkeypatch.setattr(db_module, "engine", test_engine)
    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def disable_sync_service(monkeypatch):
    """Disable background sync watcher during API tests."""
    from backend.sync.sync_service import sync_service

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(sync_service, "start", _noop)
    monkeypatch.setattr(sync_service, "stop", _noop)
    monkeypatch.setattr(sync_service, "sync_to_vault", _noop)
    monkeypatch.setattr(sync_service, "_sync_from_vault", _noop)

    from backend.api import tasks as tasks_api

    monkeypatch.setattr(tasks_api, "_sync_markdown", _noop)
