"""Public endpoints used by the online booking page."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InactiveBarberError,
    InvalidAppointmentStatusTransitionError,
    InvalidSchedulingReferenceError,
    ResourceNotFoundError,
    SchedulingConflictError,
)
from app.database.session import get_db_session
from app.schemas.availability import AvailabilityResponse
from app.schemas.appointment import AppointmentRescheduleRequest
from app.schemas.public_booking import PublicBookingCreate, PublicBookingResponse, PublicBookingSummary, PublicBusiness
from app.services.availability import AvailabilityService
from app.services.public_booking import PublicBookingService

router = APIRouter(prefix="/public/businesses")


@router.get("/appointments/{public_token}", response_model=PublicBookingSummary)
async def get_public_booking(public_token: UUID, session: AsyncSession = Depends(get_db_session)) -> PublicBookingSummary:
    try:
        return await PublicBookingService(session).summary(public_token)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/appointments/{public_token}/cancel", response_model=PublicBookingSummary)
async def cancel_public_booking(public_token: UUID, session: AsyncSession = Depends(get_db_session)) -> PublicBookingSummary:
    try:
        return await PublicBookingService(session).cancel(public_token)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InvalidSchedulingReferenceError, InvalidAppointmentStatusTransitionError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch("/appointments/{public_token}/confirm", response_model=PublicBookingSummary)
async def confirm_public_booking(public_token: UUID, session: AsyncSession = Depends(get_db_session)) -> PublicBookingSummary:
    """Allow the customer to confirm attendance using the secure booking token."""
    try:
        return await PublicBookingService(session).confirm(public_token)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InvalidSchedulingReferenceError, InvalidAppointmentStatusTransitionError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch("/appointments/{public_token}/reschedule", response_model=PublicBookingSummary)
async def reschedule_public_booking(
    public_token: UUID,
    payload: AppointmentRescheduleRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PublicBookingSummary:
    """Allow a customer to move an active booking using its secure token."""
    try:
        return await PublicBookingService(session).reschedule(public_token, payload)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (
        InactiveBarberError,
        InvalidAppointmentStatusTransitionError,
        InvalidSchedulingReferenceError,
        SchedulingConflictError,
    ) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/{business_id}", response_model=PublicBusiness)
async def get_public_business(business_id: UUID, session: AsyncSession = Depends(get_db_session)) -> PublicBusiness:
    try:
        return await PublicBookingService(session).business(business_id)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/{business_id}/barbers/{barber_id}/availability", response_model=AvailabilityResponse)
async def get_public_availability(business_id: UUID, barber_id: UUID, appointment_date: date, session: AsyncSession = Depends(get_db_session)) -> AvailabilityResponse:
    try:
        return await AvailabilityService(session).list_available_slots(business_id=business_id, barber_id=barber_id, appointment_date=appointment_date)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error


@router.post("/{business_id}/appointments", response_model=PublicBookingResponse, status_code=status.HTTP_201_CREATED)
async def create_public_booking(business_id: UUID, payload: PublicBookingCreate, session: AsyncSession = Depends(get_db_session)) -> PublicBookingResponse:
    try:
        return await PublicBookingService(session).create(business_id, payload)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InactiveBarberError, InvalidSchedulingReferenceError, SchedulingConflictError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
