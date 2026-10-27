"""Authentication journey with real PostgreSQL; mail delivery is simulated."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py against disposable PostgreSQL.",
)


def test_authentication_database(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(check_authentication(monkeypatch))


async def check_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.engine import make_url

    target = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(target)
    assert url.host == "127.0.0.1" and url.database
    assert url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == target

    import httpx

    from app.core.config import get_settings
    from app.core.security import hash_password
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.barber import Barber
    from app.models.business import Business
    from app.models.user import User

    settings = get_settings()
    for field, value in {
        "environment": "production",
        "email_delivery_enabled": True,
        "resend_api_key": "test-only",
        "discord_alert_webhook_url": "",
    }.items():
        monkeypatch.setattr(settings, field, value)
    send = AsyncMock()
    monkeypatch.setattr("app.api.v1.routes.auth.send_password_reset_code", send)
    password, new_password = "Fictitious-auth-password-123!", "Fictitious-new-password-456!"
    business_id, barber_id = uuid4(), uuid4()
    identities = {}
    try:
        async with async_session_factory() as session:
            session.add(
                Business(id=business_id, name="Authentication test", phone=uuid4().hex[:20])
            )
            await session.flush()
            session.add(
                Barber(id=barber_id, business_id=business_id, full_name="Test barber", phone="111")
            )
            await session.flush()
            encoded = hash_password(password)
            for role in ("principal", "coowner", "barber"):
                user = User(
                    id=uuid4(),
                    business_id=business_id,
                    email=f"{role}-{uuid4().hex}@example.com",
                    password_hash=encoded,
                    role="barber" if role == "barber" else "owner",
                    is_primary_owner=role == "principal",
                    barber_id=barber_id if role == "barber" else None,
                )
                session.add(user)
                identities[role] = user
            await session.commit()

        owner = identities["principal"]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://auth.test"
        ) as client:

            async def login(email: str, supplied_password: str) -> httpx.Response:
                return await client.post(
                    "/api/v1/auth/token", data={"username": email, "password": supplied_password}
                )

            response = await login(owner.email.upper(), password)
            assert response.status_code == 200
            old_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
            assert (await client.get("/api/v1/auth/me", headers=old_headers)).status_code == 200
            # A burst must count every failure, even when requests overlap.
            failures = await asyncio.gather(
                *(login(owner.email, "wrong-password") for _ in range(5))
            )
            assert sorted(item.status_code for item in failures) == [401, 401, 401, 401, 429]
            blocked = await login(owner.email, password)
            assert blocked.status_code == 429
            assert 880 <= int(blocked.headers["retry-after"]) <= 900
            async with async_session_factory() as session:
                row = await session.get(User, owner.id)
                assert row is not None and row.login_locked_until is not None
                row.login_locked_until = datetime.now(UTC) - timedelta(seconds=1)
                await session.commit()
            assert (await login(owner.email, password)).status_code == 200
            async with async_session_factory() as session:
                row = await session.get(User, owner.id)
                assert (
                    row is not None
                    and row.login_locked_until is None
                    and row.login_failed_attempts == 0
                )

            requested = await asyncio.gather(
                *(
                    client.post("/api/v1/auth/password-reset/request", json={"email": owner.email})
                    for _ in range(2)
                )
            )
            assert all(item.status_code == 200 for item in requested)
            assert requested[0].json() == requested[1].json()
            assert requested[0].json()["development_code"] is None and send.await_count == 1
            unknown = await client.post(
                "/api/v1/auth/password-reset/request",
                json={"email": f"unknown-{uuid4().hex}@example.com"},
            )
            assert unknown.json() == requested[0].json()
            professional = await client.post(
                "/api/v1/auth/password-reset/request", json={"email": identities["barber"].email}
            )
            assert professional.json() == unknown.json() and send.await_count == 1
            first_code = send.await_args.kwargs["code"]
            wrong_code = "000000" if first_code != "000000" else "999999"
            payload = {
                "email": owner.email,
                "code": wrong_code,
                "new_password": new_password,
                "password_confirmation": new_password,
            }
            for _ in range(5):
                assert (
                    await client.post("/api/v1/auth/password-reset/confirm", json=payload)
                ).status_code == 400
            assert (
                await client.post(
                    "/api/v1/auth/password-reset/confirm", json={**payload, "code": first_code}
                )
            ).status_code == 400
            assert (await login(owner.email, password)).status_code == 200

            async with async_session_factory() as session:
                row = await session.get(User, owner.id)
                assert row is not None
                row.password_reset_requested_at = datetime.now(UTC) - timedelta(minutes=2)
                await session.commit()
            await client.post("/api/v1/auth/password-reset/request", json={"email": owner.email})
            code = send.await_args.kwargs["code"]
            correct = {**payload, "code": code}
            assert (
                await client.post(
                    "/api/v1/auth/password-reset/confirm",
                    json={**correct, "password_confirmation": password},
                )
            ).status_code == 422
            results = await asyncio.gather(
                *(
                    client.post("/api/v1/auth/password-reset/confirm", json=correct)
                    for _ in range(2)
                )
            )
            assert sorted(item.status_code for item in results) == [204, 400]
            assert (await client.get("/api/v1/auth/me", headers=old_headers)).status_code == 401
            assert (await login(owner.email, password)).status_code == 401
            response = await login(owner.email, new_password)
            assert response.status_code == 200
            headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

            # Disabling and re-enabling must never resurrect an old session.
            for role in ("coowner", "barber"):
                account = identities[role]
                token = (await login(account.email, password)).json()["access_token"]
                previous = {"Authorization": f"Bearer {token}"}
                endpoint = (
                    f"/api/v1/auth/owner-accounts/{account.id}"
                    if role == "coowner"
                    else f"/api/v1/auth/barber-accounts/{barber_id}"
                )
                for active in (False, True):
                    updated = await client.patch(
                        endpoint,
                        headers=headers,
                        json={"current_password": new_password, "is_active": active},
                    )
                    assert updated.status_code == 200
                    assert (
                        await client.get("/api/v1/auth/me", headers=previous)
                    ).status_code == 401
                    assert (await login(account.email, password)).status_code == (
                        200 if active else 401
                    )

            response = await login(identities["barber"].email, password)
            previous = {"Authorization": f"Bearer {response.json()['access_token']}"}
            for active in (False, True):
                profile = await client.patch(
                    f"/api/v1/businesses/{business_id}/barbers/{barber_id}",
                    headers=headers,
                    json={"is_active": active},
                )
                assert profile.status_code == 200
                assert (await client.get("/api/v1/auth/me", headers=previous)).status_code == 401
                assert (await login(identities["barber"].email, password)).status_code == (
                    200 if active else 401
                )

            monkeypatch.setattr(settings, "email_delivery_enabled", False)
            before = send.await_count
            for email in (owner.email, f"unknown-{uuid4().hex}@example.com"):
                unavailable = await client.post(
                    "/api/v1/auth/password-reset/request", json={"email": email}
                )
                assert (
                    unavailable.status_code == 503 and "development_code" not in unavailable.json()
                )
            assert send.await_count == before
            assert (
                await client.post("/api/v1/auth/password-reset/confirm", json=correct)
            ).status_code == 503
    finally:
        await engine.dispose()
