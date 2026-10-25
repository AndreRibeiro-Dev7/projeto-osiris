from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import require_primary_owner
from app.main import app


def test_primary_owner_can_send_safe_delivery_test(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_dispatch(alert: object, **kwargs: object) -> bool:
        captured["alert"] = alert
        captured.update(kwargs)
        return True

    app.dependency_overrides[require_primary_owner] = lambda: SimpleNamespace(
        role="owner",
        is_primary_owner=True,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.operational_alerts.dispatch_operational_alert",
        fake_dispatch,
    )
    client = TestClient(app)

    try:
        response = client.post("/api/v1/operational-alerts/test")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    alert = captured["alert"]
    assert alert.category == "integration"
    assert alert.event == "delivery_test"
    assert alert.severity == "info"
    assert captured["deduplicate"] is False


def test_delivery_failure_is_reported_to_primary_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_dispatch(alert: object, **kwargs: object) -> bool:
        return False

    app.dependency_overrides[require_primary_owner] = lambda: SimpleNamespace(
        role="owner",
        is_primary_owner=True,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.operational_alerts.dispatch_operational_alert",
        fake_dispatch,
    )
    client = TestClient(app)

    try:
        response = client.post("/api/v1/operational-alerts/test")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Discord alert could not be delivered."}
