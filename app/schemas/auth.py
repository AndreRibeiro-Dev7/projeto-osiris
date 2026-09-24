"""Authentication API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.appointment import AppointmentStatus, PaymentMethod


class OwnerBootstrapRequest(BaseModel):
    """Credentials used to create the first owner of an existing business."""

    business_id: UUID
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class TokenResponse(BaseModel):
    """Bearer token returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class PasswordChangeRequest(BaseModel):
    """Current credentials and a replacement password."""

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class EmailChangeRequest(BaseModel):
    """Current password and a replacement login email."""

    current_password: str = Field(min_length=1, max_length=128)
    new_email: EmailStr


class EmailChangeRequestedResponse(BaseModel):
    """Result of requesting an email verification code."""

    detail: str
    expires_in_seconds: int
    development_code: str | None = None


class EmailChangeConfirmRequest(BaseModel):
    """Six-digit code sent to the pending email address."""

    code: str = Field(pattern=r"^\d{6}$")


class CurrentUserResponse(BaseModel):
    """Safe representation of the authenticated account."""

    id: UUID
    business_id: UUID
    email: EmailStr
    role: str
    barber_id: UUID | None = None


class BarberAccountCreate(BaseModel):
    """Credentials created by an owner for one professional."""

    barber_id: UUID
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class BarberAccountUpdate(BaseModel):
    """Owner-controlled changes to a professional login account."""

    current_password: str = Field(min_length=1, max_length=128)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=12, max_length=128)
    password_confirmation: str | None = Field(default=None, min_length=12, max_length=128)
    is_active: bool | None = None

    @model_validator(mode="after")
    def matching_password_confirmation(self) -> "BarberAccountUpdate":
        """Reject partial or mismatched password replacements."""
        if self.password != self.password_confirmation:
            raise ValueError("The new password and confirmation must match.")
        return self


class BarberAccountResponse(BaseModel):
    """Safe representation of a professional login account."""

    id: UUID
    business_id: UUID
    barber_id: UUID
    email: EmailStr
    is_active: bool


class BarberProfileResponse(BaseModel):
    """Identity and business data required by the restricted dashboard."""

    business_id: UUID
    business_name: str
    timezone: str
    barber_id: UUID
    full_name: str
    phone: str
    commission_percentage: int


class BarberAppointmentResponse(BaseModel):
    """Appointment data visible to its assigned professional."""

    id: UUID
    public_token: UUID
    customer_id: UUID
    service_id: UUID | None
    customer_name: str
    customer_phone: str
    service_name: str
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    price_cents: int | None
    payment_method: PaymentMethod | None
    notes: str | None
