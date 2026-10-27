"""A missing mail provider must never expose recovery codes in production."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routes import auth
from app.core.config import Settings
from app.schemas.auth import (
    EmailChangeConfirmRequest,
    EmailChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
)


@pytest.mark.parametrize("environment", ["production", "PRODUCTION", "staging"])
@pytest.mark.parametrize("email_enabled,key", [(False, ""), (False, "test-only"), (True, "")])
def test_unconfigured_mail_never_generates_inline_codes_outside_development(
    environment: str, email_enabled: bool, key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None,
        environment=environment,
        email_delivery_enabled=email_enabled,
        resend_api_key=key,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    generate_reset = AsyncMock()
    generate_email = AsyncMock()
    monkeypatch.setattr(auth.AuthService, "request_password_reset", generate_reset)
    monkeypatch.setattr(auth.AuthService, "request_email_change", generate_email)
    session = AsyncMock(spec=AsyncSession)
    with pytest.raises(HTTPException) as reset:
        asyncio.run(
            auth.request_password_reset(
                Request({"type": "http"}), PasswordResetRequest(email="test@example.com"), session
            )
        )
    assert reset.value.status_code == 503
    with pytest.raises(HTTPException) as email:
        asyncio.run(
            auth.request_email_change(
                EmailChangeRequest(current_password="test-only", new_email="new@example.com"),
                SimpleNamespace(role="owner"),
                session,
            )
        )
    assert email.value.status_code == 503
    with pytest.raises(HTTPException) as confirm_reset:
        asyncio.run(
            auth.confirm_password_reset(
                PasswordResetConfirmRequest(
                    email="test@example.com",
                    code="123456",
                    new_password="Fictitious-password-123!",
                    password_confirmation="Fictitious-password-123!",
                ),
                session,
            )
        )
    assert confirm_reset.value.status_code == 503
    with pytest.raises(HTTPException) as confirm_email:
        asyncio.run(
            auth.confirm_email_change(
                EmailChangeConfirmRequest(code="123456"),
                SimpleNamespace(role="owner"),
                session,
            )
        )
    assert confirm_email.value.status_code == 503
    generate_reset.assert_not_awaited()
    generate_email.assert_not_awaited()


@pytest.mark.parametrize("environment,delivery", [("development", False), ("production", True)])
def test_inline_recovery_code_is_only_allowed_in_development(
    environment: str, delivery: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None,
        environment=environment,
        email_delivery_enabled=delivery,
        resend_api_key="test-only" if delivery else "",
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    generate = AsyncMock(return_value=("test@example.com", "123456"))
    send = AsyncMock()
    monkeypatch.setattr(auth.AuthService, "request_password_reset", generate)
    monkeypatch.setattr(auth, "send_password_reset_code", send)
    result = asyncio.run(
        auth.request_password_reset(
            Request({"type": "http"}),
            PasswordResetRequest(email="test@example.com"),
            AsyncMock(spec=AsyncSession),
        )
    )
    assert result.development_code == ("123456" if environment == "development" else None)
    assert send.await_count == int(delivery)
