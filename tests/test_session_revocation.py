import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.security import hash_password
from app.services.auth import AuthService


def test_revoke_all_sessions_increments_credential_version() -> None:
    user = SimpleNamespace(password_hash=hash_password("senha-atual-forte-123"), auth_version=4)
    commit = AsyncMock()
    service = AuthService.__new__(AuthService)
    service._session = SimpleNamespace(commit=commit)

    revoked = asyncio.run(
        service.revoke_all_sessions(user=user, current_password="senha-atual-forte-123")
    )

    assert revoked
    assert user.auth_version == 5
    commit.assert_awaited_once()


def test_revoke_all_sessions_rejects_incorrect_password() -> None:
    user = SimpleNamespace(password_hash=hash_password("senha-atual-forte-123"), auth_version=4)
    commit = AsyncMock()
    service = AuthService.__new__(AuthService)
    service._session = SimpleNamespace(commit=commit)

    revoked = asyncio.run(
        service.revoke_all_sessions(user=user, current_password="senha-incorreta")
    )

    assert not revoked
    assert user.auth_version == 4
    commit.assert_not_awaited()
