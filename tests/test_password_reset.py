import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.security import hash_password, verify_password
from app.services.auth import AuthService


def make_service(user: SimpleNamespace | None) -> tuple[AuthService, AsyncMock]:
    service = AuthService.__new__(AuthService)
    commit = AsyncMock()
    service._session = SimpleNamespace(commit=commit)
    service._users = SimpleNamespace(get_by_email_for_update=AsyncMock(return_value=user))
    return service, commit


def make_owner() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        email="dono@osiris.com",
        role="owner",
        is_active=True,
        password_hash=hash_password("senha-antiga-forte-123"),
        password_reset_code_hash=None,
        password_reset_expires_at=None,
        password_reset_requested_at=None,
        password_reset_attempts=0,
        auth_version=0,
    )


def test_password_reset_request_ignores_barber_accounts() -> None:
    barber = make_owner()
    barber.role = "barber"
    service, commit = make_service(barber)

    result = asyncio.run(service.request_password_reset(email=barber.email))

    assert result is None
    commit.assert_not_awaited()


def test_expired_recovery_code_cannot_change_password() -> None:
    owner = make_owner()
    service, commit = make_service(owner)
    owner.password_reset_code_hash = service._password_reset_code_hash(owner.id, "123456")
    owner.password_reset_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    changed = asyncio.run(
        service.confirm_password_reset(
            email=owner.email,
            code="123456",
            new_password="new-fictitious-password-123!",
        )
    )
    assert not changed and owner.auth_version == 0
    assert verify_password("senha-antiga-forte-123", owner.password_hash)
    commit.assert_not_awaited()


def test_password_reset_code_is_single_use_and_revokes_sessions() -> None:
    owner = make_owner()
    service, commit = make_service(owner)
    destination, code = asyncio.run(service.request_password_reset(email=owner.email)) or ("", "")

    assert destination == owner.email
    assert code.isdigit() and len(code) == 6
    owner.password_reset_requested_at = datetime.now(UTC)
    changed = asyncio.run(
        service.confirm_password_reset(
            email=owner.email,
            code=code,
            new_password="senha-nova-forte-456",
        )
    )

    assert changed
    assert verify_password("senha-nova-forte-456", owner.password_hash)
    assert owner.auth_version == 1
    assert owner.password_reset_code_hash is None
    assert owner.password_reset_expires_at is None
    assert commit.await_count == 2
