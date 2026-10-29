"""Real assistant workflow and transactions; only the external model is simulated."""

import asyncio
import os
from datetime import date, time
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

pytestmark = pytest.mark.skipif(
    not os.environ.get("OSIRIS_INTEGRATION_DATABASE_URL"),
    reason="Run scripts/test_tenant_isolation.py to create an isolated PostgreSQL.",
)


class ControlledModel:
    def __init__(self) -> None:
        self.contexts: list[str] = []

    async def interpret(
        self, *, instructions: str, user_input: str, response_format: type[BaseModel]
    ) -> BaseModel:
        from app.core.exceptions import AIProviderError
        from app.schemas.assistant import AssistantIntent

        if user_input == "provider-failure":
            raise AIProviderError("The AI provider could not interpret the message.")
        if user_input == "Confirmo":
            return AssistantIntent(intent="confirm_booking")
        if user_input.startswith("Quero às "):
            return AssistantIntent(
                intent="select_slot", selected_time=user_input.removeprefix("Quero às ")
            )
        return AssistantIntent(intent="check_availability")

    async def generate(self, *, instructions: str, user_input: str) -> str:
        self.contexts.append(user_input)
        return "Consulte os horários disponíveis para escolher seu atendimento."


def test_assistant_workflow_with_real_postgresql(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(check_assistant_workflow(monkeypatch))


async def check_assistant_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.engine import make_url

    database_url = os.environ["OSIRIS_INTEGRATION_DATABASE_URL"]
    url = make_url(database_url)
    assert url.drivername == "postgresql+asyncpg" and url.host == "127.0.0.1"
    assert url.database and url.database.startswith("osiris_isolation_test_")
    assert os.environ.get("DATABASE_URL") == database_url

    import httpx
    from sqlalchemy import event, select
    from sqlalchemy.orm import Session

    from app.core.security import hash_password
    from app.database.session import async_session_factory, engine
    from app.main import app
    from app.models.appointment import Appointment
    from app.models.assistant_conversation import AssistantConversation
    from app.models.audit_log import AuditLog
    from app.models.barber import Barber
    from app.models.barber_schedule import BarberSchedule
    from app.models.barber_time_off import BarberTimeOff
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.user import User

    assert not app.dependency_overrides
    model = ControlledModel()
    monkeypatch.setattr("app.api.v1.routes.businesses.OpenAIResponsesClient", lambda **_: model)
    monkeypatch.setattr(
        "app.api.v1.routes.businesses.get_settings",
        lambda: SimpleNamespace(
            openai_api_key="fictitious-test-key",
            openai_model="controlled-test-model",
            assistant_requests_per_minute=20,
            assistant_requests_per_hour=200,
        ),
    )
    business_id, barber_id, customer_id = (uuid4() for _ in range(3))
    day = date(2030, 1, 17)
    email = f"assistant-{uuid4().hex}@example.com"
    password = "Fictitious-assistant-password-123!"

    async def records():
        async with async_session_factory() as session:
            return list(
                (
                    await session.scalars(
                        select(Appointment).where(Appointment.business_id == business_id)
                    )
                ).all()
            )

    try:
        async with async_session_factory() as session:
            session.add(Business(id=business_id, name="Assistant test", phone=uuid4().hex[:20]))
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
                    User(
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
                    ends_at=time(12),
                    slot_duration_minutes=30,
                )
            )
            await session.commit()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://assistant.test",
        ) as client:
            response = await client.post(
                "/api/v1/auth/token", data={"username": email, "password": password}
            )
            assert response.status_code == 200
            headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
            endpoint = f"/api/v1/businesses/{business_id}/assistant/messages"

            async def send(message: str, **extra):
                return await client.post(
                    endpoint,
                    headers=headers,
                    json={
                        "barber_id": str(barber_id),
                        "appointment_date": day.isoformat(),
                        "customer_id": str(customer_id),
                        "message": message,
                        **extra,
                    },
                )

            response = await send("Quais horários?")
            assert response.status_code == 200 and response.json()["action"] == "availability"
            async with async_session_factory() as session:
                history = list(
                    (
                        await session.scalars(
                            select(AuditLog).where(AuditLog.business_id == business_id)
                        )
                    ).all()
                )
                assert history == []
            assert "2030-01-17T09:00:00-03:00" in model.contexts[-1]
            assert str(customer_id) not in model.contexts[-1]
            assert str(business_id) not in model.contexts[-1]
            response = await send("Confirmo")
            assert response.status_code == 200 and response.json()["action"] != "booked"
            response = await send("Quero às 09:00", customer_id=None)
            assert response.status_code == 200 and response.json()["action"] == "customer_required"
            response = await send("Quero às 23:00")
            assert response.status_code == 200 and response.json()["conversation_id"] is None
            assert await records() == []

            response = await send("Quero às 09:00")
            assert (
                response.status_code == 200 and response.json()["action"] == "confirmation_required"
            )
            conversation_id = response.json()["conversation_id"]
            assert await records() == []
            response = await send("Não quero confirmar", conversation_id=conversation_id)
            assert response.status_code == 200 and response.json()["action"] != "booked"
            assert await records() == []
            response = await send("Confirmo", conversation_id=str(uuid4()))
            assert response.status_code == 404

            # Concurrent retries must return the same persisted reservation.
            first, second = await asyncio.gather(
                send("Confirmo", conversation_id=conversation_id),
                send("Confirmo", conversation_id=conversation_id),
            )
            assert first.status_code == second.status_code == 200
            assert first.json()["appointment_id"] == second.json()["appointment_id"]
            assert first.json()["action"] == second.json()["action"] == "booked"
            assert len(await records()) == 1
            async with async_session_factory() as session:
                history = list(
                    (
                        await session.scalars(
                            select(AuditLog).where(AuditLog.business_id == business_id)
                        )
                    ).all()
                )
                assert len(history) == 2  # Two confirmations, one idempotent reservation.
                assert all(
                    item.area == "Agenda" and "assistente" in item.description for item in history
                )

            # A new absence entered after the proposal invalidates that proposal.
            response = await send("Quero às 10:00")
            assert (
                response.status_code == 200 and response.json()["action"] == "confirmation_required"
            )
            blocked_conversation_id = UUID(response.json()["conversation_id"])
            async with async_session_factory() as session:
                proposal = await session.get(AssistantConversation, blocked_conversation_id)
                assert proposal is not None
                session.add(
                    BarberTimeOff(
                        barber_id=barber_id,
                        starts_at=proposal.proposed_starts_at,
                        ends_at=proposal.proposed_ends_at,
                        reason="Fictitious absence",
                    )
                )
                await session.commit()
            response = await send("Confirmo", conversation_id=str(blocked_conversation_id))
            assert response.status_code == 409
            assert len(await records()) == 1

            # Simulate failure precisely when the conversation would be linked.
            response = await send("Quero às 11:00")
            assert (
                response.status_code == 200 and response.json()["action"] == "confirmation_required"
            )
            interrupted_id = UUID(response.json()["conversation_id"])

            def interrupt_commit(session: Session) -> None:
                if any(
                    isinstance(item, AssistantConversation)
                    and item.id == interrupted_id
                    and item.appointment_id is not None
                    for item in session.dirty
                ):
                    raise RuntimeError("Controlled transaction failure")

            event.listen(Session, "before_commit", interrupt_commit)
            try:
                response = await send("Confirmo", conversation_id=str(interrupted_id))
                assert response.status_code == 500
            finally:
                event.remove(Session, "before_commit", interrupt_commit)
            assert len(await records()) == 1  # No orphan appointment after rollback.
            response = await send("Confirmo", conversation_id=str(interrupted_id))
            assert response.status_code == 200 and response.json()["action"] == "booked"
            assert len(await records()) == 2

            response = await send("provider-failure")
            assert response.status_code == 502
            assert len(await records()) == 2

            # A real booking made after the proposal must win over stale availability.
            response = await send("Quero às 09:30")
            assert response.status_code == 200
            assert response.json()["action"] == "confirmation_required"
            occupied_id = UUID(response.json()["conversation_id"])
            async with async_session_factory() as session:
                proposal = await session.get(AssistantConversation, occupied_id)
                assert proposal is not None
                occupied_start = proposal.proposed_starts_at.isoformat()
                occupied_end = proposal.proposed_ends_at.isoformat()
            response = await client.post(
                f"/api/v1/businesses/{business_id}/appointments",
                headers=headers,
                json={
                    "barber_id": str(barber_id),
                    "customer_id": str(customer_id),
                    "starts_at": occupied_start,
                    "ends_at": occupied_end,
                },
            )
            assert response.status_code == 201
            response = await send("Confirmo", conversation_id=str(occupied_id))
            assert response.status_code == 409
            assert len(await records()) == 3
    finally:
        await engine.dispose()
