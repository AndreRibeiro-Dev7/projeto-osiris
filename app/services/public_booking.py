"""Customer-facing booking use cases."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidSchedulingReferenceError, ResourceNotFoundError
from app.repositories.barber import BarberRepository
from app.repositories.business import BusinessRepository
from app.repositories.customer import CustomerRepository
from app.repositories.service import ServiceRepository
from app.repositories.appointment import AppointmentRepository
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRescheduleRequest,
    AppointmentResponse,
)
from app.schemas.public_booking import (
    PublicBarber,
    PublicBookingCreate,
    PublicBookingResponse,
    PublicBookingSummary,
    PublicBusiness,
    PublicService,
)
from app.services.appointment import AppointmentService


class PublicBookingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._businesses = BusinessRepository(session)
        self._barbers = BarberRepository(session)
        self._customers = CustomerRepository(session)
        self._services = ServiceRepository(session)
        self._appointments = AppointmentRepository(session)

    async def business(self, business_id: UUID) -> PublicBusiness:
        business = await self._businesses.get_by_id(business_id)
        if business is None:
            raise ResourceNotFoundError("Business not found.")
        barbers = await self._barbers.list_by_business(business_id)
        services = await self._services.list_by_business(business_id)
        return PublicBusiness(
            id=business.id,
            name=business.name,
            timezone=business.timezone,
            barbers=[PublicBarber(id=item.id, full_name=item.full_name) for item in barbers if item.is_active],
            services=[PublicService(id=item.id, name=item.name, description=item.description, duration_minutes=item.duration_minutes, price_cents=item.price_cents) for item in services if item.is_active],
        )

    async def create(self, business_id: UUID, payload: PublicBookingCreate) -> PublicBookingResponse:
        business = await self._businesses.get_by_id(business_id)
        if business is None:
            raise ResourceNotFoundError("Business not found.")
        barber = await self._barbers.get_by_id(payload.barber_id)
        service = await self._services.get_by_id(payload.service_id)
        if barber is None or barber.business_id != business_id or not barber.is_active:
            raise InvalidSchedulingReferenceError("Professional is not available.")
        if service is None or service.business_id != business_id or not service.is_active:
            raise InvalidSchedulingReferenceError("Service is not available.")
        customer = await self._customers.get_by_business_and_phone(business_id, payload.customer_phone)
        if customer is None:
            customer = await self._customers.create(business_id=business_id, full_name=payload.customer_name, phone=payload.customer_phone)
            await self._session.flush()
        ends_at = payload.starts_at + timedelta(minutes=service.duration_minutes)
        appointment = await AppointmentService(self._session).create(
            business_id,
            AppointmentCreate(barber_id=barber.id, customer_id=customer.id, service_id=service.id, starts_at=payload.starts_at, ends_at=ends_at, notes=payload.notes),
        )
        return PublicBookingResponse(
            appointment=AppointmentResponse.model_validate(appointment),
            business_name=business.name,
            service_name=service.name,
            barber_name=barber.full_name,
            starts_at=appointment.starts_at,
            booking_token=appointment.public_token,
        )

    async def summary(self, public_token: UUID) -> PublicBookingSummary:
        appointment = await self._appointments.get_by_public_token(public_token)
        if appointment is None:
            raise ResourceNotFoundError("Appointment not found.")
        business = await self._businesses.get_by_id(appointment.business_id)
        barber = await self._barbers.get_by_id(appointment.barber_id)
        service = await self._services.get_by_id(appointment.service_id) if appointment.service_id else None
        if business is None or barber is None:
            raise ResourceNotFoundError("Appointment not found.")
        return PublicBookingSummary(
            business_id=business.id,
            business_name=business.name,
            service_name=service.name if service else "Atendimento",
            barber_name=barber.full_name,
            starts_at=appointment.starts_at,
            status=appointment.status.value,
        )

    async def cancel(self, public_token: UUID) -> PublicBookingSummary:
        appointment = await self._appointments.get_by_public_token(public_token)
        if appointment is None:
            raise ResourceNotFoundError("Appointment not found.")
        await AppointmentService(self._session).cancel(appointment.business_id, appointment.id)
        return await self.summary(public_token)

    async def confirm(self, public_token: UUID) -> PublicBookingSummary:
        appointment = await self._appointments.get_by_public_token(public_token)
        if appointment is None:
            raise ResourceNotFoundError("Appointment not found.")
        await AppointmentService(self._session).confirm(appointment.business_id, appointment.id)
        return await self.summary(public_token)

    async def reschedule(
        self, public_token: UUID, payload: AppointmentRescheduleRequest
    ) -> PublicBookingSummary:
        appointment = await self._appointments.get_by_public_token(public_token)
        if appointment is None:
            raise ResourceNotFoundError("Appointment not found.")
        await AppointmentService(self._session).reschedule(
            appointment.business_id, appointment.id, payload
        )
        return await self.summary(public_token)
