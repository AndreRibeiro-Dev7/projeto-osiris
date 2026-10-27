"""WhatsApp recovery with real PostgreSQL locks; delivery is always simulated."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Requires scripts/test_tenant_isolation.py and disposable PostgreSQL.",
)


def test_booking_recovery_database(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(check_recovery(monkeypatch))


async def check_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    from sqlalchemy import select
    from sqlalchemy.engine import make_url

    database_url = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(database_url)
    assert url.host == "127.0.0.1"
    assert url.database and url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == database_url

    from app.core.config import get_settings
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.appointment import Appointment, AppointmentStatus
    from app.models.barber import Barber
    from app.models.booking_access import BookingAccessChallenge
    from app.models.business import Business
    from app.models.customer import Customer

    settings = get_settings()
    for field, value in {
        "whatsapp_recovery_enabled": True,
        "whatsapp_access_token": "test-only",
        "whatsapp_phone_number_id": "12345",
        "whatsapp_api_version": "v25.0",
        "jwt_secret_key": "test-secret" * 4,
    }.items():
        monkeypatch.setattr(settings, field, value)
    send = AsyncMock()
    monkeypatch.setattr("app.api.v1.routes.public_booking.send_booking_access_code", send)
    own_token = uuid4()
    phone = "11987654321"
    businesses = [uuid4(), uuid4()]
    try:
        async with async_session_factory() as session:
            for business_id in businesses:
                session.add(Business(id=business_id, name="Recovery test", phone=uuid4().hex[:20]))
            await session.flush()
            barber_ids = [uuid4(), uuid4()]
            customer_ids = [uuid4(), uuid4(), uuid4()]
            for index, business_id in enumerate(businesses):
                session.add(
                    Barber(
                        id=barber_ids[index],
                        business_id=business_id,
                        full_name="Test barber",
                        phone=uuid4().hex[:20],
                    )
                )
            session.add_all(
                [
                    Customer(
                        id=customer_ids[0],
                        business_id=businesses[0],
                        full_name="Verified",
                        phone="+55 (11) 98765-4321",
                    ),
                    Customer(
                        id=customer_ids[1],
                        business_id=businesses[0],
                        full_name="Another phone",
                        phone="21987654321",
                    ),
                    Customer(
                        id=customer_ids[2],
                        business_id=businesses[1],
                        full_name="Another business",
                        phone=phone,
                    ),
                ]
            )
            await session.flush()
            now = datetime.now(UTC)
            for index, (business_index, customer_index, status, days) in enumerate(
                [
                    (0, 0, AppointmentStatus.SCHEDULED, 1),
                    (0, 1, AppointmentStatus.SCHEDULED, 1),
                    (1, 2, AppointmentStatus.SCHEDULED, 1),
                    (0, 0, AppointmentStatus.SCHEDULED, -1),
                    (0, 0, AppointmentStatus.CANCELLED, 2),
                ]
            ):
                starts = now + timedelta(days=days, hours=index)
                session.add(
                    Appointment(
                        id=uuid4(),
                        public_token=own_token if index == 0 else uuid4(),
                        business_id=businesses[business_index],
                        barber_id=barber_ids[business_index],
                        customer_id=customer_ids[customer_index],
                        starts_at=starts,
                        ends_at=starts + timedelta(minutes=30),
                        price_cents=1000,
                        status=status,
                    )
                )
            await session.commit()

        transport = httpx.ASGITransport(app=app, client=("127.0.0.77", 1234))
        base = f"/api/v1/public/businesses/{businesses[0]}/access"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            requested = await client.post(f"{base}/request", json={"phone": phone, "consent": True})
            assert requested.status_code == 200
            assert requested.headers["cache-control"] == "no-store"
            assert set(requested.json()) == {"challenge_id", "expires_in", "resend_after", "detail"}
            code = send.await_args.kwargs["code"]
            challenge_id = requested.json()["challenge_id"]
            payload = {"phone": phone, "challenge_id": challenge_id, "code": code}
            async with async_session_factory() as session:
                row = (
                    await session.scalars(
                        select(BookingAccessChallenge).where(
                            BookingAccessChallenge.business_id == businesses[0]
                        )
                    )
                ).one()
                assert row.code_hash != code and len(row.code_hash) == 64
            response = await client.post(f"{base}/request", json={"phone": phone, "consent": True})
            assert response.status_code == 429 and int(response.headers["retry-after"]) > 0
            assert send.await_count == 1
            wrong_business = f"/api/v1/public/businesses/{businesses[1]}/access/verify"
            assert (await client.post(wrong_business, json=payload)).status_code == 400
            assert (
                await client.post(f"{base}/verify", json={**payload, "phone": "21987654321"})
            ).status_code == 400
            results = await asyncio.gather(
                *(client.post(f"{base}/verify", json=payload) for _ in range(2))
            )
            assert sorted(result.status_code for result in results) == [200, 400]
            recovered = next(result for result in results if result.status_code == 200).json()[
                "bookings"
            ]
            assert [item["booking_token"] for item in recovered] == [str(own_token)]
            assert (await client.post(f"{base}/verify", json=payload)).status_code == 400

            # New codes replace old ones; five wrong guesses permanently consume the current code.
            async with async_session_factory() as session:
                row = (
                    await session.scalars(
                        select(BookingAccessChallenge).where(
                            BookingAccessChallenge.business_id == businesses[0]
                        )
                    )
                ).one()
                row.last_sent_at = now - timedelta(minutes=2)
                await session.commit()
            assert (
                await client.post(f"{base}/request", json={"phone": phone, "consent": True})
            ).status_code == 200
            latest = send.await_args.kwargs["code"]
            wrong = "000000" if latest != "000000" else "999999"
            for _ in range(5):
                assert (
                    await client.post(f"{base}/verify", json={**payload, "code": wrong})
                ).status_code == 400
            assert (
                await client.post(f"{base}/verify", json={**payload, "code": latest})
            ).status_code == 400

            async with async_session_factory() as session:
                row = (
                    await session.scalars(
                        select(BookingAccessChallenge).where(
                            BookingAccessChallenge.business_id == businesses[0]
                        )
                    )
                ).one()
                row.last_sent_at = now - timedelta(minutes=2)
                await session.commit()
            send.side_effect = httpx.ConnectError("simulated failure")
            failure = await client.post(f"{base}/request", json={"phone": phone, "consent": True})
            assert failure.status_code == 503
            async with async_session_factory() as session:
                row = (
                    await session.scalars(
                        select(BookingAccessChallenge).where(
                            BookingAccessChallenge.business_id == businesses[0]
                        )
                    )
                ).one()
                assert row.code_hash is None
    finally:
        await engine.dispose()
