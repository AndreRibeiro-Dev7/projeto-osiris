"""Exercise tenant and role boundaries through the real HTTP dependencies."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.security import create_access_token
from app.database.session import get_db_session
from app.main import app

BUSINESS_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_BUSINESS_ID = UUID("00000000-0000-0000-0000-000000000002")
RESOURCE_ID = UUID("00000000-0000-0000-0000-000000000003")


def private_business_operations() -> list[tuple[str, str]]:
    """Include every administrative business endpoint, including future additions."""
    operations = []
    for path, methods in app.openapi()["paths"].items():
        if not path.startswith("/api/v1/businesses/{business_id}"):
            continue
        for method in methods:
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            operations.append((method.upper(), path))
    assert operations, "The isolation suite must cover private business endpoints."
    return operations


@pytest.fixture
def isolated_session():
    session = AsyncMock()

    async def session_override():
        yield session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = session_override
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.mark.parametrize(("method", "path"), private_business_operations())
@pytest.mark.parametrize("identity", ["anonymous", "foreign_owner", "foreign_co_owner", "barber"])
def test_private_business_endpoints_reject_unauthorized_accounts(
    method: str, path: str, identity: str, isolated_session: AsyncMock
) -> None:
    if identity != "anonymous":
        user = SimpleNamespace(
            business_id=BUSINESS_ID if identity == "barber" else OTHER_BUSINESS_ID,
            role="barber" if identity == "barber" else "owner",
            is_primary_owner=identity == "foreign_owner",
        )
        app.dependency_overrides[get_current_user] = lambda: user
    url = path.replace("{business_id}", str(BUSINESS_ID))
    for name in (
        "barber_id",
        "customer_id",
        "service_id",
        "appointment_id",
        "expense_id",
        "item_id",
    ):
        url = url.replace("{" + name + "}", str(RESOURCE_ID))
    url = url.replace("{weekday}", "0")

    response = TestClient(app).request(method, url, json={})

    assert response.status_code == (401 if identity == "anonymous" else 403)
    assert isolated_session.mock_calls == []


@pytest.mark.parametrize("is_primary_owner", [True, False])
def test_owner_and_co_owner_can_read_only_their_customer_list(
    is_primary_owner: bool, isolated_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = SimpleNamespace(role="owner", business_id=BUSINESS_ID, is_primary_owner=is_primary_owner)
    app.dependency_overrides[get_current_user] = lambda: user
    listing = AsyncMock(return_value=[])
    monkeypatch.setattr("app.api.v1.routes.businesses.CustomerService.list", listing)

    response = TestClient(app).get(f"/api/v1/businesses/{BUSINESS_ID}/customers")

    assert response.status_code == 200
    assert response.json() == []
    listing.assert_awaited_once_with(BUSINESS_ID)


@pytest.mark.parametrize("foreign_business", [False, True])
def test_barber_cannot_change_another_professionals_appointment(
    foreign_business: bool, isolated_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    barber_id = uuid4()
    user = SimpleNamespace(role="barber", business_id=BUSINESS_ID, barber_id=barber_id)
    app.dependency_overrides[get_current_user] = lambda: user
    appointment = SimpleNamespace(
        business_id=OTHER_BUSINESS_ID if foreign_business else BUSINESS_ID,
        barber_id=barber_id if foreign_business else uuid4(),
    )
    monkeypatch.setattr(
        "app.api.v1.routes.auth.AppointmentRepository.get_by_id",
        AsyncMock(return_value=appointment),
    )
    confirm = AsyncMock()
    monkeypatch.setattr("app.api.v1.routes.auth.AppointmentService.confirm", confirm)

    response = TestClient(app).patch(f"/api/v1/auth/barber/appointments/{RESOURCE_ID}/confirm")

    assert response.status_code == 404
    confirm.assert_not_awaited()
    isolated_session.commit.assert_not_awaited()


@pytest.mark.parametrize(
    "invalid_state", ["inactive_user", "revoked", "inactive_barber", "foreign_barber"]
)
def test_existing_tokens_reject_inactive_revoked_or_cross_tenant_profiles(
    invalid_state: str, isolated_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "tenant-test-signing-key-with-at-least-32-characters"
    user = SimpleNamespace(
        id=uuid4(),
        business_id=BUSINESS_ID,
        role="barber",
        barber_id=uuid4(),
        is_active=invalid_state != "inactive_user",
        auth_version=1 if invalid_state == "revoked" else 0,
    )
    barber = SimpleNamespace(
        business_id=OTHER_BUSINESS_ID if invalid_state == "foreign_barber" else BUSINESS_ID,
        is_active=invalid_state != "inactive_barber",
    )
    monkeypatch.setattr(
        "app.api.dependencies.get_settings", lambda: SimpleNamespace(jwt_secret_key=secret)
    )
    monkeypatch.setattr(
        "app.api.dependencies.UserRepository.get_by_id", AsyncMock(return_value=user)
    )
    monkeypatch.setattr(
        "app.api.dependencies.BarberRepository.get_by_id", AsyncMock(return_value=barber)
    )
    token = create_access_token(user_id=user.id, secret=secret, expires_minutes=5)

    response = TestClient(app).get(
        f"/api/v1/businesses/{BUSINESS_ID}/customers",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    isolated_session.commit.assert_not_awaited()


def test_co_owner_cannot_edit_the_primary_owners_account(
    isolated_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = SimpleNamespace(
        id=uuid4(), role="owner", business_id=BUSINESS_ID, is_primary_owner=False
    )
    principal = SimpleNamespace(
        id=RESOURCE_ID, role="owner", business_id=BUSINESS_ID, is_primary_owner=True
    )
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(
        "app.services.auth.UserRepository.get_by_id", AsyncMock(return_value=principal)
    )

    response = TestClient(app).patch(
        f"/api/v1/auth/owner-accounts/{RESOURCE_ID}",
        json={"current_password": "example-password", "is_active": False},
    )

    assert response.status_code == 404
    isolated_session.commit.assert_not_awaited()


@pytest.mark.parametrize("foreign_profile", [False, True])
def test_barber_login_requires_profile_in_the_same_business(
    foreign_profile: bool, isolated_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = SimpleNamespace(
        id=uuid4(),
        business_id=BUSINESS_ID,
        barber_id=RESOURCE_ID,
        role="barber",
        is_active=True,
        login_locked_until=None,
        login_failed_attempts=0,
        password_hash="test-hash",
        auth_version=0,
    )
    barber = SimpleNamespace(
        is_active=True,
        business_id=OTHER_BUSINESS_ID if foreign_profile else BUSINESS_ID,
    )
    monkeypatch.setattr(
        "app.services.auth.UserRepository.get_by_email", AsyncMock(return_value=user)
    )
    monkeypatch.setattr(
        "app.services.auth.BarberRepository.get_by_id", AsyncMock(return_value=barber)
    )
    monkeypatch.setattr("app.services.auth.verify_password", lambda *_: True)
    monkeypatch.setattr(
        "app.api.v1.routes.auth.get_settings",
        lambda: SimpleNamespace(jwt_secret_key="x" * 40, access_token_expire_minutes=60),
    )

    response = TestClient(app).post(
        "/api/v1/auth/token",
        data={"username": "barber@example.com", "password": "example-password"},
    )

    assert response.status_code == (401 if foreign_profile else 200)
    if foreign_profile:
        assert "access_token" not in response.json()


@pytest.mark.parametrize(
    ("method", "path", "lookup", "body", "expected_status"),
    [
        (
            "PATCH",
            "/expenses/{resource}/paid",
            "app.repositories.expense.ExpenseRepository.get_by_id",
            {},
            404,
        ),
        (
            "DELETE",
            "/expenses/{resource}",
            "app.repositories.expense.ExpenseRepository.get_by_id",
            {},
            404,
        ),
        (
            "PATCH",
            "/services/{resource}",
            "app.repositories.service.ServiceRepository.get_by_id",
            {"name": "Example service"},
            404,
        ),
        (
            "GET",
            "/customers/{resource}/appointments",
            "app.repositories.customer.CustomerRepository.get_by_id",
            {},
            404,
        ),
        (
            "PATCH",
            "/appointments/{resource}/confirm",
            "app.repositories.appointment.AppointmentRepository.get_by_id_for_update",
            {},
            409,
        ),
    ],
)
def test_owner_cannot_use_a_foreign_resource_under_own_business_url(
    method: str,
    path: str,
    lookup: str,
    body: dict,
    expected_status: int,
    isolated_session: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(role="owner", business_id=BUSINESS_ID)
    foreign_resource = SimpleNamespace(id=RESOURCE_ID, business_id=OTHER_BUSINESS_ID)
    app.dependency_overrides[get_current_user] = lambda: user
    lookup_mock = AsyncMock(return_value=foreign_resource)
    monkeypatch.setattr(lookup, lookup_mock)
    url = f"/api/v1/businesses/{BUSINESS_ID}" + path.replace("{resource}", str(RESOURCE_ID))

    response = TestClient(app).request(method, url, json=body)

    assert response.status_code == expected_status
    lookup_mock.assert_awaited_once_with(RESOURCE_ID)
    isolated_session.commit.assert_not_awaited()
    isolated_session.delete.assert_not_awaited()
