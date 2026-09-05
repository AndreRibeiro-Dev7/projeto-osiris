import app.models  # noqa: F401  # Register all models in Base.metadata.
from app.database.base import Base


def test_scheduling_models_are_registered_in_metadata() -> None:
    assert set(Base.metadata.tables) == {
        "appointments",
        "barber_schedules",
        "barbers",
        "businesses",
        "customers",
    }


def test_appointments_require_a_valid_time_range() -> None:
    appointments = Base.metadata.tables["appointments"]
    constraint_names = {constraint.name for constraint in appointments.constraints}

    assert "ck_appointments_valid_time_range" in constraint_names
