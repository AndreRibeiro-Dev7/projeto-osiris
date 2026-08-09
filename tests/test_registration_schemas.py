import pytest
from pydantic import ValidationError

from app.schemas.barber import BarberCreate
from app.schemas.business import BusinessCreate
from app.schemas.customer import CustomerCreate


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
