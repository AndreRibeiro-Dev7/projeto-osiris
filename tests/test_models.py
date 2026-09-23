import app.models  # noqa: F401  # Register all models in Base.metadata.
from app.database.base import Base


def test_scheduling_models_are_registered_in_metadata() -> None:
    assert set(Base.metadata.tables) == {
        "appointments",
        "assistant_conversations",
        "barber_schedules",
        "barber_time_off",
        "barbers",
        "businesses",
        "business_closures",
        "customers",
        "expenses",
        "services",
        "users",
    }


def test_appointments_require_a_valid_time_range() -> None:
    appointments = Base.metadata.tables["appointments"]
    constraint_names = {constraint.name for constraint in appointments.constraints}

    assert "ck_appointments_valid_time_range" in constraint_names


def test_customer_loyalty_redemptions_cannot_be_negative() -> None:
    customers = Base.metadata.tables["customers"]
    constraint_names = {constraint.name for constraint in customers.constraints}

    assert "ck_customers_loyalty_rewards_redeemed_non_negative" in constraint_names


def test_users_support_restricted_barber_accounts() -> None:
    users = Base.metadata.tables["users"]
    constraint_names = {constraint.name for constraint in users.constraints}

    assert "role" in users.columns
    assert "barber_id" in users.columns
    assert "ck_users_role" in constraint_names
    assert users.columns["barber_id"].unique
