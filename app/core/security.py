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


def create_access_token(*, user_id: UUID, secret: str, expires_minutes: int) -> str:
    """Create a signed token containing only the account identifier."""
    expires_at = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires_at}, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> UUID | None:
    """Validate a token and return its subject when valid."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        return UUID(subject) if isinstance(subject, str) else None
    except (InvalidTokenError, ValueError):
        return None
