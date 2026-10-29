import app.models  # noqa: F401  # Register all models in Base.metadata.
from app.database.base import Base


def test_scheduling_models_are_registered_in_metadata() -> None:
    assert set(Base.metadata.tables) == {
        "appointments",
        "audit_logs",
        "assistant_conversations",
        "assistant_usage_limits",
        "public_booking_usage_limits",
        "barber_schedules",
        "barber_time_off",
        "barbers",
        "businesses",
        "business_closures",
        "booking_access_challenges",
        "booking_access_throttles",
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


def test_users_identify_the_primary_owner() -> None:
    users = Base.metadata.tables["users"]

    assert "is_primary_owner" in users.columns
    assert users.columns["is_primary_owner"].nullable is False


def test_users_support_secure_password_recovery() -> None:
    users = Base.metadata.tables["users"]

    assert "password_reset_code_hash" in users.columns
    assert "password_reset_expires_at" in users.columns
    assert "password_reset_attempts" in users.columns
    assert "login_failed_attempts" in users.columns
    assert "login_locked_until" in users.columns
    assert "auth_version" in users.columns
