"""Authentication API contracts."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


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
