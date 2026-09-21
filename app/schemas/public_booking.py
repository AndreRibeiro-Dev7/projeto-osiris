"""Contracts for the customer-facing booking page."""

from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

from app.schemas.appointment import AppointmentResponse


class PublicBarber(BaseModel):
    id: UUID
    full_name: str


class PublicService(BaseModel):
    id: UUID
    name: str
    description: str | None
    duration_minutes: int
    price_cents: int


class PublicBusiness(BaseModel):
    id: UUID
    name: str
    timezone: str
    barbers: list[PublicBarber]
    services: list[PublicService]


class PublicBookingCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=8, max_length=30)
    barber_id: UUID
    service_id: UUID
    starts_at: AwareDatetime
    notes: str | None = Field(default=None, max_length=1000)


class PublicBookingResponse(BaseModel):
    appointment: AppointmentResponse
    business_name: str
    service_name: str
    barber_name: str
    starts_at: datetime
    booking_token: UUID


class PublicBookingSummary(BaseModel):
    business_id: UUID
    business_name: str
    service_name: str
    barber_name: str
    starts_at: datetime
    status: str
