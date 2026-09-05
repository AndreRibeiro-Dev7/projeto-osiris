"""Endpoints for business, barber and customer registration."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateResourceError,
    InactiveBarberError,
    InvalidAppointmentStatusTransitionError,
    InvalidSchedulingReferenceError,
    ResourceNotFoundError,
    SchedulingConflictError,
)
from app.database.session import get_db_session
from app.schemas.appointment import AppointmentCreate, AppointmentResponse
from app.schemas.availability import (
    AvailabilityResponse,
    BarberScheduleResponse,
    BarberScheduleUpsert,
)
from app.schemas.barber import BarberCreate, BarberResponse
from app.schemas.business import BusinessCreate, BusinessResponse
from app.schemas.customer import CustomerCreate, CustomerResponse
from app.schemas.error import ErrorResponse
from app.services.appointment import AppointmentService
from app.services.availability import AvailabilityService
from app.services.barber import BarberService
from app.services.business import BusinessService
from app.services.customer import CustomerService

router = APIRouter(prefix="/businesses")


@router.post("", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
async def create_business(
    payload: BusinessCreate,
    session: AsyncSession = Depends(get_db_session),
) -> BusinessResponse:
    """Register a barbershop."""
    try:
        business = await BusinessService(session).create(payload)
        return BusinessResponse.model_validate(business)
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    business_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> BusinessResponse:
    """Return one barbershop."""
    try:
        business = await BusinessService(session).get(business_id)
        return BusinessResponse.model_validate(business)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{business_id}/barbers",
    response_model=BarberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_barber(
    business_id: UUID,
    payload: BarberCreate,
    session: AsyncSession = Depends(get_db_session),
) -> BarberResponse:
    """Register a professional at a barbershop."""
    try:
        barber = await BarberService(session).create(business_id, payload)
        return BarberResponse.model_validate(barber)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/{business_id}/barbers", response_model=list[BarberResponse])
async def list_barbers(
    business_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[BarberResponse]:
    """List all professionals registered at a barbershop."""
    try:
        barbers = await BarberService(session).list(business_id)
        return [BarberResponse.model_validate(barber) for barber in barbers]
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{business_id}/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer(
    business_id: UUID,
    payload: CustomerCreate,
    session: AsyncSession = Depends(get_db_session),
) -> CustomerResponse:
    """Register a customer at a barbershop."""
    try:
        customer = await CustomerService(session).create(business_id, payload)
        return CustomerResponse.model_validate(customer)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/{business_id}/customers", response_model=list[CustomerResponse])
async def list_customers(
    business_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[CustomerResponse]:
    """List customers registered at a barbershop."""
    try:
        customers = await CustomerService(session).list(business_id)
        return [CustomerResponse.model_validate(customer) for customer in customers]
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{business_id}/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    business_id: UUID,
    payload: AppointmentCreate,
    session: AsyncSession = Depends(get_db_session),
) -> AppointmentResponse:
    """Reserve an available time range with a barber."""
    try:
        appointment = await AppointmentService(session).create(business_id, payload)
        return AppointmentResponse.model_validate(appointment)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InactiveBarberError, SchedulingConflictError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.get(
    "/{business_id}/barbers/{barber_id}/appointments",
    response_model=list[AppointmentResponse],
)
async def list_barber_appointments(
    business_id: UUID,
    barber_id: UUID,
    appointment_date: date,
    session: AsyncSession = Depends(get_db_session),
) -> list[AppointmentResponse]:
    """List a barber's active schedule for one local business day."""
    try:
        appointments = await AppointmentService(session).list_for_barber(
            business_id=business_id,
            barber_id=barber_id,
            appointment_date=appointment_date,
        )
        return [AppointmentResponse.model_validate(appointment) for appointment in appointments]
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.put(
    "/{business_id}/barbers/{barber_id}/schedule/{weekday}",
    response_model=BarberScheduleResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Barber not found.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "The barber does not belong to the requested business.",
        },
    },
)
async def upsert_barber_schedule(
    business_id: UUID,
    barber_id: UUID,
    weekday: Annotated[int, Path(ge=0, le=6, description="Monday=0, Sunday=6")],
    payload: BarberScheduleUpsert,
    session: AsyncSession = Depends(get_db_session),
) -> BarberScheduleResponse:
    """Create or replace a barber's recurring work schedule for one weekday."""
    try:
        schedule = await AvailabilityService(session).upsert_schedule(
            business_id=business_id,
            barber_id=barber_id,
            weekday=weekday,
            payload=payload,
        )
        return BarberScheduleResponse.model_validate(schedule)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.get(
    "/{business_id}/barbers/{barber_id}/availability",
    response_model=AvailabilityResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Business or barber not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "The barber is inactive.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "The barber does not belong to the requested business.",
        },
    },
)
async def list_barber_availability(
    business_id: UUID,
    barber_id: UUID,
    appointment_date: date,
    session: AsyncSession = Depends(get_db_session),
) -> AvailabilityResponse:
    """List free appointment slots for one local business day."""
    try:
        return await AvailabilityService(session).list_available_slots(
            business_id=business_id,
            barber_id=barber_id,
            appointment_date=appointment_date,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InactiveBarberError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.patch(
    "/{business_id}/appointments/{appointment_id}/confirm",
    response_model=AppointmentResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Appointment not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "The appointment does not belong to the business or cannot be confirmed "
                "from its current status."
            ),
        },
    },
)
async def confirm_appointment(
    business_id: UUID,
    appointment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AppointmentResponse:
    """Mark a scheduled appointment as confirmed."""
    try:
        appointment = await AppointmentService(session).confirm(business_id, appointment_id)
        return AppointmentResponse.model_validate(appointment)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InvalidSchedulingReferenceError, InvalidAppointmentStatusTransitionError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch(
    "/{business_id}/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Appointment not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "The appointment does not belong to the business or cannot be cancelled "
                "from its current status."
            ),
        },
    },
)
async def cancel_appointment(
    business_id: UUID,
    appointment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AppointmentResponse:
    """Cancel a scheduled or confirmed appointment."""
    try:
        appointment = await AppointmentService(session).cancel(business_id, appointment_id)
        return AppointmentResponse.model_validate(appointment)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InvalidSchedulingReferenceError, InvalidAppointmentStatusTransitionError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
