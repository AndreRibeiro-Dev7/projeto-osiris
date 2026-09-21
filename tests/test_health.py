from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import require_business_access
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


def test_assistant_returns_service_unavailable_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[require_business_access] = lambda: None
    monkeypatch.setattr(
        "app.api.v1.routes.businesses.get_settings",
        lambda: SimpleNamespace(openai_api_key="", openai_model="gpt-5.6-luna"),
    )
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/businesses/b932827e-a7b0-46b2-9d9e-d30419f89777/assistant/messages",
            json={
                "barber_id": "0d15a1e1-31bd-437d-809f-71cfbe12569e",
                "appointment_date": "2026-09-07",
                "message": "Tem horário pela manhã?",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "OPENAI_API_KEY is not configured."}
