"""Bounded ASGI load with real PostgreSQL; not a production capacity benchmark."""

import asyncio
import math
import os
from datetime import date, datetime, time
from time import perf_counter
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL")
    or os.environ.get("OSIRIS_RUN_LOAD_TEST") != "true",
    reason="Run scripts/test_tenant_isolation.py --load with disposable PostgreSQL.",
)


def test_moderate_scheduling_load_database() -> None:
    asyncio.run(check_moderate_scheduling_load())


async def check_moderate_scheduling_load() -> None:
    from sqlalchemy.engine import make_url

    database_url = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(database_url)
    assert url.drivername == "postgresql+asyncpg" and url.host == "127.0.0.1"
    assert url.database and url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == database_url

    import httpx
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.appointment import Appointment
    from app.models.barber import Barber
    from app.models.barber_schedule import BarberSchedule
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.service import Service
    from app.models.user import User

    assert not app.dependency_overrides
    business_id, barber_id, service_id = (uuid4() for _ in range(3))
    email = f"load-{uuid4().hex}@example.com"
    password = "Fictitious-load-only-password-123!"
    day = date(2030, 1, 16)
    latencies: list[float] = []
    try:
        async with async_session_factory() as session:
            session.add(
                Business(
                    id=business_id,
                    name="Load test",
                    phone=uuid4().hex[:20],
                    timezone="America/Sao_Paulo",
                )
            )
            await session.flush()
            session.add_all(
                [
                    Barber(
                        id=barber_id, business_id=business_id, full_name="Test barber", phone="111"
                    ),
                    Service(
                        id=service_id,
                        business_id=business_id,
                        name="Test cut",
                        duration_minutes=30,
                        price_cents=2500,
                    ),
                    User(
                        id=uuid4(),
                        business_id=business_id,
                        email=email,
                        password_hash=hash_password(password),
                        role="owner",
                        is_primary_owner=True,
                    ),
                ]
            )
            await session.flush()
            session.add(
                BarberSchedule(
                    barber_id=barber_id,
                    weekday=day.weekday(),
                    starts_at=time(9),
                    ends_at=time(18),
                    slot_duration_minutes=30,
                )
            )
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://isolated-load.test"
        ) as client:
            login = await client.post(
                "/api/v1/auth/token", data={"username": email, "password": password}
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            public = f"/api/v1/public/businesses/{business_id}"
            availability = f"{public}/barbers/{barber_id}/availability"
            agenda = f"/api/v1/businesses/{business_id}/barbers/{barber_id}/appointments"
            params = {"appointment_date": day.isoformat()}
            # Warm up connection pools; these responses are not included in timings.
            warmup = await client.get(availability, params=params)
            assert warmup.status_code == 200 and len(warmup.json()["slots"]) == 18
            semaphore = asyncio.Semaphore(10)

            async def read(index: int) -> None:
                async with semaphore:
                    started = perf_counter()
                    kind = index % 3
                    if kind == 0:
                        response = await client.get(public)
                    elif kind == 1:
                        response = await client.get(availability, params=params)
                    else:
                        response = await client.get(agenda, params=params, headers=headers)
                    latencies.append((perf_counter() - started) * 1000)
                    assert response.status_code == 200
                    data = response.json()
                    if kind == 0:
                        assert data["id"] == str(business_id) and len(data["barbers"]) == 1
                    elif kind == 1:
                        assert len(data["slots"]) == 18
                    else:
                        assert data == []

            started = perf_counter()
            await asyncio.wait_for(
                asyncio.gather(*(read(index) for index in range(100))), timeout=60
            )
            elapsed = perf_counter() - started
            ordered = sorted(latencies)
            p95 = ordered[math.ceil(len(ordered) * 0.95) - 1]
            print(
                f"\nConsultas: 100 | simultaneas: 10 | HTTP 200: {len(latencies)} | "
                f"p50: {ordered[49]:.1f}ms | p95: {p95:.1f}ms | max: {ordered[-1]:.1f}ms | "
                f"total: {elapsed:.2f}s | vazao: {100/elapsed:.1f} req/s",
                flush=True,
            )

            async def reserve(index: int) -> httpx.Response:
                return await client.post(
                    f"{public}/appointments",
                    json={
                        "customer_name": f"Fictitious load client {index}",
                        "customer_phone": f"0000000{index:04}",
                        "barber_id": str(barber_id),
                        "service_id": str(service_id),
                        "starts_at": f"{day.isoformat()}T10:00:00-03:00",
                    },
                )

            responses = await asyncio.wait_for(
                asyncio.gather(*(reserve(index) for index in range(10))), timeout=60
            )
            codes = [response.status_code for response in responses]
            assert codes.count(201) == 1 and codes.count(409) == 9, codes
            async with async_session_factory() as session:
                bookings = list(
                    (
                        await session.scalars(
                            select(Appointment).where(Appointment.business_id == business_id)
                        )
                    ).all()
                )
                customers = list(
                    (
                        await session.scalars(
                            select(Customer).where(Customer.business_id == business_id)
                        )
                    ).all()
                )
                assert len(bookings) == len(customers) == 1
                assert bookings[0].customer_id == customers[0].id
                assert bookings[0].starts_at == datetime.fromisoformat(
                    f"{day.isoformat()}T10:00:00-03:00"
                )
            after = await client.get(availability, params=params)
            assert after.status_code == 200 and len(after.json()["slots"]) == 17
            print(
                "Disputa de horario: 10 tentativas | 1 reserva | 9 conflitos | "
                "1 cliente persistido | nenhum cadastro orfao",
                flush=True,
            )
    finally:
        await engine.dispose()
