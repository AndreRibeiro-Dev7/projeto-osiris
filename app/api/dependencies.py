"""Shared API authentication dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.database.session import get_db_session
from app.models.user import User
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Resolve the active account represented by a bearer token."""
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SECRET_KEY is not configured.",
        )
    user_id = decode_access_token(token, secret=settings.jwt_secret_key)
    user = await UserRepository(session).get_by_id(user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_business_access(
    business_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Reject cross-tenant access even when the resource identifier exists."""
    if current_user.business_id != business_id or current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access is required for this business.",
        )
    return current_user
