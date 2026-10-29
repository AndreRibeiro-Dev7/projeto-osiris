"""Public admission quotas in real PostgreSQL with no external delivery."""

import asyncio
import os
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py against disposable PostgreSQL.",
)


def test_public_booking_quota_database(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(check_public_quota(monkeypatch))


async def check_public_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.engine import make_url

    database_url = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(database_url)
    assert url.drivername == "postgresql+asyncpg" and url.host == "127.0.0.1"
    assert url.database and url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == database_url

    import httpx
    from sqlalchemy import select

    from app.core.config import Settings
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.appointment import Appointment
    from app.models.barber import Barber
    from app.models.barber_schedule import BarberSchedule
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.public_booking_usage import PublicBookingUsage
    from app.models.service import Service

    assert not app.dependency_overrides
    settings = Settings(
        _env_file=None, public_booking_requests_per_minute=2, public_booking_requests_per_hour=3
    )
    monkeypatch.setattr("app.api.v1.routes.public_booking.get_settings", lambda: settings)
    clock = [datetime(2030, 1, 16, 12, tzinfo=UTC)]
    monkeypatch.setattr("app.services.assistant_usage.utc_now", lambda: clock[0])
    tenants = []
    day = date(2030, 1, 17)
    try:
        async with async_session_factory() as session:
            for _ in range(2):
                business = Business(
                    id=uuid4(),
                    name="Public quota test",
                    phone=uuid4().hex[:20],
                    timezone="America/Sao_Paulo",
                )
                session.add(business)
                await session.flush()
                barber = Barber(
                    id=uuid4(), business_id=business.id, full_name="Test barber", phone="111"
                )
                cut = Service(
                    id=uuid4(),
                    business_id=business.id,
                    name="Test cut",
                    duration_minutes=30,
                    price_cents=2500,
                )
                session.add_all([barber, cut])
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
                tenants.append((business, barber, cut))
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://public-quota.test"
        ) as client:
            business, barber, cut = tenants[0]

            async def reserve(index, tenant=0, starts_at=None, target_id=None):
                target, professional, service = tenants[tenant]
                return await client.post(
                    f"/api/v1/public/businesses/{target_id or target.id}/appointments",
                    headers={"X-Forwarded-For": f"192.0.2.{index+1}"},
                    json={
                        "barber_id": str(professional.id),
                        "service_id": str(service.id),
                        "customer_name": f"Test client {index}",
                        "customer_phone": f"0000000{index:04}",
                        "starts_at": starts_at
                        or f"{day.isoformat()}T{9+index//2:02}:{(index%2)*30:02}:00-03:00",
                    },
                )

            missing = uuid4()
            assert (await reserve(0, target_id=missing)).status_code == 404
            async with async_session_factory() as session:
                assert await session.get(PublicBookingUsage, missing) is None
            responses = await asyncio.gather(*(reserve(index) for index in range(4)))
            assert sorted(response.status_code for response in responses) == [201, 201, 429, 429]
            bookings = [response.json() for response in responses if response.status_code == 201]
            limited = await reserve(4)
            assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
            token = bookings[0]["booking_token"]
            manage = f"/api/v1/public/businesses/appointments/{token}"
            assert (await client.get(manage)).status_code == 200
            assert (await client.patch(f"{manage}/confirm")).status_code == 200
            assert (await client.patch(f"{manage}/cancel")).status_code == 200
            available = await client.get(
                f"/api/v1/public/businesses/{business.id}/barbers/{barber.id}/availability",
                params={"appointment_date": day.isoformat()},
            )
            assert available.status_code == 200 and len(available.json()["slots"]) == 5
            assert (await reserve(0, tenant=1)).status_code == 201

            clock[0] += timedelta(seconds=61)
            conflict = await reserve(10, starts_at=bookings[1]["appointment"]["starts_at"])
            assert conflict.status_code == 409
            limited = await reserve(11, starts_at=f"{day.isoformat()}T11:00:00-03:00")
            assert limited.status_code == 429 and limited.headers["retry-after"] == "3539"
            async with async_session_factory() as session:
                usage = await session.get(PublicBookingUsage, business.id)
                assert usage and usage.hour_requests == 3
                customers = list(
                    (
                        await session.scalars(
                            select(Customer).where(Customer.business_id == business.id)
                        )
                    ).all()
                )
                persisted = list(
                    (
                        await session.scalars(
                            select(Appointment).where(Appointment.business_id == business.id)
                        )
                    ).all()
                )
                assert len(customers) == len(persisted) == 2
            clock[0] += timedelta(hours=1)
            reopened = await reserve(11, starts_at=f"{day.isoformat()}T11:00:00-03:00")
            assert reopened.status_code == 201
            async with async_session_factory() as session:
                usage = await session.get(PublicBookingUsage, business.id)
                assert usage and (usage.minute_requests, usage.hour_requests) == (1, 1)
    finally:
        await engine.dispose()
