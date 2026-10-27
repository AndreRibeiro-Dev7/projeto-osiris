"""Recovery requests never expose the generated code or customer existence."""

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.public_booking import PublicBookingSummary


def normalize_mobile(phone: str) -> str:
    """Brazilian mobile numbers, with DDD and optional country code 55."""
    if re.search(r"[^0-9+().\s-]", phone):
        raise ValueError("Informe seu WhatsApp com DDD.")
    digits = re.sub(r"[^0-9]", "", phone)
    if len(digits) == 13 and digits.startswith("55"):
        digits = digits[2:]
    if not re.fullmatch(r"[1-9][0-9]9[0-9]{8}", digits):
        raise ValueError("Informe um celular brasileiro com DDD e nove dígitos.")
    return "55" + digits


class BookingAccessRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=30)
    consent: Literal[True]

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_mobile(value)


class BookingAccessVerify(BaseModel):
    phone: str = Field(min_length=8, max_length=30)
    challenge_id: UUID
    code: str = Field(pattern=r"^[0-9]{6}$")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_mobile(value)


class BookingAccessRequested(BaseModel):
    challenge_id: UUID
    expires_in: int = 300
    resend_after: int = 60
    detail: str = (
        "Solicitação enviada ao WhatsApp. Digite o código recebido para consultar reservas."
    )


class RecoveredBooking(PublicBookingSummary):
    booking_token: UUID


class BookingAccessResult(BaseModel):
    bookings: list[RecoveredBooking]
