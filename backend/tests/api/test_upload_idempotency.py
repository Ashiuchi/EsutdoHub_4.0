import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_upload_returns_existing_edital_when_hash_found():
    """Second upload of same file returns existing edital without queuing a background task."""
    existing_id = uuid.uuid4()
    existing_hash = "a" * 64

    existing = MagicMock()
    existing.id = existing_id
    existing.content_hash = existing_hash
    existing.status = "processado"

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = existing

    with patch("app.api.endpoints.SessionLocal", return_value=mock_db), \
         patch("app.api.endpoints._compute_hash", return_value=existing_hash):
        response = client.post(
            "/api/v1/upload",
            files={"file": ("edital.pdf", b"%PDF-1.4 test", "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["content_hash"] == existing_hash
    assert data["status"] == "processado"
    assert str(data["id"]) == str(existing_id)
    mock_db.query.assert_called_once()


def test_upload_processes_new_file_when_hash_not_found():
    """Upload of a file not yet in DB queues a background task and returns 'processando'."""
    from unittest.mock import AsyncMock
    from fastapi import BackgroundTasks

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None

    scheduled_tasks = []

    original_add_task = BackgroundTasks.add_task

    def capture_add_task(self, func, *args, **kwargs):
        scheduled_tasks.append(func)
        # Don't actually run it — avoid hitting Ollama in tests
        pass

    with patch("app.api.endpoints.SessionLocal", return_value=mock_db), \
         patch.object(BackgroundTasks, "add_task", capture_add_task):
        response = client.post(
            "/api/v1/upload",
            files={"file": ("edital.pdf", b"%PDF-1.4 new", "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processando"
    assert len(scheduled_tasks) == 1, "Expected exactly one background task to be scheduled"
