"""Single-use recovery codes, persisted limits and tenant-scoped lookup."""

import hashlib
import hmac
import math
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_now
from app.models.appointment import Appointment, AppointmentStatus
from app.models.booking_access import BookingAccessChallenge, BookingAccessThrottle
from app.models.customer import Customer
from app.schemas.booking_access import RecoveredBooking
from app.services.public_booking import PublicBookingService


class RecoveryRateLimited(Exception):
    def __init__(self, seconds: int) -> None:
        self.seconds = max(1, seconds)


class InvalidRecoveryCode(Exception):
    pass


class BookingAccessService:
    def __init__(self, session: AsyncSession, secret: str) -> None:
        self.session = session
        self.secret = secret

    def digest(self, purpose: str, value: str) -> str:
        return hmac.new(
            self.secret.encode(), f"booking-access:{purpose}:{value}".encode(), hashlib.sha256
        ).hexdigest()

    async def _limit(self, key: str, maximum: int, minutes: int) -> None:
        now = utc_now()
        fingerprint = self.digest("limit", key)
        await self.session.execute(
            insert(BookingAccessThrottle)
            .values(key=fingerprint, window_started_at=now, requests=0)
            .on_conflict_do_nothing(index_elements=["key"])
        )
        row = (
            await self.session.scalars(
                select(BookingAccessThrottle)
                .where(BookingAccessThrottle.key == fingerprint)
                .with_for_update()
            )
        ).one()
        if now >= row.window_started_at + timedelta(minutes=minutes):
            row.window_started_at, row.requests = now, 0
        if row.requests >= maximum:
            await self._rate_limited(
                math.ceil(
                    (row.window_started_at + timedelta(minutes=minutes) - now).total_seconds()
                )
            )
        row.requests += 1

    async def _rate_limited(self, seconds: int) -> None:
        await self.session.commit()
        raise RecoveryRateLimited(seconds)

    async def issue(self, business_id: UUID, phone: str, ip: str) -> tuple[UUID, str]:
        now = utc_now()
        # All identifiers are keyed hashes. Expired rate windows are removed opportunistically.
        await self.session.execute(
            delete(BookingAccessThrottle).where(
                BookingAccessThrottle.window_started_at < now - timedelta(days=1)
            )
        )
        await self.session.execute(
            delete(BookingAccessChallenge).where(
                BookingAccessChallenge.window_started_at < now - timedelta(days=1)
            )
        )
        await self._limit(f"issue-ip:{ip}", 10, 15)
        await self._limit("issue-global", 100, 60)
        fingerprint = self.digest("phone", f"{business_id}:{phone}")
        await self.session.execute(
            insert(BookingAccessChallenge)
            .values(
                id=uuid4(),
                business_id=business_id,
                subject_hash=fingerprint,
                window_started_at=now,
                requests=0,
                attempts=0,
            )
            .on_conflict_do_nothing(index_elements=["subject_hash"])
        )
        row = (
            await self.session.scalars(
                select(BookingAccessChallenge)
                .where(BookingAccessChallenge.subject_hash == fingerprint)
                .with_for_update()
            )
        ).one()
        if row.last_sent_at and now < row.last_sent_at + timedelta(seconds=60):
            await self._rate_limited(
                math.ceil((row.last_sent_at + timedelta(seconds=60) - now).total_seconds())
            )
        if now >= row.window_started_at + timedelta(hours=1):
            row.window_started_at, row.requests = now, 0
        if row.requests >= 5:
            await self._rate_limited(
                math.ceil((row.window_started_at + timedelta(hours=1) - now).total_seconds())
            )
        code = f"{secrets.randbelow(1_000_000):06d}"
        row.code_hash = self.digest("code", f"{row.id}:{code}")
        row.expires_at = now + timedelta(minutes=5)
        row.last_sent_at, row.attempts = now, 0
        row.requests += 1
        challenge_id = row.id
        await self.session.commit()
        return challenge_id, code

    async def invalidate(self, challenge_id: UUID, code: str) -> None:
        # A late delivery failure must never invalidate a newer code.
        await self.session.execute(
            update(BookingAccessChallenge)
            .where(
                BookingAccessChallenge.id == challenge_id,
                BookingAccessChallenge.code_hash == self.digest("code", f"{challenge_id}:{code}"),
            )
            .values(code_hash=None)
        )
        await self.session.commit()

    async def verify(
        self, business_id: UUID, phone: str, challenge_id: UUID, code: str, ip: str
    ) -> list[RecoveredBooking]:
        await self._limit(f"verify-ip:{ip}", 30, 15)
        row = (
            await self.session.scalars(
                select(BookingAccessChallenge)
                .where(BookingAccessChallenge.id == challenge_id)
                .with_for_update()
            )
        ).one_or_none()
        if (
            row is None
            or row.business_id != business_id
            or not hmac.compare_digest(
                row.subject_hash, self.digest("phone", f"{business_id}:{phone}")
            )
            or not row.code_hash
            or not row.expires_at
            or row.expires_at <= utc_now()
            or row.attempts >= 5
        ):
            await self.session.commit()
            raise InvalidRecoveryCode
        row.attempts += 1
        if not hmac.compare_digest(row.code_hash, self.digest("code", f"{row.id}:{code}")):
            if row.attempts >= 5:
                row.code_hash = None
            await self.session.commit()
            raise InvalidRecoveryCode
        row.code_hash = None
        await self.session.commit()
        return await self._bookings_for_verified_phone(business_id, phone)

    async def _bookings_for_verified_phone(
        self, business_id: UUID, phone: str
    ) -> list[RecoveredBooking]:
        normalized = func.regexp_replace(Customer.phone, "[^0-9]", "", "g")
        appointments = (
            await self.session.scalars(
                select(Appointment)
                .join(Customer, Appointment.customer_id == Customer.id)
                .where(
                    Customer.business_id == business_id,
                    Appointment.business_id == business_id,
                    normalized.in_([phone, phone[2:]]),
                    Appointment.starts_at > utc_now(),
                    Appointment.status.in_(
                        [AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]
                    ),
                )
                .order_by(Appointment.starts_at)
                .limit(20)
            )
        ).all()
        result = []
        for appointment in appointments:
            summary = await PublicBookingService(self.session).summary(appointment.public_token)
            result.append(
                RecoveredBooking(**summary.model_dump(), booking_token=appointment.public_token)
            )
        return result
