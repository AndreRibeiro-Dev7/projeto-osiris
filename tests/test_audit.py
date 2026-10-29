import asyncio
import logging
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.main import create_app
from app.models.user import User
from app.services.audit import describe_activity, record_activity


def test_audit_describes_owner_account_deletion() -> None:
    area, description = describe_activity("DELETE", "/api/v1/auth/owner-accounts/123")

    assert area == "Contas"
    assert description == "Excluiu o acesso de um coproprietário"


def test_audit_describes_expense_payment() -> None:
    area, description = describe_activity("PATCH", "/api/v1/businesses/123/expenses/456/paid")

    assert area == "Financeiro"
    assert description == "Confirmou o pagamento de uma despesa"


def test_audit_describes_appointment_completion() -> None:
    area, description = describe_activity(
        "PATCH", "/api/v1/businesses/123/appointments/456/complete"
    )

    assert area == "Agenda"
    assert description == "Concluiu um atendimento"


def test_audit_describes_operational_alert_test() -> None:
    area, description = describe_activity("POST", "/api/v1/operational-alerts/test")

    assert area == "Configurações"
    assert description == "Enviou um alerta de teste ao Discord"


@pytest.mark.parametrize(
    ("resource", "area", "description"),
    [
        ("barbers/456/schedule/0", "Equipe", "Removeu um dia da jornada de um profissional"),
        ("barbers/456/time-off/789", "Equipe", "Removeu uma folga de profissional"),
        ("expenses/456", "Financeiro", "Excluiu uma despesa"),
    ],
)
def test_audit_describes_deletions(resource: str, area: str, description: str) -> None:
    assert describe_activity("DELETE", f"/api/v1/businesses/123/{resource}") == (
        area,
        description,
    )


def test_assistant_query_does_not_pretend_to_be_a_mutation() -> None:
    session = AsyncMock(spec=AsyncSession)
    user = User(
        id=uuid4(),
        business_id=uuid4(),
        email="test@example.com",
        role="owner",
        is_primary_owner=True,
    )
    path = "/api/v1/businesses/123/assistant/messages"
    assert describe_activity("POST", path) is None
    asyncio.run(record_activity(session, user=user, method="POST", path=path))
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    asyncio.run(
        record_activity(
            session,
            user=user,
            method="POST",
            path=path,
            activity=("Agenda", "Confirmou um agendamento pelo assistente"),
        )
    )
    session.add.assert_called_once()
    log = session.add.call_args.args[0]
    assert log.actor_user_id == user.id
    assert log.area == "Agenda" and "assistente" in log.description
    session.commit.assert_awaited_once()


@pytest.mark.parametrize("alert_fails", [False, True])
def test_audit_failure_preserves_saved_response_and_logs_no_exception_data(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    alert_fails: bool,
) -> None:
    settings = Settings(_env_file=None, environment="development", discord_alert_webhook_url="")
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.configure_logging", lambda **kwargs: None)
    caplog.set_level(logging.ERROR)
    sensitive = "private-sentinel@example.com token=private-sentinel-token"
    record = AsyncMock(side_effect=RuntimeError(sensitive))
    monkeypatch.setattr("app.main.record_activity", record)
    # Session factories return asynchronous context managers synchronously.
    from unittest.mock import MagicMock

    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=AsyncMock(spec=AsyncSession))
    manager.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("app.main.async_session_factory", lambda: manager)
    delivery = AsyncMock(
        side_effect=RuntimeError(sensitive) if alert_fails else None, return_value=False
    )
    monkeypatch.setattr("app.main.dispatch_operational_alert", delivery)
    application = create_app()

    @application.post("/audit-test/{item_id}", status_code=201)
    async def saved(request: Request) -> dict[str, bool]:
        request.state.current_user = User(
            id=uuid4(),
            business_id=uuid4(),
            email="actor@example.com",
            role="owner",
            is_primary_owner=True,
        )
        return {"saved": True}

    response = TestClient(application).post("/audit-test/123")
    assert response.status_code == 201 and response.json() == {"saved": True}
    delivery.assert_awaited_once()
    alert = delivery.call_args.args[0]
    assert alert.event == "audit_persistence_failed"
    assert alert.route == "/audit-test/{item_id}"
    assert delivery.call_args.kwargs["request_id"] == response.headers["x-request-id"]
    failures = [r for r in caplog.records if getattr(r, "event", "").startswith("audit.")]
    assert len(failures) == (2 if alert_fails else 1)
    assert all(record.exc_info is None for record in failures)
    assert "private-sentinel" not in caplog.text
