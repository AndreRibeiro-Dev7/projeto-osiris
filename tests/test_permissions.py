import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.dependencies import require_business_access, require_primary_owner
from app.api.v1.routes.auth import require_owner_account
from app.core.exceptions import InsufficientPermissionError
from app.services.auth import AuthService


def test_owner_can_access_own_business() -> None:
    business_id = uuid4()
    owner = SimpleNamespace(business_id=business_id, role="owner")

    result = asyncio.run(require_business_access(business_id, owner))  # type: ignore[arg-type]

    assert result is owner


def test_barber_cannot_access_owner_business_routes() -> None:
    business_id = uuid4()
    barber = SimpleNamespace(business_id=business_id, role="barber")

    with pytest.raises(HTTPException) as error:
        asyncio.run(require_business_access(business_id, barber))  # type: ignore[arg-type]

    assert error.value.status_code == 403


def test_barber_cannot_change_its_own_credentials() -> None:
    barber = SimpleNamespace(role="barber")

    with pytest.raises(HTTPException) as error:
        require_owner_account(barber)  # type: ignore[arg-type]

    assert error.value.status_code == 403


def test_owner_can_change_its_own_credentials() -> None:
    owner = SimpleNamespace(role="owner")

    assert require_owner_account(owner) is None  # type: ignore[arg-type]


def test_co_owner_cannot_delete_owner_accounts() -> None:
    co_owner = SimpleNamespace(role="owner", is_primary_owner=False)
    service = AuthService.__new__(AuthService)

    with pytest.raises(InsufficientPermissionError):
        asyncio.run(
            service.delete_owner_account(  # type: ignore[arg-type]
                owner=co_owner,
                account_id=uuid4(),
                current_password="senha-atual",
            )
        )


def test_primary_owner_can_send_operational_alert_test() -> None:
    owner = SimpleNamespace(role="owner", is_primary_owner=True)

    result = asyncio.run(require_primary_owner(owner))  # type: ignore[arg-type]

    assert result is owner


@pytest.mark.parametrize(
    "account",
    [
        SimpleNamespace(role="owner", is_primary_owner=False),
        SimpleNamespace(role="barber", is_primary_owner=False),
    ],
)
def test_non_primary_accounts_cannot_send_operational_alert_test(account: object) -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_primary_owner(account))  # type: ignore[arg-type]

    assert error.value.status_code == 403
