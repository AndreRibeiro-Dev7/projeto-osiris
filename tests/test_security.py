from uuid import uuid4

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verified() -> None:
    password = "uma-senha-forte-123"
    encoded = hash_password(password)

    assert encoded != password
    assert verify_password(password, encoded)
    assert not verify_password("senha-incorreta", encoded)


def test_access_token_round_trip_and_rejects_wrong_secret() -> None:
    user_id = uuid4()
    secret_a = "a" * 64
    secret_b = "b" * 64
    token = create_access_token(user_id=user_id, secret=secret_a, expires_minutes=5)

    assert decode_access_token(token, secret=secret_a) == user_id
    assert decode_access_token(token, secret=secret_b) is None
