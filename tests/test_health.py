from fastapi.testclient import TestClient

from app.main import app


def test_health_check_returns_application_status() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "application": "Projeto Osiris",
        "version": "0.1.0",
    }
