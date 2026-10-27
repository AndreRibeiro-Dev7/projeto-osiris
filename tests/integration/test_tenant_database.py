"""Opt-in HTTP checks using real PostgreSQL, accounts, JWTs and repositories."""

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py to create an isolated PostgreSQL.",
)


def test_tenant_boundaries_with_real_postgresql() -> None:
    asyncio.run(check_tenant_boundaries())


async def check_tenant_boundaries() -> None:
    # Validate the target before importing app settings or opening a connection.
    from sqlalchemy.engine import make_url

    database_url = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(database_url)
    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "127.0.0.1"
    assert url.database and url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == database_url

    import httpx
    from sqlalchemy import func, select

    from app.core.security import hash_password
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.appointment import Appointment, AppointmentStatus, PaymentMethod
    from app.models.barber import Barber
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.expense import Expense
    from app.models.service import Service
    from app.models.user import User

    assert not app.dependency_overrides, "Integration checks must use real dependencies."
    password = "Fictitious-password-for-isolation-123!"
    password_hash = hash_password(password)
    tenants = []
    starts_at = datetime(2030, 1, 15, 14, tzinfo=UTC)
    try:
        async with async_session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(Business)) == 0
            for index in (1, 2):
                business = Business(id=uuid4(), name=f"Test business {index}", phone=f"000{index}")
                session.add(business)
                await session.flush()
                barber = Barber(
                    id=uuid4(),
                    business_id=business.id,
                    full_name=f"Test barber {index}",
                    phone="111",
                )
                alternate = Barber(
                    id=uuid4(), business_id=business.id, full_name="Other professional", phone="222"
                )
                customer = Customer(
                    id=uuid4(),
                    business_id=business.id,
                    full_name=f"Test customer {index}",
                    phone="333",
                )
                service = Service(
                    id=uuid4(),
                    business_id=business.id,
                    name="Test cut",
                    duration_minutes=30,
                    price_cents=index * 1000,
                )
                session.add_all([barber, alternate, customer, service])
                await session.flush()
                accounts = {}
                for role in ("principal", "coowner", "barber"):
                    user = User(
                        id=uuid4(),
                        business_id=business.id,
                        email=f"{role}{index}@example.com",
                        password_hash=password_hash,
                        role="barber" if role == "barber" else "owner",
                        is_primary_owner=role == "principal",
                        barber_id=barber.id if role == "barber" else None,
                    )
                    session.add(user)
                    accounts[role] = user
                scheduled = Appointment(
                    id=uuid4(),
                    business_id=business.id,
                    barber_id=barber.id,
                    customer_id=customer.id,
                    service_id=service.id,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(minutes=30),
                    status=AppointmentStatus.SCHEDULED,
                    price_cents=service.price_cents,
                )
                completed = Appointment(
                    id=uuid4(),
                    business_id=business.id,
                    barber_id=barber.id,
                    customer_id=customer.id,
                    service_id=service.id,
                    starts_at=starts_at + timedelta(hours=1),
                    ends_at=starts_at + timedelta(hours=1, minutes=30),
                    status=AppointmentStatus.COMPLETED,
                    price_cents=service.price_cents,
                    payment_method=PaymentMethod.CASH,
                    paid_at=starts_at,
                )
                expense = Expense(
                    id=uuid4(),
                    business_id=business.id,
                    category="rent",
                    description=f"Test expense {index}",
                    amount_cents=index * 100,
                    occurred_on=date(2030, 1, 15),
                )
                session.add_all([scheduled, completed, expense])
                tenants.append(
                    {
                        "business": business,
                        "barber": barber,
                        "alternate": alternate,
                        "customer": customer,
                        "service": service,
                        "scheduled": scheduled,
                        "expense": expense,
                        "accounts": accounts,
                    }
                )
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://isolation.test"
        ) as client:
            for tenant in tenants:
                tenant["headers"] = {}
                for role, account in tenant["accounts"].items():
                    response = await client.post(
                        "/api/v1/auth/token", data={"username": account.email, "password": password}
                    )
                    assert response.status_code == 200
                    tenant["headers"][role] = {
                        "Authorization": f"Bearer {response.json()['access_token']}"
                    }

            for own, foreign in (tenants, tenants[::-1]):
                base = f"/api/v1/businesses/{own['business'].id}"
                foreign_base = f"/api/v1/businesses/{foreign['business'].id}"
                for role in ("principal", "coowner"):
                    headers = own["headers"][role]
                    response = await client.get(f"{base}/customers", headers=headers)
                    assert response.status_code == 200
                    assert [row["id"] for row in response.json()] == [str(own["customer"].id)]
                    for suffix, params in (
                        ("/customers", {}),
                        ("/expenses", {"date_from": "2030-01-01", "date_to": "2030-01-31"}),
                        ("/audit-logs", {}),
                    ):
                        response = await client.get(
                            foreign_base + suffix, params=params, headers=headers
                        )
                        assert response.status_code == 403
                    response = await client.get(
                        f"{base}/reports/financial",
                        headers=headers,
                        params={"date_from": "2030-01-01", "date_to": "2030-01-31"},
                    )
                    assert response.status_code == 200
                    assert response.json()["total_revenue_cents"] == own["service"].price_cents
                    assert response.json()["total_expenses_cents"] == own["expense"].amount_cents
                    response = await client.patch(
                        f"{base}/expenses/{foreign['expense'].id}/paid", headers=headers
                    )
                    assert response.status_code == 404
                    response = await client.patch(
                        f"{base}/appointments/{foreign['scheduled'].id}/confirm", headers=headers
                    )
                    assert response.status_code == 409
                    response = await client.patch(
                        f"/api/v1/auth/owner-accounts/{foreign['accounts']['coowner'].id}",
                        headers=headers,
                        json={"current_password": password, "is_active": False},
                    )
                    assert response.status_code == 404

                response = await client.get(f"{base}/customers", headers=own["headers"]["barber"])
                assert response.status_code == 403
                response = await client.get(
                    "/api/v1/auth/barber/appointments",
                    headers=own["headers"]["barber"],
                    params={"appointment_date": "2030-01-15"},
                )
                assert response.status_code == 200
                assert all(row["customer_id"] == str(own["customer"].id) for row in response.json())
                assert len(response.json()) == 2
                response = await client.patch(
                    f"/api/v1/auth/barber/appointments/{foreign['scheduled'].id}/confirm",
                    headers=own["headers"]["barber"],
                )
                assert response.status_code == 404
                response = await client.patch(
                    f"/api/v1/auth/owner-accounts/{own['accounts']['principal'].id}",
                    headers=own["headers"]["coowner"],
                    json={"current_password": password, "is_active": False},
                )
                assert response.status_code == 404
                response = await client.request(
                    "DELETE",
                    f"/api/v1/auth/owner-accounts/{own['accounts']['principal'].id}",
                    headers=own["headers"]["coowner"],
                    json={"current_password": password},
                )
                assert response.status_code == 403

            # Confirm the denied writes did not alter either tenant's records.
            async with async_session_factory() as session:
                for tenant in tenants:
                    expense = await session.get(Expense, tenant["expense"].id)
                    appointment = await session.get(Appointment, tenant["scheduled"].id)
                    assert expense and not expense.is_paid
                    assert appointment and appointment.status == AppointmentStatus.SCHEDULED

            own, foreign = tenants
            response = await client.patch(
                f"/api/v1/auth/barber/appointments/{own['scheduled'].id}/confirm",
                headers=own["headers"]["barber"],
            )
            assert response.status_code == 200
            assert response.json()["status"] == "confirmed"

            # A database-level inconsistent link must invalidate both login and old JWTs.
            async with async_session_factory() as session:
                account = await session.get(User, own["accounts"]["barber"].id)
                assert account is not None
                account.barber_id = foreign["alternate"].id
                await session.commit()
            response = await client.get("/api/v1/auth/me", headers=own["headers"]["barber"])
            assert response.status_code == 401
            response = await client.post(
                "/api/v1/auth/token",
                data={"username": own["accounts"]["barber"].email, "password": password},
            )
            assert response.status_code == 401
    finally:
        await engine.dispose()
