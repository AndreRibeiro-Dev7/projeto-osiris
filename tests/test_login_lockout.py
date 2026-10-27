import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.exceptions import LoginTemporarilyLockedError
from app.core.security import hash_password
from app.services.auth import LOGIN_MAX_FAILED_ATTEMPTS, AuthService


def make_service(user: SimpleNamespace) -> tuple[AuthService, AsyncMock]:
    service = AuthService.__new__(AuthService)
    commit = AsyncMock()
    service._session = SimpleNamespace(commit=commit)
    service._users = SimpleNamespace(get_by_email_for_update=AsyncMock(return_value=user))
    service._barbers = SimpleNamespace(get_by_id=AsyncMock())
    return service, commit


def make_owner() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        email="dono@osiris.com",
        role="owner",
        is_active=True,
        password_hash=hash_password("senha-correta-forte-123"),
        login_failed_attempts=0,
        login_locked_until=None,
    )


def test_fifth_invalid_password_temporarily_locks_account() -> None:
    owner = make_owner()
    service, commit = make_service(owner)

    for _ in range(LOGIN_MAX_FAILED_ATTEMPTS - 1):
        assert (
            asyncio.run(service.authenticate(email=owner.email, password="senha-incorreta")) is None
        )
    try:
        asyncio.run(service.authenticate(email=owner.email, password="senha-incorreta"))
    except LoginTemporarilyLockedError as error:
        assert 899 <= error.retry_after_seconds <= 900
    else:
        raise AssertionError("The fifth invalid login must report the temporary lockout")

    assert owner.login_failed_attempts == 0
    assert owner.login_locked_until is not None
    assert owner.login_locked_until > datetime.now(UTC)
    assert commit.await_count == LOGIN_MAX_FAILED_ATTEMPTS


def test_correct_password_is_rejected_during_lockout() -> None:
    owner = make_owner()
    owner.login_locked_until = datetime.now(UTC) + timedelta(minutes=10)
    service, commit = make_service(owner)

    try:
        asyncio.run(service.authenticate(email=owner.email, password="senha-correta-forte-123"))
    except LoginTemporarilyLockedError as error:
        assert 599 <= error.retry_after_seconds <= 600
    else:
        raise AssertionError("A locked account must report the remaining wait")
    commit.assert_not_awaited()


def test_successful_login_after_expiry_clears_lockout() -> None:
    owner = make_owner()
    owner.login_failed_attempts = 3
    owner.login_locked_until = datetime.now(UTC) - timedelta(seconds=1)
    service, commit = make_service(owner)

    authenticated = asyncio.run(
        service.authenticate(email=owner.email, password="senha-correta-forte-123")
    )

    assert authenticated is owner
    assert owner.login_failed_attempts == 0
    assert owner.login_locked_until is None
    commit.assert_awaited_once()
