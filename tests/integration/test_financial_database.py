"""Owner financial workflow using real PostgreSQL and the HTTP API."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py against disposable PostgreSQL.",
)


def test_financial_workflow_database() -> None:
    asyncio.run(check_financial_workflow())


async def check_financial_workflow() -> None:
    from sqlalchemy.engine import make_url

    database_url = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(database_url)
    assert url.host == "127.0.0.1" and url.database
    assert url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == database_url

    import httpx
    from openpyxl import load_workbook

    from app.core.security import hash_password
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.appointment import Appointment, AppointmentStatus, PaymentMethod
    from app.models.barber import Barber
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.service import Service
    from app.models.user import User

    assert not app.dependency_overrides
    tenants = []
    password = "Financial-test-only-password-123!"
    password_hash = hash_password(password)
    try:
        async with async_session_factory() as session:
            for index in range(2):
                business = Business(
                    id=uuid4(), name=f"Finance test {index}", phone=uuid4().hex[:20]
                )
                session.add(business)
                await session.flush()
                barber = Barber(
                    id=uuid4(),
                    business_id=business.id,
                    full_name="Test barber",
                    phone="111",
                    commission_percentage=50,
                )
                customer = Customer(
                    id=uuid4(), business_id=business.id, full_name="Test customer", phone="222"
                )
                service = Service(
                    id=uuid4(),
                    business_id=business.id,
                    name="Test cut",
                    duration_minutes=30,
                    price_cents=1001,
                )
                owner = User(
                    id=uuid4(),
                    business_id=business.id,
                    email=f"finance-{uuid4().hex}@example.com",
                    password_hash=password_hash,
                    role="owner",
                    is_primary_owner=True,
                )
                session.add_all([barber, customer, service, owner])
                await session.flush()
                tenants.append((business, barber, customer, service, owner))
            business, barber, customer, service, _ = tenants[1]
            starts = datetime(2030, 1, 16, 14, tzinfo=UTC)
            session.add(
                Appointment(
                    id=uuid4(),
                    business_id=business.id,
                    barber_id=barber.id,
                    customer_id=customer.id,
                    service_id=service.id,
                    starts_at=starts,
                    ends_at=starts + timedelta(minutes=30),
                    status=AppointmentStatus.COMPLETED,
                    price_cents=99999,
                    payment_method=PaymentMethod.CASH,
                    paid_at=starts,
                )
            )
            await session.commit()

        business, barber, customer, service, owner = tenants[0]
        base = f"/api/v1/businesses/{business.id}"
        foreign_base = f"/api/v1/businesses/{tenants[1][0].id}"
        dates = {"date_from": "2030-01-15", "date_to": "2030-01-31"}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://finance.test"
        ) as client:
            login = await client.post(
                "/api/v1/auth/token", data={"username": owner.email, "password": password}
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            async def create_appointment(hour: int) -> str:
                starts_at = datetime(2030, 1, 16, hour, tzinfo=UTC)
                response = await client.post(
                    f"{base}/appointments",
                    headers=headers,
                    json={
                        "barber_id": str(barber.id),
                        "customer_id": str(customer.id),
                        "service_id": str(service.id),
                        "starts_at": starts_at.isoformat(),
                        "ends_at": (starts_at + timedelta(minutes=30)).isoformat(),
                    },
                )
                assert response.status_code == 201
                return response.json()["id"]

            first, second = await create_appointment(1), await create_appointment(14)
            # The price charged is the reservation's snapshot, not the edited catalog price.
            edited = await client.patch(
                f"{base}/services/{service.id}", headers=headers, json={"price_cents": 5000}
            )
            assert edited.status_code == 200
            completed = await client.patch(
                f"{base}/appointments/{first}/complete",
                headers=headers,
                json={"payment_method": "pix"},
            )
            assert completed.status_code == 200
            assert completed.json()["price_cents"] == 1001 and completed.json()["paid_at"]
            repeated = await asyncio.gather(
                *(
                    client.patch(
                        f"{base}/appointments/{second}/complete",
                        headers=headers,
                        json={"payment_method": "cash"},
                    )
                    for _ in range(2)
                )
            )
            assert sorted(item.status_code for item in repeated) == [200, 409]
            assert (
                await client.patch(
                    f"{base}/appointments/{first}/complete",
                    headers=headers,
                    json={"payment_method": "cash"},
                )
            ).status_code == 409
            for hour, action in [(15, "cancel"), (16, "no-show"), (17, "confirm")]:
                appointment_id = await create_appointment(hour)
                assert (
                    await client.patch(
                        f"{base}/appointments/{appointment_id}/{action}", headers=headers
                    )
                ).status_code == 200
            await create_appointment(18)

            expenses = []
            for amount, day, fixed in [(75, "2030-01-31", True), (25, "2030-01-16", False)]:
                response = await client.post(
                    f"{base}/expenses",
                    headers=headers,
                    json={
                        "category": "rent" if fixed else "supplies",
                        "description": "Fixed test" if fixed else "Variable test",
                        "amount_cents": amount,
                        "occurred_on": day,
                        "is_fixed": fixed,
                    },
                )
                assert response.status_code == 201 and not response.json()["is_paid"]
                expenses.append(response.json())
            variable_id = expenses[1]["id"]
            paid = await client.patch(f"{base}/expenses/{variable_id}/paid", headers=headers)
            assert paid.status_code == 200 and paid.json()["is_paid"] and paid.json()["paid_at"]
            pending = await client.patch(f"{base}/expenses/{variable_id}/pending", headers=headers)
            assert (
                pending.status_code == 200
                and not pending.json()["is_paid"]
                and pending.json()["paid_at"] is None
            )
            await client.patch(f"{base}/expenses/{variable_id}/paid", headers=headers)

            response = await client.get(f"{base}/reports/financial", headers=headers, params=dates)
            assert response.status_code == 200
            report = response.json()
            assert report["total_revenue_cents"] == 2002
            assert report["total_commission_cents"] == 1000
            assert report["total_expenses_cents"] == 100 and report["final_result_cents"] == 902
            assert sum(day["result_cents"] for day in report["daily"]) == 902
            assert report["completed"] == 2 and report["cancelled"] == report["no_show"] == 1
            assert report["scheduled"] == report["confirmed"] == 1
            assert (
                report["average_ticket_cents"] == 1001 and report["attendance_rate_percent"] == 67
            )
            assert {row["label"]: row["total_cents"] for row in report["by_payment_method"]} == {
                "Pix": 1001,
                "Dinheiro": 1001,
            }
            assert (
                report["daily"][0]["date"] == "2030-01-15"
                and report["daily"][0]["revenue_cents"] == 1001
            )
            assert (
                await client.get(f"{foreign_base}/reports/financial", headers=headers, params=dates)
            ).status_code == 403

            exported = await client.get(
                f"{base}/reports/financial.xlsx", headers=headers, params=dates
            )
            assert exported.status_code == 200
            workbook = load_workbook(BytesIO(exported.content), data_only=True)
            assert workbook["Financeiro"]["B8"].value == pytest.approx(20.02)
            assert workbook["Financeiro"]["D8"].value == 10
            assert workbook["Financeiro"]["D11"].value == pytest.approx(9.02)
            workbook.close()

            # Two simultaneous monthly generation requests may create only one copy.
            generated = await asyncio.gather(
                *(
                    client.post(
                        f"{base}/expenses/fixed/generate",
                        headers=headers,
                        params={"target_month": "2030-02-17"},
                    )
                    for _ in range(2)
                )
            )
            assert all(item.status_code == 200 for item in generated)
            assert sorted(len(item.json()) for item in generated) == [0, 1]
            fixed = next(item.json()[0] for item in generated if item.json())
            assert fixed["occurred_on"] == "2030-02-28" and fixed["amount_cents"] == 75
            assert not fixed["is_paid"] and fixed["paid_at"] is None
            assert (
                await client.post(
                    f"{base}/expenses/fixed/generate",
                    headers=headers,
                    params={"target_month": "2030-02-01"},
                )
            ).json() == []

            updated = await client.patch(
                f"{base}/expenses/{variable_id}",
                headers=headers,
                json={
                    "category": "supplies",
                    "description": "Corrected test",
                    "amount_cents": 50,
                    "occurred_on": "2030-01-16",
                    "is_fixed": False,
                },
            )
            assert updated.status_code == 200
            report = (
                await client.get(f"{base}/reports/financial", headers=headers, params=dates)
            ).json()
            assert report["total_expenses_cents"] == 125 and report["final_result_cents"] == 877
            assert (
                await client.delete(f"{base}/expenses/{variable_id}", headers=headers)
            ).status_code == 204
            report = (
                await client.get(f"{base}/reports/financial", headers=headers, params=dates)
            ).json()
            assert report["total_expenses_cents"] == 75 and report["final_result_cents"] == 927

            profile = (await client.get(base, headers=headers)).json()
            goal = await client.patch(
                base,
                headers=headers,
                json={
                    "name": profile["name"],
                    "phone": profile["phone"],
                    "timezone": profile["timezone"],
                    "monthly_revenue_goal_cents": 3000,
                },
            )
            assert goal.status_code == 200 and goal.json()["monthly_revenue_goal_cents"] == 3000
            assert (await client.get(base, headers=headers)).json()[
                "monthly_revenue_goal_cents"
            ] == 3000
            assert (
                await client.get(
                    f"{base}/reports/financial",
                    headers=headers,
                    params={"date_from": "2030-02-02", "date_to": "2030-02-01"},
                )
            ).status_code == 422
    finally:
        await engine.dispose()
