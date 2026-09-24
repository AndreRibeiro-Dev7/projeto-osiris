"""Authentication use cases."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateResourceError,
    InvalidCredentialsError,
    ResourceNotFoundError,
)
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.barber import BarberRepository
from app.repositories.business import BusinessRepository
from app.repositories.user import UserRepository


class AuthService:
    """Create the first owner and validate credentials."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._businesses = BusinessRepository(session)
        self._barbers = BarberRepository(session)
        self._users = UserRepository(session)

    async def bootstrap_owner(self, *, business_id: UUID, email: str, password: str) -> User:
        """Create the first and only bootstrap owner for a business."""
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        if await self._users.count_for_business(business_id) > 0:
            raise DuplicateResourceError("This business already has an owner.")
        if await self._users.get_by_email(email) is not None:
            raise DuplicateResourceError("An account with this email already exists.")

        user = await self._users.create(
            business_id=business_id,
            email=email,
            password_hash=hash_password(password),
        )
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError("The owner account could not be created.") from error
        await self._session.refresh(user)
        return user

    async def create_barber_account(
        self,
        *,
        owner: User,
        barber_id: UUID,
        email: str,
        password: str,
    ) -> User:
        """Create a restricted login linked to one professional."""
        if owner.role != "owner":
            raise ResourceNotFoundError("Owner access is required.")
        barber = await self._barbers.get_by_id(barber_id)
        if barber is None or barber.business_id != owner.business_id:
            raise ResourceNotFoundError("Barber not found.")
        if await self._users.get_by_barber_id(barber_id) is not None:
            raise DuplicateResourceError("This professional already has a login account.")
        if await self._users.get_by_email(email) is not None:
            raise DuplicateResourceError("An account with this email already exists.")
        user = await self._users.create(
            business_id=owner.business_id,
            barber_id=barber_id,
            email=email,
            password_hash=hash_password(password),
            role="barber",
        )
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError(
                "The professional account could not be created."
            ) from error
        await self._session.refresh(user)
        return user

    async def update_barber_account(
        self,
        *,
        owner: User,
        barber_id: UUID,
        current_password: str,
        email: str | None,
        password: str | None,
        password_confirmation: str | None,
        is_active: bool | None,
    ) -> User:
        """Update credentials or availability for a professional account."""
        account = await self._users.get_by_barber_id(barber_id)
        if (
            owner.role != "owner"
            or account is None
            or account.business_id != owner.business_id
            or account.role != "barber"
        ):
            raise ResourceNotFoundError("Professional account not found.")
        if not verify_password(current_password, owner.password_hash):
            raise InvalidCredentialsError("Current owner password is incorrect.")
        if password != password_confirmation:
            raise InvalidCredentialsError("The new password and confirmation must match.")
        if email is not None:
            existing = await self._users.get_by_email(email)
            if existing is not None and existing.id != account.id:
                raise DuplicateResourceError("An account with this email already exists.")
            account.email = email.lower()
        if password is not None:
            account.password_hash = hash_password(password)
        if is_active is not None:
            account.is_active = is_active
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError(
                "The professional account could not be updated."
            ) from error
        await self._session.refresh(account)
        return account

    async def delete_barber_account(self, *, owner: User, barber_id: UUID) -> None:
        """Permanently remove one professional login without deleting the barber."""
        account = await self._users.get_by_barber_id(barber_id)
        if (
            owner.role != "owner"
            or account is None
            or account.business_id != owner.business_id
            or account.role != "barber"
        ):
            raise ResourceNotFoundError("Professional account not found.")
        await self._session.delete(account)
        await self._session.commit()

    async def authenticate(self, *, email: str, password: str) -> User | None:
        """Return an active user only when both credentials are valid."""
        user = await self._users.get_by_email(email)
        if user is None or not user.is_active:
            return None
        return user if verify_password(password, user.password_hash) else None

    async def change_password(
        self, *, user: User, current_password: str, new_password: str
    ) -> bool:
        """Replace an owner's password after verifying the current one."""
        if not verify_password(current_password, user.password_hash):
            return False
        if verify_password(new_password, user.password_hash):
            return False
        user.password_hash = hash_password(new_password)
        await self._session.commit()
        return True

    async def request_email_change(
        self, *, user: User, current_password: str, new_email: str
    ) -> str | None:
        """Create a short-lived verification code for a replacement email."""
        if not verify_password(current_password, user.password_hash):
            return None
        normalized_email = new_email.lower()
        email_owner = await self._users.get_by_email(normalized_email)
        if email_owner is not None and email_owner.id != user.id:
            raise DuplicateResourceError("An account with this email already exists.")
        code = f"{secrets.randbelow(1_000_000):06d}"
        user.pending_email = normalized_email
        user.email_verification_code_hash = self._email_code_hash(user.id, code)
        user.email_verification_expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await self._session.commit()
        return code

    async def confirm_email_change(self, *, user: User, code: str) -> User | None:
        """Apply a pending email after validating its code and expiry."""
        if (
            user.pending_email is None
            or user.email_verification_code_hash is None
            or user.email_verification_expires_at is None
            or user.email_verification_expires_at < datetime.now(UTC)
            or not hmac.compare_digest(
                user.email_verification_code_hash,
                self._email_code_hash(user.id, code),
            )
        ):
            return None
        email_owner = await self._users.get_by_email(user.pending_email)
        if email_owner is not None and email_owner.id != user.id:
            raise DuplicateResourceError("An account with this email already exists.")
        user.email = user.pending_email
        user.pending_email = None
        user.email_verification_code_hash = None
        user.email_verification_expires_at = None
        try:
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise DuplicateResourceError("An account with this email already exists.") from error
        await self._session.refresh(user)
        return user

    @staticmethod
    def _email_code_hash(user_id: UUID, code: str) -> str:
        return hashlib.sha256(f"{user_id}:{code}".encode()).hexdigest()
