"""Exercise the public customer journey against disposable PostgreSQL."""

import asyncio
import os
from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py to create an isolated PostgreSQL.",
)


def test_public_booking_lifecycle_with_real_postgresql() -> None:
    asyncio.run(check_public_booking_lifecycle())


async def check_public_booking_lifecycle() -> None:
    from sqlalchemy.engine import make_url

    database_url = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(database_url)
    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "127.0.0.1"
    assert url.database and url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == database_url

    import httpx
    from sqlalchemy import select

    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.appointment import Appointment, AppointmentStatus
    from app.models.barber import Barber
    from app.models.barber_schedule import BarberSchedule
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.service import Service

    assert not app.dependency_overrides
    business_id, barber_id, service_id = (uuid4() for _ in range(3))
    booking_date = date(2030, 1, 16)
    try:
        async with async_session_factory() as session:
            session.add(
                Business(
                    id=business_id,
                    name="Public booking test",
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
                        description="Test service",
                        duration_minutes=30,
                        price_cents=2500,
                    ),
                ]
            )
            await session.flush()
            session.add(
                BarberSchedule(
                    barber_id=barber_id,
                    weekday=booking_date.weekday(),
                    starts_at=time(9),
                    ends_at=time(12),
                    slot_duration_minutes=30,
                )
            )
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://public-booking.test"
        ) as client:
            public_base = f"/api/v1/public/businesses/{business_id}"
            availability_url = f"{public_base}/barbers/{barber_id}/availability"
            params = {"appointment_date": booking_date.isoformat()}

            response = await client.get(
                "/dashboard/booking/", params={"business_id": str(business_id)}
            )
            assert response.status_code == 200
            response = await client.get(public_base)
            assert response.status_code == 200
            assert response.json()["barbers"][0]["id"] == str(barber_id)
            assert response.json()["services"][0]["id"] == str(service_id)

            response = await client.get(availability_url, params=params)
            assert response.status_code == 200
            slots = response.json()["slots"]
            assert len(slots) == 6
            first, second = (slot["starts_at"] for slot in slots[:2])
            payload = {
                "customer_name": "Fictitious new customer",
                "customer_phone": "00000000001",
                "barber_id": str(barber_id),
                "service_id": str(service_id),
                "starts_at": first,
            }

            # New customer, persisted appointment and secure management token.
            response = await client.post(f"{public_base}/appointments", json=payload)
            assert response.status_code == 201
            result = response.json()
            appointment_id = UUID(result["appointment"]["id"])
            customer_id = UUID(result["appointment"]["customer_id"])
            booking_token = result["booking_token"]
            assert result["appointment"]["status"] == "scheduled"
            assert result["appointment"]["price_cents"] == 2500
            assert datetime.fromisoformat(result["appointment"]["ends_at"]) == (
                datetime.fromisoformat(first) + timedelta(minutes=30)
            )
            manage_url = f"/api/v1/public/businesses/appointments/{booking_token}"
            async with async_session_factory() as session:
                customer = await session.get(Customer, customer_id)
                assert customer is not None and customer.business_id == business_id
                assert customer.full_name == payload["customer_name"]
                assert customer.notes is None and customer.birth_date is None

            response = await client.get(availability_url, params=params)
            assert response.status_code == 200
            assert first not in [item["starts_at"] for item in response.json()["slots"]]

            # A second customer cannot occupy the same slot, nor remain after rollback.
            conflicting_payload = {**payload, "customer_phone": "00000000002"}
            response = await client.post(f"{public_base}/appointments", json=conflicting_payload)
            assert response.status_code == 409
            async with async_session_factory() as session:
                phantom = await session.scalar(
                    select(Customer).where(
                        Customer.business_id == business_id,
                        Customer.phone == conflicting_payload["customer_phone"],
                    )
                )
                assert phantom is None

            response = await client.get(manage_url)
            assert response.status_code == 200
            assert response.json()["status"] == "scheduled"
            response = await client.patch(f"{manage_url}/confirm")
            assert response.status_code == 200
            assert response.json()["status"] == "confirmed"

            response = await client.patch(
                f"{manage_url}/reschedule",
                json={
                    "barber_id": str(barber_id),
                    "service_id": str(service_id),
                    "starts_at": second,
                },
            )
            assert response.status_code == 200
            assert datetime.fromisoformat(response.json()["starts_at"]) == datetime.fromisoformat(
                second
            )
            response = await client.get(availability_url, params=params)
            assert response.status_code == 200
            available = [item["starts_at"] for item in response.json()["slots"]]
            assert first in available and second not in available

            response = await client.patch(f"{manage_url}/cancel")
            assert response.status_code == 200
            assert response.json()["status"] == "cancelled"
            response = await client.get(availability_url, params=params)
            assert response.status_code == 200
            assert len(response.json()["slots"]) == 6
            # Cancelled bookings cannot be confirmed or rescheduled again.
            response = await client.patch(f"{manage_url}/confirm")
            assert response.status_code == 409
            response = await client.patch(
                f"{manage_url}/reschedule",
                json={
                    "barber_id": str(barber_id),
                    "service_id": str(service_id),
                    "starts_at": first,
                },
            )
            assert response.status_code == 409
            response = await client.get(f"/api/v1/public/businesses/appointments/{uuid4()}")
            assert response.status_code == 404

            # A fresh reservation reuses the tenant's existing customer and freed slot.
            response = await client.post(f"{public_base}/appointments", json=payload)
            assert response.status_code == 201
            assert response.json()["appointment"]["customer_id"] == str(customer_id)
            assert response.json()["booking_token"] != booking_token
            async with async_session_factory() as session:
                customers = list(
                    (
                        await session.scalars(
                            select(Customer).where(Customer.business_id == business_id)
                        )
                    ).all()
                )
                appointments = list(
                    (
                        await session.scalars(
                            select(Appointment).where(Appointment.business_id == business_id)
                        )
                    ).all()
                )
                original = await session.get(Appointment, appointment_id)
                assert len(customers) == 1 and len(appointments) == 2
                assert original is not None and original.status == AppointmentStatus.CANCELLED
    finally:
        await engine.dispose()
