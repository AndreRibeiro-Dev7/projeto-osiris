"""First-owner setup must remain private and serialize concurrent requests."""

import asyncio
import os
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py against disposable PostgreSQL.",
)


def test_owner_setup_database(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(check_owner_setup(monkeypatch))


async def check_owner_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import select
    from sqlalchemy.engine import make_url

    target = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(target)
    assert url.drivername == "postgresql+asyncpg" and url.host == "127.0.0.1"
    assert url.database and url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == target

    import httpx

    from app.core.config import get_settings
    from app.core.security import verify_password
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.business import Business
    from app.models.user import User
    from app.repositories.business import BusinessRepository

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "owner_bootstrap_enabled", False)
    monkeypatch.setattr(settings, "owner_bootstrap_token", "fictitious-setup-token")
    monkeypatch.setattr(settings, "discord_alert_webhook_url", "")
    business_id = uuid4()
    password = "Fictitious-setup-password-123!"
    payload = {
        "business_id": str(business_id),
        "email": f"setup-{uuid4().hex}@example.com",
        "password": password,
    }
    setup_headers = {"X-Setup-Token": "fictitious-setup-token"}
    pending: list[asyncio.Task] = []
    try:
        async with async_session_factory() as session:
            session.add(Business(id=business_id, name="Setup test", phone=uuid4().hex[:20]))
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://setup.test"
        ) as client:
            endpoint = "/api/v1/auth/bootstrap-owner"
            assert (
                await client.post(endpoint, json=payload, headers=setup_headers)
            ).status_code == 404
            monkeypatch.setattr(settings, "owner_bootstrap_enabled", True)
            for headers in ({}, {"X-Setup-Token": "wrong-token"}):
                assert (
                    await client.post(endpoint, json=payload, headers=headers)
                ).status_code == 404
            assert (
                await client.post(
                    endpoint, json={**payload, "business_id": str(uuid4())}, headers=setup_headers
                )
            ).status_code == 404
            assert (
                await client.post(
                    endpoint, json={**payload, "password": "short"}, headers=setup_headers
                )
            ).status_code == 422

            # Hold the row lock until all requests reach the locking query.
            # A timeout here catches a regression to a non-locking lookup.
            original = BusinessRepository.get_by_id_for_update
            reached = asyncio.Event()
            attempts = 0

            async def observed(repository: BusinessRepository, key: UUID) -> Business | None:
                nonlocal attempts
                if key == business_id:
                    attempts += 1
                    if attempts == 3:
                        reached.set()
                return await original(repository, key)

            monkeypatch.setattr(BusinessRepository, "get_by_id_for_update", observed)
            async with async_session_factory() as blocker:
                await original(BusinessRepository(blocker), business_id)
                for index in range(3):
                    pending.append(
                        asyncio.create_task(
                            client.post(
                                endpoint,
                                json={
                                    **payload,
                                    "email": f"setup-{index}-{uuid4().hex}@example.com",
                                },
                                headers=setup_headers,
                            )
                        )
                    )
                await asyncio.wait_for(reached.wait(), timeout=10)
                assert all(not task.done() for task in pending)
                await blocker.commit()
            responses = await asyncio.wait_for(asyncio.gather(*pending), timeout=20)
            assert sorted(response.status_code for response in responses) == [201, 409, 409]
            created = next(response.json() for response in responses if response.status_code == 201)
            assert created["role"] == "owner" and created["is_primary_owner"] is True
            assert "password" not in created and "password_hash" not in created
            async with async_session_factory() as session:
                users = list(
                    (
                        await session.scalars(select(User).where(User.business_id == business_id))
                    ).all()
                )
                assert len(users) == 1 and users[0].is_primary_owner
                assert users[0].password_hash != password
                assert verify_password(password, users[0].password_hash)
            login = await client.post(
                "/api/v1/auth/token", data={"username": created["email"], "password": password}
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200
            assert (
                await client.post(endpoint, json=payload, headers=setup_headers)
            ).status_code == 409
            monkeypatch.setattr(settings, "owner_bootstrap_enabled", False)
            assert (
                await client.post(endpoint, json=payload, headers=setup_headers)
            ).status_code == 404
    finally:
        for task in pending:
            if not task.done():
                task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await engine.dispose()
