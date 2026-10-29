"""Public endpoints used by the online booking page."""

import logging
from datetime import date
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    InactiveBarberError,
    InvalidAppointmentStatusTransitionError,
    InvalidSchedulingReferenceError,
    ResourceNotFoundError,
    SchedulingConflictError,
)
from app.database.session import get_db_session
from app.integrations.whatsapp_delivery import recovery_is_available, send_booking_access_code
from app.models.public_booking_usage import PublicBookingUsage
from app.repositories.business import BusinessRepository
from app.schemas.appointment import AppointmentRescheduleRequest
from app.schemas.availability import AvailabilityResponse
from app.schemas.booking_access import (
    BookingAccessRequest,
    BookingAccessRequested,
    BookingAccessResult,
    BookingAccessVerify,
)
from app.schemas.error import ErrorResponse
from app.schemas.public_booking import (
    PublicBookingCreate,
    PublicBookingResponse,
    PublicBookingSummary,
    PublicBusiness,
)
from app.services.assistant_usage import BusinessRateLimited, BusinessUsageService
from app.services.availability import AvailabilityService
from app.services.booking_access import (
    BookingAccessService,
    InvalidRecoveryCode,
    RecoveryRateLimited,
)
from app.services.public_booking import PublicBookingService

router = APIRouter(prefix="/public/businesses")
logger = logging.getLogger(__name__)


def require_whatsapp_recovery() -> None:
    if not recovery_is_available(get_settings()):
        raise HTTPException(
            status_code=503, detail="A consulta por WhatsApp ainda não está disponível."
        )


@router.post("/{business_id}/access/request", response_model=BookingAccessRequested)
async def request_booking_access(
    business_id: UUID,
    payload: BookingAccessRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> BookingAccessRequested:
    require_whatsapp_recovery()
    response.headers["Cache-Control"] = "no-store"
    try:
        await PublicBookingService(session).business(business_id)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada.") from error
    settings = get_settings()
    recovery = BookingAccessService(session, settings.jwt_secret_key)
    try:
        challenge_id, code = await recovery.issue(
            business_id, payload.phone, request.client.host if request.client else "unknown"
        )
    except RecoveryRateLimited as error:
        raise HTTPException(
            status_code=429,
            detail="Aguarde antes de solicitar outro código.",
            headers={"Retry-After": str(error.seconds)},
        ) from error
    try:
        await send_booking_access_code(settings=settings, phone=payload.phone, code=code)
    except httpx.HTTPError as error:
        await recovery.invalidate(challenge_id, code)
        # Do not log provider errors: their request bodies contain phone and code.
        logger.warning("WhatsApp booking recovery delivery failed")
        raise HTTPException(
            status_code=503, detail="Não foi possível enviar o código. Tente novamente mais tarde."
        ) from error
    return BookingAccessRequested(challenge_id=challenge_id)


@router.post("/{business_id}/access/verify", response_model=BookingAccessResult)
async def verify_booking_access(
    business_id: UUID,
    payload: BookingAccessVerify,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> BookingAccessResult:
    require_whatsapp_recovery()
    response.headers["Cache-Control"] = "no-store"
    try:
        bookings = await BookingAccessService(session, get_settings().jwt_secret_key).verify(
            business_id,
            payload.phone,
            payload.challenge_id,
            payload.code,
            request.client.host if request.client else "unknown",
        )
    except RecoveryRateLimited as error:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Aguarde antes de tentar novamente.",
            headers={"Retry-After": str(error.seconds)},
        ) from error
    except InvalidRecoveryCode as error:
        raise HTTPException(
            status_code=400,
            detail="Código inválido ou expirado. Solicite outro código se necessário.",
        ) from error
    return BookingAccessResult(bookings=bookings)


@router.get("/appointments/{public_token}", response_model=PublicBookingSummary)
async def get_public_booking(
    public_token: UUID, session: AsyncSession = Depends(get_db_session)
) -> PublicBookingSummary:
    try:
        return await PublicBookingService(session).summary(public_token)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/appointments/{public_token}/cancel", response_model=PublicBookingSummary)
async def cancel_public_booking(
    public_token: UUID, session: AsyncSession = Depends(get_db_session)
) -> PublicBookingSummary:
    try:
        return await PublicBookingService(session).cancel(public_token)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InvalidSchedulingReferenceError, InvalidAppointmentStatusTransitionError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch("/appointments/{public_token}/confirm", response_model=PublicBookingSummary)
async def confirm_public_booking(
    public_token: UUID, session: AsyncSession = Depends(get_db_session)
) -> PublicBookingSummary:
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
async def get_public_business(
    business_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> PublicBusiness:
    try:
        return await PublicBookingService(session).business(business_id)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/{business_id}/barbers/{barber_id}/availability", response_model=AvailabilityResponse)
async def get_public_availability(
    business_id: UUID,
    barber_id: UUID,
    appointment_date: date,
    session: AsyncSession = Depends(get_db_session),
) -> AvailabilityResponse:
    try:
        return await AvailabilityService(session).list_available_slots(
            business_id=business_id, barber_id=barber_id, appointment_date=appointment_date
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.post(
    "/{business_id}/appointments",
    response_model=PublicBookingResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        429: {
            "model": ErrorResponse,
            "description": "Public booking quota exhausted; observe Retry-After.",
            "headers": {"Retry-After": {"schema": {"type": "integer", "minimum": 1}}},
        }
    },
)
async def create_public_booking(
    business_id: UUID, payload: PublicBookingCreate, session: AsyncSession = Depends(get_db_session)
) -> PublicBookingResponse:
    try:
        if await BusinessRepository(session).get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        settings = get_settings()
        await BusinessUsageService(session, PublicBookingUsage).consume(
            business_id,
            per_minute=settings.public_booking_requests_per_minute,
            per_hour=settings.public_booking_requests_per_hour,
        )
        return await PublicBookingService(session).create(business_id, payload)
    except BusinessRateLimited as error:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Limite de tentativas de agendamento atingido. Aguarde {error.seconds} segundos "
                "para tentar novamente. Suas reservas existentes continuam disponíveis."
            ),
            headers={"Retry-After": str(error.seconds)},
        ) from error
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InactiveBarberError, InvalidSchedulingReferenceError, SchedulingConflictError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
