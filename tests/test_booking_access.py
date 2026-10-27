import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.whatsapp_delivery import recovery_is_available, send_booking_access_code
from app.schemas.booking_access import BookingAccessRequest, normalize_mobile
from app.services.booking_access import (
    BookingAccessService,
    InvalidRecoveryCode,
    RecoveryRateLimited,
)

NOW = datetime(2026, 10, 27, 15, tzinfo=UTC)
PHONE = "5511999999999"


def configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        whatsapp_recovery_enabled=True,
        whatsapp_access_token="test-only",
        whatsapp_phone_number_id="12345",
        whatsapp_api_version="v25.0",
        jwt_secret_key="s" * 32,
    )


@pytest.mark.parametrize("phone", ["(11) 99999-9999", "+55 11 99999-9999", PHONE])
def test_mobile_normalization(phone: str) -> None:
    assert normalize_mobile(phone) == PHONE


@pytest.mark.parametrize(
    "phone", ["1199999999", "551199999999999", "11999999999ext2", "004411999999999"]
)
def test_invalid_phone_is_not_silently_changed(phone: str) -> None:
    with pytest.raises(ValueError):
        normalize_mobile(phone)


def test_code_request_needs_explicit_consent() -> None:
    with pytest.raises(ValidationError):
        BookingAccessRequest(phone=PHONE, consent=False)


def test_recovery_requires_enablement_and_complete_configuration() -> None:
    settings = configured_settings()
    assert recovery_is_available(settings)
    for field, missing in [
        ("whatsapp_recovery_enabled", False),
        ("whatsapp_access_token", ""),
        ("whatsapp_phone_number_id", "../host"),
        ("whatsapp_api_version", ""),
        ("jwt_secret_key", "short"),
        ("whatsapp_auth_template", "../template"),
    ]:
        assert not recovery_is_available(settings.model_copy(update={field: missing}))


def make_service(monkeypatch: pytest.MonkeyPatch) -> tuple[BookingAccessService, SimpleNamespace]:
    monkeypatch.setattr("app.services.booking_access.utc_now", lambda: NOW)
    session = AsyncMock(spec=AsyncSession)
    service = BookingAccessService(session, "test-secret" * 4)
    service._limit = AsyncMock()
    row = SimpleNamespace(
        id=uuid4(),
        business_id=uuid4(),
        attempts=0,
        requests=0,
        window_started_at=NOW,
        last_sent_at=None,
        expires_at=NOW + timedelta(minutes=5),
    )
    row.subject_hash = service.digest("phone", f"{row.business_id}:{PHONE}")
    row.code_hash = service.digest("code", f"{row.id}:123456")
    session.scalars.return_value = Mock(
        one=Mock(return_value=row), one_or_none=Mock(return_value=row)
    )
    service._bookings_for_verified_phone = AsyncMock(return_value=[])
    return service, row


def test_code_is_consumed_before_lookup_and_cannot_be_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, row = make_service(monkeypatch)
    assert asyncio.run(service.verify(row.business_id, PHONE, row.id, "123456", "127.0.0.1")) == []
    assert row.code_hash is None
    service.session.commit.assert_awaited_once()
    with pytest.raises(InvalidRecoveryCode):
        asyncio.run(service.verify(row.business_id, PHONE, row.id, "123456", "127.0.0.1"))
    service._bookings_for_verified_phone.assert_awaited_once_with(row.business_id, PHONE)


@pytest.mark.parametrize("invalid", ["business", "phone", "expiry", "consumed"])
def test_invalid_challenges_never_lookup_reservations(
    invalid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, row = make_service(monkeypatch)
    business_id, phone = row.business_id, PHONE
    if invalid == "business":
        business_id = uuid4()
    elif invalid == "phone":
        phone = "5521999999999"
    elif invalid == "expiry":
        row.expires_at = NOW
    else:
        row.code_hash = None
    with pytest.raises(InvalidRecoveryCode):
        asyncio.run(service.verify(business_id, phone, row.id, "123456", "127.0.0.1"))
    service._bookings_for_verified_phone.assert_not_awaited()


def test_five_wrong_attempts_disable_the_code(monkeypatch: pytest.MonkeyPatch) -> None:
    service, row = make_service(monkeypatch)
    for _ in range(5):
        with pytest.raises(InvalidRecoveryCode):
            asyncio.run(service.verify(row.business_id, PHONE, row.id, "999999", "127.0.0.1"))
    assert row.attempts == 5 and row.code_hash is None
    with pytest.raises(InvalidRecoveryCode):
        asyncio.run(service.verify(row.business_id, PHONE, row.id, "123456", "127.0.0.1"))
    service._bookings_for_verified_phone.assert_not_awaited()


def test_issue_stores_only_hash_and_replaces_old_code(monkeypatch: pytest.MonkeyPatch) -> None:
    service, row = make_service(monkeypatch)
    monkeypatch.setattr("app.services.booking_access.secrets.randbelow", lambda _: 42)
    challenge_id, code = asyncio.run(service.issue(row.business_id, PHONE, "127.0.0.1"))
    assert challenge_id == row.id and code == "000042"
    assert row.code_hash == service.digest("code", f"{row.id}:{code}")
    assert row.code_hash != code and row.requests == 1 and row.attempts == 0
    assert row.expires_at == NOW + timedelta(minutes=5)
    assert not hasattr(row, "phone")


@pytest.mark.parametrize("cooldown", [True, False])
def test_phone_resend_and_hourly_limits_are_committed(
    cooldown: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, row = make_service(monkeypatch)
    row.last_sent_at = NOW if cooldown else NOW - timedelta(minutes=2)
    row.requests = 5
    with pytest.raises(RecoveryRateLimited) as caught:
        asyncio.run(service.issue(row.business_id, PHONE, "127.0.0.1"))
    assert caught.value.seconds == (60 if cooldown else 3600)
    service.session.commit.assert_awaited_once()


def test_ip_throttle_uses_shared_locked_state(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = make_service(monkeypatch)
    del service._limit
    bucket = SimpleNamespace(requests=10, window_started_at=NOW)
    service.session.scalars.return_value = Mock(one=Mock(return_value=bucket))
    with pytest.raises(RecoveryRateLimited):
        asyncio.run(service._limit("issue-ip:127.0.0.1", 10, 15))
    statement = str(service.session.scalars.await_args.args[0])
    assert "FOR UPDATE" in statement
    service.session.commit.assert_awaited_once()


def test_meta_request_uses_authentication_template_without_real_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"messages": [{"id": "test"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr("app.integrations.whatsapp_delivery.httpx.AsyncClient", lambda **_: client)
    asyncio.run(
        send_booking_access_code(settings=configured_settings(), phone=PHONE, code="123456")
    )
    payload = json.loads(captured[0].content)
    assert captured[0].url.host == "graph.facebook.com"
    assert payload["to"] == PHONE and payload["type"] == "template"
    assert payload["template"]["components"][0]["parameters"][0]["text"] == "123456"
    assert payload["template"]["components"][1]["parameters"][0]["text"] == "123456"
