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
        "revision": None,
    }


def test_health_reports_deployed_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    revision = "7fcb79239ad771265dfe3d814c759234c6dd509d"
    settings = Settings(_env_file=None, render_git_commit=revision)
    monkeypatch.setattr("app.api.v1.routes.health.get_settings", lambda: settings)
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["revision"] == revision


@pytest.mark.parametrize("value", ["", "invalid revision", "https://private.example/token"])
def test_health_does_not_expose_invalid_revision(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    from app.core.config import Settings

    settings = Settings(_env_file=None, render_git_commit=value)
    monkeypatch.setattr("app.api.v1.routes.health.get_settings", lambda: settings)
    assert TestClient(app).get("/api/v1/health").json()["revision"] is None


def test_assistant_returns_service_unavailable_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("ERROR", logger="app.operations")
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
    alert_record = next(
        record for record in caplog.records if getattr(record, "event", None) == "operational.alert"
    )
    assert alert_record.alert_category == "ai"
    assert alert_record.alert_event == "ai_provider_failed"
    assert alert_record.route.endswith("/assistant/messages")
