"""Owner authentication endpoints."""

import hmac
from datetime import date
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import DuplicateResourceError, ResourceNotFoundError
from app.core.security import create_access_token
from app.database.session import get_db_session
from app.integrations.email_delivery import send_email_change_code
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.service import Service
from app.models.user import User
from app.repositories.appointment import AppointmentRepository
from app.repositories.barber import BarberRepository
from app.repositories.business import BusinessRepository
from app.schemas.appointment import AppointmentCompleteRequest
from app.schemas.auth import (
    BarberAccountCreate,
    BarberAccountResponse,
    BarberAppointmentResponse,
    BarberProfileResponse,
    CurrentUserResponse,
    EmailChangeConfirmRequest,
    EmailChangeRequest,
    EmailChangeRequestedResponse,
    OwnerBootstrapRequest,
    PasswordChangeRequest,
    TokenResponse,
)
from app.services.appointment import AppointmentService
from app.services.auth import AuthService

router = APIRouter(prefix="/auth")


def bootstrap_is_allowed(
    *,
    environment: str,
    enabled: bool,
    configured_token: str,
    received_token: str | None,
) -> bool:
    """Allow local setup or a production setup request bearing the secret token."""
    if environment == "development":
        return True
    return bool(
        enabled
        and configured_token
        and received_token
        and hmac.compare_digest(configured_token, received_token)
    )


@router.post("/bootstrap-owner", response_model=CurrentUserResponse, status_code=201)
async def bootstrap_owner(
    payload: OwnerBootstrapRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    setup_token: Annotated[str | None, Header(alias="X-Setup-Token")] = None,
) -> CurrentUserResponse:
    """Create the first owner using local mode or the production setup token."""
    settings = get_settings()
    if not bootstrap_is_allowed(
        environment=settings.environment,
        enabled=settings.owner_bootstrap_enabled,
        configured_token=settings.owner_bootstrap_token,
        received_token=setup_token,
    ):
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        user = await AuthService(session).bootstrap_owner(**payload.model_dump())
        return CurrentUserResponse(
            id=user.id,
            business_id=user.business_id,
            email=user.email,
            role=user.role,
            barber_id=user.barber_id,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DuplicateResourceError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/token", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Exchange owner credentials for a signed bearer token."""
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise HTTPException(status_code=503, detail="JWT_SECRET_KEY is not configured.")
    user = await AuthService(session).authenticate(email=form.username, password=form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        user_id=user.id,
        secret=settings.jwt_secret_key,
        expires_minutes=settings.access_token_expire_minutes,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=CurrentUserResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> CurrentUserResponse:
    """Return the account represented by the bearer token."""
    return CurrentUserResponse(
        id=current_user.id,
        business_id=current_user.business_id,
        email=current_user.email,
        role=current_user.role,
        barber_id=current_user.barber_id,
    )


@router.post(
    "/barber-accounts",
    response_model=BarberAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_barber_account(
    payload: BarberAccountCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BarberAccountResponse:
    """Allow an owner to create a restricted account for one professional."""
    if current_user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required.")
    try:
        user = await AuthService(session).create_barber_account(
            owner=current_user,
            **payload.model_dump(),
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if user.barber_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return BarberAccountResponse(
        id=user.id,
        business_id=user.business_id,
        barber_id=user.barber_id,
        email=user.email,
        is_active=user.is_active,
    )


def require_barber_account(user: User) -> UUID:
    """Return the linked professional or reject non-professional accounts."""
    if user.role != "barber" or user.barber_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Barber access required.")
    return user.barber_id


@router.get("/barber/profile", response_model=BarberProfileResponse)
async def barber_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BarberProfileResponse:
    """Return the identity shown in the restricted professional dashboard."""
    barber_id = require_barber_account(current_user)
    barber = await BarberRepository(session).get_by_id(barber_id)
    business = await BusinessRepository(session).get_by_id(current_user.business_id)
    if barber is None or business is None or barber.business_id != business.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return BarberProfileResponse(
        business_id=business.id,
        business_name=business.name,
        timezone=business.timezone,
        barber_id=barber.id,
        full_name=barber.full_name,
        phone=barber.phone,
        commission_percentage=barber.commission_percentage,
    )


async def barber_appointment_response(
    appointment: Appointment, session: AsyncSession
) -> BarberAppointmentResponse:
    customer = await session.get(Customer, appointment.customer_id)
    service = await session.get(Service, appointment.service_id) if appointment.service_id else None
    return BarberAppointmentResponse(
        id=appointment.id,
        public_token=appointment.public_token,
        customer_id=appointment.customer_id,
        service_id=appointment.service_id,
        customer_name=customer.full_name if customer else "Cliente",
        customer_phone=customer.phone if customer else "",
        service_name=service.name if service else "Atendimento",
        starts_at=appointment.starts_at,
        ends_at=appointment.ends_at,
        status=appointment.status,
        price_cents=appointment.price_cents,
        payment_method=appointment.payment_method,
        notes=appointment.notes,
    )


@router.get("/barber/appointments", response_model=list[BarberAppointmentResponse])
async def barber_appointments(
    appointment_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[BarberAppointmentResponse]:
    """List only the appointments assigned to the authenticated professional."""
    barber_id = require_barber_account(current_user)
    appointments = await AppointmentService(session).list_for_barber(
        business_id=current_user.business_id,
        barber_id=barber_id,
        appointment_date=appointment_date,
    )
    return [await barber_appointment_response(item, session) for item in appointments]


async def require_assigned_appointment(
    *, current_user: User, appointment_id: UUID, session: AsyncSession
) -> Appointment:
    barber_id = require_barber_account(current_user)
    appointment = await AppointmentRepository(session).get_by_id(appointment_id)
    if (
        appointment is None
        or appointment.business_id != current_user.business_id
        or appointment.barber_id != barber_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    return appointment


@router.patch(
    "/barber/appointments/{appointment_id}/confirm",
    response_model=BarberAppointmentResponse,
)
async def barber_confirm_appointment(
    appointment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BarberAppointmentResponse:
    await require_assigned_appointment(
        current_user=current_user, appointment_id=appointment_id, session=session
    )
    appointment = await AppointmentService(session).confirm(
        current_user.business_id, appointment_id
    )
    return await barber_appointment_response(appointment, session)


@router.patch(
    "/barber/appointments/{appointment_id}/complete",
    response_model=BarberAppointmentResponse,
)
async def barber_complete_appointment(
    appointment_id: UUID,
    payload: AppointmentCompleteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BarberAppointmentResponse:
    await require_assigned_appointment(
        current_user=current_user, appointment_id=appointment_id, session=session
    )
    appointment = await AppointmentService(session).complete(
        current_user.business_id, appointment_id, payload.payment_method
    )
    return await barber_appointment_response(appointment, session)


@router.patch(
    "/barber/appointments/{appointment_id}/no-show",
    response_model=BarberAppointmentResponse,
)
async def barber_no_show_appointment(
    appointment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BarberAppointmentResponse:
    await require_assigned_appointment(
        current_user=current_user, appointment_id=appointment_id, session=session
    )
    appointment = await AppointmentService(session).mark_no_show(
        current_user.business_id, appointment_id
    )
    return await barber_appointment_response(appointment, session)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Change the authenticated owner's password."""
    changed = await AuthService(session).change_password(
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    if not changed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect or the new password is unchanged.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/email/request",
    response_model=EmailChangeRequestedResponse,
    responses={
        400: {"description": "Incorrect current password."},
        409: {"description": "Email already in use."},
        503: {"description": "Email delivery unavailable."},
    },
)
async def request_email_change(
    payload: EmailChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EmailChangeRequestedResponse:
    """Send a verification code to a requested replacement email."""
    try:
        code = await AuthService(session).request_email_change(
            user=current_user,
            current_password=payload.current_password,
            new_email=str(payload.new_email),
        )
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    settings = get_settings()
    development_code: str | None = None
    if settings.email_delivery_enabled and settings.resend_api_key:
        try:
            await send_email_change_code(
                api_key=settings.resend_api_key,
                from_email=settings.resend_from_email,
                to_email=str(payload.new_email),
                code=code,
            )
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The verification email could not be sent.",
            ) from error
    elif settings.environment == "development" or not settings.email_delivery_enabled:
        development_code = code
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured.",
        )
    return EmailChangeRequestedResponse(
        detail="Verification code sent.",
        expires_in_seconds=600,
        development_code=development_code,
    )


@router.post(
    "/email/confirm",
    response_model=CurrentUserResponse,
    responses={
        400: {"description": "Invalid or expired code."},
        409: {"description": "Email already in use."},
    },
)
async def confirm_email_change(
    payload: EmailChangeConfirmRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrentUserResponse:
    """Confirm the code and apply the pending login email."""
    try:
        user = await AuthService(session).confirm_email_change(user=current_user, code=payload.code)
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code is invalid or expired.",
        )
    return CurrentUserResponse(
        id=user.id,
        business_id=user.business_id,
        email=user.email,
        role=user.role,
        barber_id=user.barber_id,
    )
