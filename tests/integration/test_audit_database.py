"""Authenticated audit history, financial actions and retained actor snapshots."""

import asyncio
import os
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py against disposable PostgreSQL.",
)


def test_audit_history_database(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(check_audit_history(monkeypatch))


async def check_audit_history(monkeypatch: pytest.MonkeyPatch) -> None:
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
    from app.models.audit_log import AuditLog
    from app.models.barber import Barber
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.expense import Expense
    from app.models.service import Service
    from app.models.user import User

    assert not app.dependency_overrides
    password = "Fictitious-audit-test-password-123!"
    hashed = hash_password(password)
    business_id, other_id, barber_id, customer_id, service_id = (uuid4() for _ in range(5))
    accounts = []
    try:
        async with async_session_factory() as session:
            session.add_all(
                [
                    Business(id=business_id, name="Audit test", phone=uuid4().hex[:20]),
                    Business(id=other_id, name="Other audit test", phone=uuid4().hex[:20]),
                ]
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
                ]
            )
            await session.flush()
            for tenant, role, principal in [
                (business_id, "owner", True),
                (business_id, "owner", False),
                (other_id, "owner", True),
                (business_id, "barber", False),
            ]:
                user = User(
                    id=uuid4(),
                    business_id=tenant,
                    role=role,
                    is_primary_owner=principal,
                    email=f"audit-{uuid4().hex}@example.com",
                    password_hash=hashed,
                    barber_id=barber_id if role == "barber" else None,
                )
                session.add(user)
                accounts.append(user)
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://audit.test"
        ) as client:
            tokens = []
            for user in accounts:
                login = await client.post(
                    "/api/v1/auth/token", data={"username": user.email, "password": password}
                )
                assert login.status_code == 200
                tokens.append({"Authorization": f"Bearer {login.json()['access_token']}"})
            base = f"/api/v1/businesses/{business_id}"
            history = f"{base}/audit-logs"

            async def logs(headers=tokens[0], **params):
                response = await client.get(history, headers=headers, params=params)
                assert response.status_code == 200
                return response.json()

            assert await logs() == []
            assert (await client.get(history)).status_code == 401
            for token in [tokens[2], tokens[3]]:
                assert (await client.get(history, headers=token)).status_code == 403
            private_description = "Audit-payload-sentinel-do-not-store"
            payload = {
                "category": "rent",
                "description": private_description,
                "amount_cents": 240000,
                "occurred_on": "2030-01-16",
            }
            invalid = await client.post(
                f"{base}/expenses", headers=tokens[0], json={**payload, "amount_cents": 0}
            )
            assert invalid.status_code == 422 and await logs() == []
            expense = await client.post(f"{base}/expenses", headers=tokens[1], json=payload)
            assert expense.status_code == 201
            expense_id = expense.json()["id"]
            first = await logs()
            assert len(first) == 1
            assert first[0]["actor_email"] == accounts[1].email
            assert first[0]["actor_is_primary_owner"] is False
            assert first[0]["description"] == "Cadastrou uma despesa"
            assert first[0]["area"] == "Financeiro" and first[0]["created_at"]
            paid = await client.patch(f"{base}/expenses/{expense_id}/paid", headers=tokens[0])
            assert paid.status_code == 200
            deleted = await client.delete(f"{base}/expenses/{expense_id}", headers=tokens[0])
            assert deleted.status_code == 204

            booking = await client.post(
                f"{base}/appointments",
                headers=tokens[0],
                json={
                    "barber_id": str(barber_id),
                    "customer_id": str(customer_id),
                    "service_id": str(service_id),
                    "starts_at": "2030-01-16T09:00:00-03:00",
                    "ends_at": "2030-01-16T09:30:00-03:00",
                },
            )
            assert booking.status_code == 201
            completed = await client.patch(
                f"{base}/appointments/{booking.json()['id']}/complete",
                headers=tokens[0],
                json={"payment_method": "pix"},
            )
            assert completed.status_code == 200
            financial = await logs(area="Financeiro")
            assert len(financial) == 3
            assert {item["description"] for item in financial} == {
                "Cadastrou uma despesa",
                "Confirmou o pagamento de uma despesa",
                "Excluiu uma despesa",
            }
            assert len(await logs(area="Agenda")) == 2
            assert await logs(tokens[1]) == await logs()
            limited = await logs(limit=1)
            assert len(limited) == 1
            assert (
                await client.get(history, headers=tokens[0], params={"limit": 201})
            ).status_code == 422
            before = await logs()
            assert (
                await client.patch(history, headers=tokens[0], json={"description": "tampered"})
            ).status_code == 405
            assert (await client.delete(history, headers=tokens[0])).status_code == 405
            assert await logs() == before

            removed = await client.request(
                "DELETE",
                f"/api/v1/auth/owner-accounts/{accounts[1].id}",
                headers=tokens[0],
                json={"current_password": password},
            )
            assert removed.status_code == 204
            assert (await client.get(history, headers=tokens[1])).status_code == 401
            after = await logs(area="Financeiro")
            assert after == financial
            async with async_session_factory() as session:
                records = list(
                    (
                        await session.scalars(
                            select(AuditLog).where(AuditLog.business_id == business_id)
                        )
                    ).all()
                )
                snapshot = next(row for row in records if row.actor_email == accounts[1].email)
                assert snapshot.actor_user_id is None and snapshot.actor_role == "owner"
                assert snapshot.actor_is_primary_owner is False
                assert all(private_description not in row.description for row in records)
                assert all(
                    password not in row.description and password not in row.path for row in records
                )
                foreign = list(
                    (
                        await session.scalars(
                            select(AuditLog).where(AuditLog.business_id == other_id)
                        )
                    ).all()
                )
                assert foreign == []

            # A failed history write must not make a committed expense look unsaved.
            from unittest.mock import AsyncMock

            notification = AsyncMock(return_value=False)
            monkeypatch.setattr(
                "app.main.record_activity",
                AsyncMock(side_effect=RuntimeError("Simulated history failure")),
            )
            monkeypatch.setattr("app.main.dispatch_operational_alert", notification)
            saved = await client.post(f"{base}/expenses", headers=tokens[0], json=payload)
            assert saved.status_code == 201
            notification.assert_awaited_once()
            assert notification.call_args.args[0].event == "audit_persistence_failed"
            async with async_session_factory() as session:
                committed = await session.get(Expense, UUID(saved.json()["id"]))
                assert committed and committed.amount_cents == payload["amount_cents"]
    finally:
        await engine.dispose()
