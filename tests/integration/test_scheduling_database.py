"""Owner scheduling journey in disposable PostgreSQL, without mocked permissions."""

import asyncio
import os
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py against disposable PostgreSQL.",
)


def test_owner_scheduling_database() -> None:
    asyncio.run(check_owner_scheduling())


async def check_owner_scheduling() -> None:
    from sqlalchemy.engine import make_url

    database_url = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(database_url)
    assert url.drivername == "postgresql+asyncpg" and url.host == "127.0.0.1"
    assert url.database and url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == database_url

    import httpx

    from app.core.security import hash_password
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.appointment import Appointment
    from app.models.barber import Barber
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.service import Service
    from app.models.user import User

    assert not app.dependency_overrides
    password = "Scheduling-test-only-password-123!"
    business_id, barber_id, customer_id, service_id = (uuid4() for _ in range(4))
    email = f"schedule-{uuid4().hex}@example.com"
    day = "2030-01-16"

    def starts(hour: int, minute: int = 0) -> str:
        return f"{day}T{hour:02}:{minute:02}:00-03:00"

    def payload(hour: int, minute: int = 0) -> dict:
        start = datetime.fromisoformat(starts(hour, minute))
        return {
            "barber_id": str(barber_id),
            "customer_id": str(customer_id),
            "service_id": str(service_id),
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(minutes=30)).isoformat(),
        }

    try:
        async with async_session_factory() as session:
            session.add(
                Business(
                    id=business_id,
                    name="Scheduling test",
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
                    Customer(
                        id=customer_id,
                        business_id=business_id,
                        full_name="Test client",
                        phone="222",
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
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://scheduling.test"
        ) as client:
            login = await client.post(
                "/api/v1/auth/token", data={"username": email, "password": password}
            )
            assert login.status_code == 200
            client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
            base = f"/api/v1/businesses/{business_id}"
            barber = f"{base}/barbers/{barber_id}"
            schedule = f"{barber}/schedule/{datetime.fromisoformat(day).weekday()}"
            response = await client.put(
                schedule,
                json={
                    "starts_at": "09:00",
                    "ends_at": "18:00",
                    "slot_duration_minutes": 30,
                    "break_starts_at": "12:00",
                    "break_ends_at": "13:00",
                },
            )
            assert response.status_code == 200

            async def slots() -> list[datetime]:
                response = await client.get(
                    f"{barber}/availability", params={"appointment_date": day}
                )
                assert response.status_code == 200
                return [
                    datetime.fromisoformat(item["starts_at"]) for item in response.json()["slots"]
                ]

            initial = await slots()
            assert len(initial) == 16
            assert datetime.fromisoformat(starts(11, 30)) in initial
            assert datetime.fromisoformat(starts(12)) not in initial
            assert datetime.fromisoformat(starts(13)) in initial
            time_off = await client.post(
                f"{barber}/time-off",
                json={
                    "starts_at": starts(10),
                    "ends_at": starts(11),
                    "reason": "Test absence",
                },
            )
            assert time_off.status_code == 201
            assert len(await slots()) == 14
            assert datetime.fromisoformat(starts(10)) not in await slots()
            removed = await client.delete(f"{barber}/time-off/{time_off.json()['id']}")
            assert removed.status_code == 204
            assert await slots() == initial

            # Same barber and interval: only one competing reservation can commit.
            responses = await asyncio.gather(
                *[client.post(f"{base}/appointments", json=payload(9)) for _ in range(2)]
            )
            assert sorted(response.status_code for response in responses) == [201, 409]
            first = next(response.json() for response in responses if response.status_code == 201)
            assert datetime.fromisoformat(starts(9)) not in await slots()
            second = await client.post(f"{base}/appointments", json=payload(9, 30))
            assert second.status_code == 201  # Adjacent appointments do not overlap.
            appointment_url = f"{base}/appointments/{first['id']}"
            move = {
                "barber_id": str(barber_id),
                "service_id": str(service_id),
                "starts_at": starts(9, 30),
            }
            rejected = await client.patch(f"{appointment_url}/reschedule", json=move)
            assert rejected.status_code == 409
            async with async_session_factory() as session:
                original = await session.get(Appointment, UUID(first["id"]))
                assert original is not None
                assert original.starts_at == datetime.fromisoformat(starts(9))
            move["starts_at"] = starts(11)
            moved = await client.patch(f"{appointment_url}/reschedule", json=move)
            assert moved.status_code == 200
            available = await slots()
            assert datetime.fromisoformat(starts(9)) in available
            assert datetime.fromisoformat(starts(11)) not in available
            confirmed = await client.patch(f"{appointment_url}/confirm")
            assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"

            closure_payload = {"closure_date": day, "reason": "Test closure"}
            closure = await client.post(f"{base}/closures", json=closure_payload)
            assert closure.status_code == 409  # Active appointments must be handled first.
            for appointment_id in [first["id"], second.json()["id"]]:
                cancelled = await client.patch(f"{base}/appointments/{appointment_id}/cancel")
                assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
            assert await slots() == initial
            rejected = await client.patch(f"{appointment_url}/reschedule", json=move)
            assert rejected.status_code == 409  # A cancelled appointment stays cancelled.

            # Reserve another date, close this day, and reject moving into the closure.
            other = payload(9)
            other["starts_at"] = other["starts_at"].replace(day, "2030-01-17")
            other["ends_at"] = other["ends_at"].replace(day, "2030-01-17")
            other_booking = await client.post(f"{base}/appointments", json=other)
            assert other_booking.status_code == 201
            closure = await client.post(f"{base}/closures", json=closure_payload)
            assert closure.status_code == 201
            assert await slots() == []
            rejected = await client.post(f"{base}/appointments", json=payload(9))
            assert rejected.status_code == 409
            rejected = await client.patch(
                f"{base}/appointments/{other_booking.json()['id']}/reschedule", json=move
            )
            assert rejected.status_code == 409
            removed = await client.delete(f"{base}/closures/{closure.json()['id']}")
            assert removed.status_code == 204
            assert await slots() == initial
            # Different appointments competing for the same destination are serialized.
            candidates = []
            for minute in [0, 30]:
                created = await client.post(f"{base}/appointments", json=payload(13, minute))
                assert created.status_code == 201
                candidates.append(created.json()["id"])
            destination = {**move, "starts_at": starts(14)}
            competing = await asyncio.gather(
                *[
                    client.patch(f"{base}/appointments/{item}/reschedule", json=destination)
                    for item in candidates
                ]
            )
            assert sorted(response.status_code for response in competing) == [200, 409]
            async with async_session_factory() as session:
                records = [await session.get(Appointment, UUID(item)) for item in candidates]
                assert (
                    sum(
                        item is not None and item.starts_at == datetime.fromisoformat(starts(14))
                        for item in records
                    )
                    == 1
                )
    finally:
        await engine.dispose()
