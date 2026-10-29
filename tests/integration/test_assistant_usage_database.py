"""Persistent assistant quotas with real auth and PostgreSQL; model calls are simulated."""

import asyncio
import os
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py against disposable PostgreSQL.",
)


def test_assistant_quota_database(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(check_assistant_quota(monkeypatch))


async def check_assistant_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.engine import make_url

    database_url = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(database_url)
    assert url.drivername == "postgresql+asyncpg" and url.host == "127.0.0.1"
    assert url.database and url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == database_url

    import httpx

    from app.core.config import Settings
    from app.core.exceptions import AIProviderError
    from app.core.security import hash_password
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.assistant_usage import AssistantUsage
    from app.models.barber import Barber
    from app.models.barber_schedule import BarberSchedule
    from app.models.business import Business
    from app.models.user import User
    from app.schemas.assistant import AssistantIntent

    assert not app.dependency_overrides
    settings = Settings(
        _env_file=None,
        openai_api_key="simulated-not-a-key",
        openai_model="simulated",
        assistant_requests_per_minute=2,
        assistant_requests_per_hour=3,
    )
    monkeypatch.setattr("app.api.v1.routes.businesses.get_settings", lambda: settings)
    clock = [datetime(2030, 1, 16, 12, tzinfo=UTC)]
    monkeypatch.setattr("app.services.assistant_usage.utc_now", lambda: clock[0])
    calls = []

    class Model:
        async def interpret(self, **kwargs):
            calls.append(kwargs["user_input"])
            if kwargs["user_input"] == "failure":
                raise AIProviderError("Simulated provider failure")
            return AssistantIntent(intent="check_availability")

        async def generate(self, **kwargs):
            return "Horários disponíveis."

    monkeypatch.setattr(
        "app.api.v1.routes.businesses.OpenAIResponsesClient", lambda **kwargs: Model()
    )
    password = "Quota-test-only-password-123!"
    hashed = hash_password(password)
    tenants = []
    day = date(2030, 1, 17)
    try:
        async with async_session_factory() as session:
            for _ in range(2):
                business = Business(
                    id=uuid4(),
                    name="Quota test",
                    phone=uuid4().hex[:20],
                    timezone="America/Sao_Paulo",
                )
                session.add(business)
                await session.flush()
                barber = Barber(
                    id=uuid4(), business_id=business.id, full_name="Test barber", phone="111"
                )
                session.add(barber)
                users = []
                for principal in [True, False]:
                    user = User(
                        id=uuid4(),
                        business_id=business.id,
                        role="owner",
                        is_primary_owner=principal,
                        password_hash=hashed,
                        email=f"quota-{uuid4().hex}@example.com",
                    )
                    session.add(user)
                    users.append(user)
                await session.flush()
                session.add(
                    BarberSchedule(
                        barber_id=barber.id,
                        weekday=day.weekday(),
                        starts_at=time(9),
                        ends_at=time(12),
                        slot_duration_minutes=30,
                    )
                )
                tenants.append((business, barber, users))
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://quota.test"
        ) as client:
            business, barber, users = tenants[0]
            tokens = []
            for user in [*users, tenants[1][2][0]]:
                login = await client.post(
                    "/api/v1/auth/token", data={"username": user.email, "password": password}
                )
                assert login.status_code == 200
                tokens.append({"Authorization": f"Bearer {login.json()['access_token']}"})

            async def send(headers, tenant=0, message="horários"):
                target, professional, _ = tenants[tenant]
                return await client.post(
                    f"/api/v1/businesses/{target.id}/assistant/messages",
                    headers=headers,
                    json={
                        "barber_id": str(professional.id),
                        "appointment_date": day.isoformat(),
                        "message": message,
                    },
                )

            assert (await send({})).status_code == 401
            assert (await send(tokens[0], tenant=1)).status_code == 403
            assert calls == []
            responses = await asyncio.gather(*(send(tokens[0]) for _ in range(4)))
            assert sorted(response.status_code for response in responses) == [200, 200, 429, 429]
            assert len(calls) == 2
            limited = await send(tokens[1])  # Co-owner shares the same allowance.
            assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
            assert len(calls) == 2
            async with async_session_factory() as session:
                usage = await session.get(AssistantUsage, business.id)
                assert usage and (usage.minute_requests, usage.hour_requests) == (2, 2)
                assert await session.get(AssistantUsage, tenants[1][0].id) is None

            clock[0] += timedelta(seconds=61)
            failed = await send(tokens[0], message="failure")
            assert failed.status_code == 502
            # A provider error consumes quota even when its workflow rolls back.
            limited = await send(tokens[0])
            assert limited.status_code == 429
            assert limited.headers["retry-after"] == "3539"
            assert len(calls) == 3
            async with async_session_factory() as session:
                usage = await session.get(AssistantUsage, business.id)
                assert usage and usage.hour_requests == 3
            other = await send(tokens[2], tenant=1)
            assert other.status_code == 200 and len(calls) == 4
            manual = await client.get(
                f"/api/v1/businesses/{business.id}/barbers/{barber.id}/availability",
                headers=tokens[0],
                params={"appointment_date": day.isoformat()},
            )
            assert manual.status_code == 200
            clock[0] += timedelta(hours=1)
            reopened = await send(tokens[0])
            assert reopened.status_code == 200 and len(calls) == 5
            async with async_session_factory() as session:
                usage = await session.get(AssistantUsage, business.id)
                assert usage and (usage.minute_requests, usage.hour_requests) == (1, 1)
    finally:
        await engine.dispose()
