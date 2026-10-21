"""Password hashing and signed access tokens."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password with the recommended Argon2 parameters."""
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    """Check a plaintext password against its stored hash."""
    return password_hash.verify(password, encoded_hash)


def create_access_token(
    *, user_id: UUID, secret: str, expires_minutes: int, auth_version: int = 0
) -> str:
    """Create a signed token containing only the account identifier."""
    expires_at = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    return jwt.encode(
        {"sub": str(user_id), "ver": auth_version, "exp": expires_at},
        secret,
        algorithm=ALGORITHM,
    )


def decode_access_token_identity(token: str, *, secret: str) -> tuple[UUID, int] | None:
    """Validate a token and return its account identifier and credential version."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        version = payload.get("ver", 0)
        if not isinstance(subject, str) or not isinstance(version, int):
            return None
        return UUID(subject), version
    except (InvalidTokenError, ValueError):
        return None


def decode_access_token(token: str, *, secret: str) -> UUID | None:
    """Validate a token and return its subject when valid."""
    identity = decode_access_token_identity(token, secret=secret)
    return identity[0] if identity else None
