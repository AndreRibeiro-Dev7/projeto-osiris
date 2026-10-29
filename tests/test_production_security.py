"""Production-only documentation and browser controls, without database access."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.mark.parametrize("debug", [False, True])
def test_production_documentation_is_closed_and_responses_are_protected(
    monkeypatch: pytest.MonkeyPatch, debug: bool
) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=debug,
        email_delivery_enabled=False,
        discord_alert_webhook_url="",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.v1.routes.health.get_settings", lambda: settings)
    # Avoid changing the process-global logging setup of the other tests.
    monkeypatch.setattr("app.main.configure_logging", lambda **kwargs: None)
    application = create_app()
    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None
    with TestClient(application, base_url="https://production.test") as client:
        for path, status in [
            ("/api/v1/health", 200),
            ("/dashboard/", 200),
            ("/api/v1/auth/me", 401),
            ("/docs", 404),
            ("/docs/oauth2-redirect", 404),
            ("/redoc", 404),
            ("/openapi.json", 404),
            ("/missing", 404),
        ]:
            response = client.get(path)
            assert response.status_code == status, path
            assert response.headers["strict-transport-security"] == (
                "max-age=31536000; includeSubDomains"
            )
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["x-frame-options"] == "DENY"
            assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
            assert response.headers["permissions-policy"] == (
                "camera=(), microphone=(), geolocation=(), payment=()"
            )
            policy = {
                parts[0]: parts[1:]
                for directive in response.headers["content-security-policy"].split(";")
                if (parts := directive.split())
            }
            for directive, allowed in {
                "frame-ancestors": ["'none'"],
                "object-src": ["'none'"],
                "script-src": ["'self'"],
                "connect-src": ["'self'"],
                "form-action": ["'self'"],
            }.items():
                assert policy[directive] == allowed
            assert response.headers["x-request-id"]
            if status == 404:
                assert response.json() == {"detail": "Not Found"}
            if status == 401:
                assert response.headers["www-authenticate"] == "Bearer"


def test_development_documentation_remains_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        email_delivery_enabled=False,
        discord_alert_webhook_url="",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.configure_logging", lambda **kwargs: None)
    with TestClient(create_app()) as client:
        for path in ["/docs", "/redoc", "/openapi.json"]:
            response = client.get(path)
            assert response.status_code == 200
            assert "strict-transport-security" not in response.headers
