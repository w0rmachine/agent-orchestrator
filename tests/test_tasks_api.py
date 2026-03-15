"""Tests for Task API."""
from fastapi.testclient import TestClient


def test_create_task(client: TestClient):
    """Test task creation."""
    response = client.post(
        "/tasks/",
        json={
            "task_code": "TASK-001",
            "title": "Test task",
            "description": "Test description",
            "status": "radar",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["task_code"] == "TASK-001"
    assert data["title"] == "Test task"
    assert data["status"] == "radar"


def test_list_tasks(client: TestClient):
    """Test listing tasks."""
    # Create a task first
    client.post(
        "/tasks/",
        json={
            "task_code": "TASK-002",
            "title": "Test task 2",
            "status": "radar",
        },
    )

    # List tasks
    response = client.get("/tasks/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["task_code"] == "TASK-002"


def test_get_task(client: TestClient):
    """Test getting a single task."""
    # Create a task
    create_response = client.post(
        "/tasks/",
        json={
            "task_code": "TASK-003",
            "title": "Test task 3",
            "status": "radar",
        },
    )
    task_id = create_response.json()["id"]

    # Get the task
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["task_code"] == "TASK-003"


def test_update_task(client: TestClient):
    """Test updating a task."""
    # Create a task
    create_response = client.post(
        "/tasks/",
        json={
            "task_code": "TASK-004",
            "title": "Test task 4",
            "status": "radar",
        },
    )
    task_id = create_response.json()["id"]

    # Update the task
    response = client.patch(
        f"/tasks/{task_id}",
        json={
            "title": "Updated title",
            "status": "runway",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["status"] == "runway"


def test_move_task(client: TestClient):
    """Test moving a task to a different status."""
    # Create a task
    create_response = client.post(
        "/tasks/",
        json={
            "task_code": "TASK-005",
            "title": "Test task 5",
            "status": "radar",
        },
    )
    task_id = create_response.json()["id"]

    # Move to runway
    response = client.post(f"/tasks/{task_id}/move?status=runway")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "runway"


def test_delete_task(client: TestClient):
    """Test deleting a task."""
    # Create a task
    create_response = client.post(
        "/tasks/",
        json={
            "task_code": "TASK-006",
            "title": "Test task 6",
            "status": "radar",
        },
    )
    task_id = create_response.json()["id"]

    # Delete the task
    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 204

    # Verify it's deleted
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 404


def test_duplicate_task_code(client: TestClient):
    """Test that duplicate task codes are rejected."""
    # Create a task
    client.post(
        "/tasks/",
        json={
            "task_code": "TASK-007",
            "title": "Test task 7",
            "status": "radar",
        },
    )

    # Try to create another task with the same code
    response = client.post(
        "/tasks/",
        json={
            "task_code": "TASK-007",
            "title": "Duplicate task",
            "status": "radar",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]
