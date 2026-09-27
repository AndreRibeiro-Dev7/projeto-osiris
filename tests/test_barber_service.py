import asyncio
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.barber import Barber
from app.models.user import User
from app.repositories.barber import BarberRepository
from app.repositories.user import UserRepository
from app.schemas.barber import BarberUpdate
from app.services.barber import BarberService


def test_disabling_barber_also_disables_linked_login() -> None:
    business_id = uuid4()
    barber = Barber(
        id=uuid4(),
        business_id=business_id,
        full_name="Profissional Osiris",
        phone="5511999999999",
        is_active=True,
    )
    account = User(
        id=uuid4(),
        business_id=business_id,
        barber_id=barber.id,
        email="barbeiro@osiris.com",
        password_hash="hash",
        role="barber",
        is_active=True,
    )
    session = AsyncMock(spec=AsyncSession)
    service = BarberService(cast(AsyncSession, session))
    barbers = AsyncMock(spec=BarberRepository)
    barbers.get_by_id.return_value = barber
    users = AsyncMock(spec=UserRepository)
    users.get_by_barber_id.return_value = account
    service._barbers = cast(BarberRepository, barbers)
    service._users = cast(UserRepository, users)

    result = asyncio.run(service.update(business_id, barber.id, BarberUpdate(is_active=False)))

    assert result.is_active is False
    assert account.is_active is False
    session.commit.assert_awaited_once()
