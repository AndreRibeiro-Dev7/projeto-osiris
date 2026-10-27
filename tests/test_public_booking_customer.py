import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.repositories.customer import CustomerRepository
from app.schemas.public_booking import PublicBookingCreate
from app.services.public_booking import PublicBookingService


@pytest.mark.parametrize("existing_customer", [False, True])
def test_public_booking_creates_or_reuses_a_customer(
    existing_customer: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = AsyncMock(spec=AsyncSession)
    service = PublicBookingService(session)
    business_id, barber_id, service_id, customer_id = (uuid4() for _ in range(4))
    customer = SimpleNamespace(id=customer_id)
    customers = create_autospec(CustomerRepository, instance=True)
    customers.get_by_business_and_phone.return_value = customer if existing_customer else None
    customers.create.return_value = customer
    service._customers = customers
    service._businesses = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id=business_id, name="Test business"))
    )
    service._barbers = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(
                id=barber_id, business_id=business_id, is_active=True, full_name="Test barber"
            )
        )
    )
    service._services = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=SimpleNamespace(
                id=service_id,
                business_id=business_id,
                is_active=True,
                name="Test cut",
                duration_minutes=30,
            )
        )
    )
    starts_at = datetime(2030, 1, 15, 14, tzinfo=UTC)
    appointment = Appointment(
        id=uuid4(),
        public_token=uuid4(),
        business_id=business_id,
        barber_id=barber_id,
        service_id=service_id,
        customer_id=customer_id,
        price_cents=1000,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        status=AppointmentStatus.SCHEDULED,
        created_at=starts_at,
    )
    reserve = AsyncMock(return_value=appointment)
    monkeypatch.setattr("app.services.public_booking.AppointmentService.create", reserve)
    payload = PublicBookingCreate(
        customer_name="Test customer",
        customer_phone="00000000000",
        barber_id=barber_id,
        service_id=service_id,
        starts_at=starts_at,
    )

    response = asyncio.run(service.create(business_id, payload))

    assert response.appointment.customer_id == customer_id
    assert response.booking_token == appointment.public_token
    customers.get_by_business_and_phone.assert_awaited_once_with(
        business_id, payload.customer_phone
    )
    if existing_customer:
        customers.create.assert_not_awaited()
        session.flush.assert_not_awaited()
    else:
        customers.create.assert_awaited_once_with(
            business_id=business_id,
            full_name=payload.customer_name,
            phone=payload.customer_phone,
            notes=None,
            birth_date=None,
        )
        session.flush.assert_awaited_once()
    assert reserve.await_args.args[1].customer_id == customer_id
