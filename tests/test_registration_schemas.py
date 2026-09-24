import pytest
from pydantic import ValidationError

from app.schemas.appointment import AppointmentCreate
from app.schemas.auth import BarberAccountUpdate
from app.schemas.availability import BarberScheduleUpsert
from app.schemas.barber import BarberCreate
from app.schemas.business import BusinessCreate, BusinessUpdate
from app.schemas.customer import CustomerCreate, CustomerUpdate


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (BusinessCreate, {"name": "", "phone": "5511999999999"}),
        (BarberCreate, {"full_name": "A", "phone": "5511999999999"}),
        (CustomerCreate, {"full_name": "Cliente", "phone": "123"}),
    ],
)
def test_registration_schemas_reject_invalid_data(
    schema: type[BusinessCreate | BarberCreate | CustomerCreate],
    payload: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_appointment_schema_rejects_an_invalid_time_range() -> None:
    with pytest.raises(ValidationError):
        AppointmentCreate.model_validate(
            {
                "barber_id": "0d15a1e1-31bd-437d-809f-71cfbe12569e",
                "customer_id": "fea93fe2-cbae-449b-b0f5-5d793e3ad4b2",
                "starts_at": "2026-08-10T15:00:00Z",
                "ends_at": "2026-08-10T14:30:00Z",
            }
        )


def test_barber_schedule_rejects_an_invalid_working_window() -> None:
    with pytest.raises(ValidationError):
        BarberScheduleUpsert.model_validate(
            {
                "starts_at": "18:00:00",
                "ends_at": "09:00:00",
                "slot_duration_minutes": 30,
            }
        )


def test_customer_update_validates_contact_data() -> None:
    customer = CustomerUpdate(full_name="André Ribeiro", phone="11999999999")

    assert customer.full_name == "André Ribeiro"
    assert customer.phone == "11999999999"


def test_business_loyalty_target_must_be_between_two_and_fifty() -> None:
    with pytest.raises(ValidationError):
        BusinessUpdate(
            name="Barbearia Osiris",
            phone="11999999999",
            timezone="America/Sao_Paulo",
            loyalty_target=1,
            loyalty_reward="Corte grátis",
        )


def test_barber_account_update_requires_matching_password_confirmation() -> None:
    with pytest.raises(ValidationError):
        BarberAccountUpdate(
            current_password="senha-atual-do-dono",
            password="nova-senha-forte-123",
            password_confirmation="nova-senha-diferente-456",
        )


def test_barber_account_update_requires_owner_current_password() -> None:
    with pytest.raises(ValidationError):
        BarberAccountUpdate(email="barbeiro@osiris.com")
