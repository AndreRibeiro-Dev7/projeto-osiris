"""Endpoints for business, barber and customer registration."""

from datetime import date, datetime, time, timedelta
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.availability_agent import AvailabilityAgent
from app.api.dependencies import require_business_access
from app.core.config import get_settings
from app.core.exceptions import (
    AIProviderError,
    DuplicateResourceError,
    InactiveBarberError,
    InvalidAppointmentStatusTransitionError,
    InvalidSchedulingReferenceError,
    LoyaltyRewardUnavailableError,
    ResourceNotFoundError,
    SchedulingConflictError,
)
from app.database.session import get_db_session
from app.integrations.customer_workbook import build_customer_workbook
from app.integrations.openai_responses import OpenAIResponsesClient
from app.integrations.financial_workbook import build_financial_workbook
from app.schemas.appointment import (
    AppointmentCompleteRequest,
    AppointmentCreate,
    AppointmentNotesUpdate,
    AppointmentRescheduleRequest,
    AppointmentResponse,
)
from app.schemas.assistant import AssistantMessageRequest, AssistantMessageResponse
from app.schemas.availability import (
    AvailabilityResponse,
    BarberScheduleResponse,
    BarberScheduleUpsert,
    BarberTimeOffCreate,
    BarberTimeOffResponse,
)
from app.schemas.barber import BarberCreate, BarberResponse, BarberUpdate
from app.schemas.business import BusinessCreate, BusinessResponse, BusinessUpdate
from app.schemas.customer import (
    CustomerCreate,
    CustomerPortfolioEntry,
    CustomerResponse,
    CustomerUpdate,
)
from app.schemas.closure import BusinessClosureCreate, BusinessClosureResponse
from app.repositories.business_closure import BusinessClosureRepository
from app.repositories.appointment import AppointmentRepository
from app.repositories.business import BusinessRepository
from app.models.appointment import AppointmentStatus
from app.schemas.error import ErrorResponse
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseUpdate
from app.schemas.report import FinancialReportResponse
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.appointment import AppointmentService
from app.services.assistant_booking import AssistantBookingService
from app.services.availability import AvailabilityService
from app.services.barber import BarberService
from app.services.business import BusinessService
from app.services.customer import CustomerService
from app.services.expense import ExpenseService
from app.services.report import ReportService
from app.services.service import ServiceCatalogService

router = APIRouter(prefix="/businesses")

@router.get("/{business_id}/closures", response_model=list[BusinessClosureResponse], dependencies=[Depends(require_business_access)])
async def list_business_closures(business_id: UUID, session: AsyncSession = Depends(get_db_session)) -> list[BusinessClosureResponse]:
    items = await BusinessClosureRepository(session).list(business_id)
    return [BusinessClosureResponse.model_validate(item) for item in items]

@router.post("/{business_id}/closures", response_model=BusinessClosureResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_business_access)])
async def create_business_closure(business_id: UUID, payload: BusinessClosureCreate, session: AsyncSession = Depends(get_db_session)) -> BusinessClosureResponse:
    repository = BusinessClosureRepository(session)
    existing = await repository.get_for_date(business_id, payload.closure_date)
    if existing: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This date is already closed.")
    business = await BusinessRepository(session).get_by_id(business_id)
    if business is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found.")
    timezone = ZoneInfo(business.timezone); starts_at = datetime.combine(payload.closure_date, time.min, tzinfo=timezone); ends_at = starts_at + timedelta(days=1)
    appointments = await AppointmentRepository(session).list_by_business_range(business_id=business_id, starts_at=starts_at, ends_at=ends_at)
    active_count = sum(item.status in {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED} for item in appointments)
    if active_count: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"There are {active_count} active appointments on this date. Reschedule or cancel them first.")
    item = await repository.create(business_id, payload.closure_date, payload.reason); await session.commit(); await session.refresh(item)
    return BusinessClosureResponse.model_validate(item)

@router.delete("/{business_id}/closures/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_business_access)])
async def delete_business_closure(business_id: UUID, item_id: UUID, session: AsyncSession = Depends(get_db_session)) -> None:
    if not await BusinessClosureRepository(session).delete(business_id, item_id): raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Closure not found.")
    await session.commit()


@router.post(
    "/{business_id}/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_business_access)],
)
async def create_expense(
    business_id: UUID,
    payload: ExpenseCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ExpenseResponse:
    """Record one business expense."""
    try:
        expense = await ExpenseService(session).create(business_id, payload)
        return ExpenseResponse.model_validate(expense)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/{business_id}/expenses",
    response_model=list[ExpenseResponse],
    dependencies=[Depends(require_business_access)],
)
async def list_expenses(
    business_id: UUID,
    date_from: date,
    date_to: date,
    session: AsyncSession = Depends(get_db_session),
) -> list[ExpenseResponse]:
    """List expenses recorded within a date range."""
    if date_to < date_from:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The end date must be on or after the start date.")
    try:
        expenses = await ExpenseService(session).list(business_id, date_from, date_to)
        return [ExpenseResponse.model_validate(item) for item in expenses]
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete(
    "/{business_id}/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_business_access)],
)
async def delete_expense(
    business_id: UUID,
    expense_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an expense entered by mistake."""
    try:
        await ExpenseService(session).delete(business_id, expense_id)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch(
    "/{business_id}/expenses/{expense_id}",
    response_model=ExpenseResponse,
    dependencies=[Depends(require_business_access)],
    responses={404: {"model": ErrorResponse}},
)
async def update_expense(
    business_id: UUID,
    expense_id: UUID,
    payload: ExpenseUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ExpenseResponse:
    """Correct an existing expense entry."""
    try:
        expense = await ExpenseService(session).update(business_id, expense_id, payload)
        return ExpenseResponse.model_validate(expense)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch(
    "/{business_id}/expenses/{expense_id}/paid",
    response_model=ExpenseResponse,
    dependencies=[Depends(require_business_access)],
    responses={404: {"model": ErrorResponse}},
)
async def mark_expense_paid(
    business_id: UUID,
    expense_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ExpenseResponse:
    """Confirm that an expense has been paid."""
    try:
        expense = await ExpenseService(session).mark_paid(business_id, expense_id)
        return ExpenseResponse.model_validate(expense)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch(
    "/{business_id}/expenses/{expense_id}/pending",
    response_model=ExpenseResponse,
    dependencies=[Depends(require_business_access)],
    responses={404: {"model": ErrorResponse}},
)
async def mark_expense_pending(
    business_id: UUID,
    expense_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ExpenseResponse:
    """Reopen an expense payment confirmed by mistake."""
    try:
        expense = await ExpenseService(session).mark_pending(business_id, expense_id)
        return ExpenseResponse.model_validate(expense)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{business_id}/expenses/fixed/generate",
    response_model=list[ExpenseResponse],
    dependencies=[Depends(require_business_access)],
    responses={404: {"model": ErrorResponse}},
)
async def generate_fixed_expenses(
    business_id: UUID,
    target_month: date,
    session: AsyncSession = Depends(get_db_session),
) -> list[ExpenseResponse]:
    """Copy fixed expenses from the previous month without duplicates."""
    try:
        expenses = await ExpenseService(session).generate_fixed_for_month(
            business_id, target_month
        )
        return [ExpenseResponse.model_validate(item) for item in expenses]
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/{business_id}/reports/financial",
    response_model=FinancialReportResponse,
    dependencies=[Depends(require_business_access)],
)
async def get_financial_report(
    business_id: UUID,
    date_from: date,
    date_to: date,
    session: AsyncSession = Depends(get_db_session),
) -> FinancialReportResponse:
    """Summarize revenue and appointments for a date range."""
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The end date must be on or after the start date.",
        )
    try:
        return await ReportService(session).financial(business_id, date_from, date_to)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/{business_id}/reports/financial.xlsx",
    dependencies=[Depends(require_business_access)],
    response_class=StreamingResponse,
)
async def export_financial_report(
    business_id: UUID,
    date_from: date,
    date_to: date,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Download a formatted Excel financial report."""
    if date_to < date_from:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The end date must be on or after the start date.")
    try:
        business = await BusinessService(session).get(business_id)
        report = await ReportService(session).financial(business_id, date_from, date_to)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    filename = f"osiris-financeiro-{date_from.isoformat()}-{date_to.isoformat()}.xlsx"
    return StreamingResponse(
        build_financial_workbook(business.name, report),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.get(
    "/{business_id}",
    response_model=BusinessResponse,
    dependencies=[Depends(require_business_access)],
)
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


@router.patch(
    "/{business_id}",
    response_model=BusinessResponse,
    dependencies=[Depends(require_business_access)],
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def update_business(
    business_id: UUID,
    payload: BusinessUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> BusinessResponse:
    """Update the authenticated owner's barbershop profile."""
    try:
        business = await BusinessService(session).update(business_id, payload)
        return BusinessResponse.model_validate(business)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/{business_id}/barbers",
    response_model=BarberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_business_access)],
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


@router.get(
    "/{business_id}/barbers",
    response_model=list[BarberResponse],
    dependencies=[Depends(require_business_access)],
)
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


@router.patch(
    "/{business_id}/barbers/{barber_id}",
    response_model=BarberResponse,
    dependencies=[Depends(require_business_access)],
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def update_barber(
    business_id: UUID,
    barber_id: UUID,
    payload: BarberUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> BarberResponse:
    """Update a professional's contact data, status or commission settings."""
    try:
        barber = await BarberService(session).update(business_id, barber_id, payload)
        return BarberResponse.model_validate(barber)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/{business_id}/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_business_access)],
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


@router.get(
    "/{business_id}/customers",
    response_model=list[CustomerResponse],
    dependencies=[Depends(require_business_access)],
)
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


@router.get(
    "/{business_id}/customers/portfolio",
    response_model=list[CustomerPortfolioEntry],
    dependencies=[Depends(require_business_access)],
)
async def get_customer_portfolio(
    business_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[CustomerPortfolioEntry]:
    """Return customer activity and spending metrics for the owner dashboard."""
    try:
        return await CustomerService(session).portfolio(business_id)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/{business_id}/customers.xlsx",
    dependencies=[Depends(require_business_access)],
    response_class=StreamingResponse,
)
async def export_customer_portfolio(
    business_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Download the complete customer portfolio as a formatted Excel workbook."""
    try:
        business = await BusinessService(session).get(business_id)
        customers = await CustomerService(session).portfolio(business_id)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return StreamingResponse(
        build_customer_workbook(business.name, business.timezone, customers),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="osiris-clientes.xlsx"'},
    )


@router.patch(
    "/{business_id}/customers/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_business_access)],
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def update_customer(
    business_id: UUID,
    customer_id: UUID,
    payload: CustomerUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> CustomerResponse:
    """Update a customer's name and phone number."""
    try:
        customer = await CustomerService(session).update(
            business_id, customer_id, payload
        )
        return CustomerResponse.model_validate(customer)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/{business_id}/customers/{customer_id}/loyalty/redeem",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_business_access)],
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def redeem_customer_loyalty_reward(
    business_id: UUID,
    customer_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Consume one available loyalty reward for a customer."""
    try:
        await CustomerService(session).redeem_loyalty_reward(business_id, customer_id)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except LoyaltyRewardUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get(
    "/{business_id}/customers/{customer_id}/appointments",
    response_model=list[AppointmentResponse],
    dependencies=[Depends(require_business_access)],
)
async def get_customer_appointment_history(
    business_id: UUID,
    customer_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[AppointmentResponse]:
    """Return the complete appointment history for one customer."""
    try:
        appointments = await CustomerService(session).appointment_history(
            business_id, customer_id
        )
        return [AppointmentResponse.model_validate(item) for item in appointments]
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{business_id}/services",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_business_access)],
)
async def create_service(
    business_id: UUID,
    payload: ServiceCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ServiceResponse:
    """Register a bookable service."""
    try:
        service = await ServiceCatalogService(session).create(business_id, payload)
        return ServiceResponse.model_validate(service)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get(
    "/{business_id}/services",
    response_model=list[ServiceResponse],
    dependencies=[Depends(require_business_access)],
)
async def list_services(
    business_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[ServiceResponse]:
    """List services offered by a barbershop."""
    try:
        services = await ServiceCatalogService(session).list(business_id)
        return [ServiceResponse.model_validate(service) for service in services]
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch(
    "/{business_id}/services/{service_id}",
    response_model=ServiceResponse,
    dependencies=[Depends(require_business_access)],
)
async def update_service(
    business_id: UUID,
    service_id: UUID,
    payload: ServiceUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ServiceResponse:
    """Update service details or active status."""
    try:
        service = await ServiceCatalogService(session).update(business_id, service_id, payload)
        return ServiceResponse.model_validate(service)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except DuplicateResourceError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/{business_id}/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_business_access)],
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


@router.patch(
    "/{business_id}/appointments/{appointment_id}/notes",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_business_access)],
)
async def update_appointment_notes(
    business_id: UUID,
    appointment_id: UUID,
    payload: AppointmentNotesUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> AppointmentResponse:
    """Update the internal observations attached to an appointment."""
    try:
        appointment = await AppointmentService(session).update_notes(
            business_id, appointment_id, payload.notes
        )
        return AppointmentResponse.model_validate(appointment)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error


@router.patch(
    "/{business_id}/appointments/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_business_access)],
)
async def reschedule_appointment(
    business_id: UUID,
    appointment_id: UUID,
    payload: AppointmentRescheduleRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AppointmentResponse:
    """Move an active appointment to another available time."""
    try:
        appointment = await AppointmentService(session).reschedule(
            business_id, appointment_id, payload
        )
        return AppointmentResponse.model_validate(appointment)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (
        InactiveBarberError,
        InvalidAppointmentStatusTransitionError,
        InvalidSchedulingReferenceError,
        SchedulingConflictError,
    ) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get(
    "/{business_id}/barbers/{barber_id}/appointments",
    response_model=list[AppointmentResponse],
    dependencies=[Depends(require_business_access)],
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


@router.get(
    "/{business_id}/barbers/{barber_id}/schedule",
    response_model=list[BarberScheduleResponse],
    dependencies=[Depends(require_business_access)],
)
async def list_barber_schedules(
    business_id: UUID,
    barber_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[BarberScheduleResponse]:
    """List the weekly working schedule configured for one barber."""
    try:
        schedules = await AvailabilityService(session).list_schedules(
            business_id=business_id, barber_id=barber_id
        )
        return [BarberScheduleResponse.model_validate(schedule) for schedule in schedules]
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.put(
    "/{business_id}/barbers/{barber_id}/schedule/{weekday}",
    response_model=BarberScheduleResponse,
    dependencies=[Depends(require_business_access)],
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


@router.delete(
    "/{business_id}/barbers/{barber_id}/schedule/{weekday}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_business_access)],
)
async def delete_barber_schedule(
    business_id: UUID,
    barber_id: UUID,
    weekday: Annotated[int, Path(ge=0, le=6, description="Monday=0, Sunday=6")],
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove one weekday from a barber's recurring schedule."""
    try:
        await AvailabilityService(session).delete_schedule(
            business_id=business_id, barber_id=barber_id, weekday=weekday
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error


@router.get(
    "/{business_id}/barbers/{barber_id}/time-off",
    response_model=list[BarberTimeOffResponse],
    dependencies=[Depends(require_business_access)],
)
async def list_barber_time_off(business_id: UUID, barber_id: UUID, session: AsyncSession = Depends(get_db_session)) -> list[BarberTimeOffResponse]:
    try:
        items = await AvailabilityService(session).list_time_off(business_id=business_id, barber_id=barber_id)
        return [BarberTimeOffResponse.model_validate(item) for item in items]
    except (ResourceNotFoundError, InvalidSchedulingReferenceError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{business_id}/barbers/{barber_id}/time-off",
    response_model=BarberTimeOffResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_business_access)],
)
async def create_barber_time_off(business_id: UUID, barber_id: UUID, payload: BarberTimeOffCreate, session: AsyncSession = Depends(get_db_session)) -> BarberTimeOffResponse:
    try:
        item = await AvailabilityService(session).create_time_off(business_id=business_id, barber_id=barber_id, payload=payload)
        return BarberTimeOffResponse.model_validate(item)
    except (ResourceNotFoundError, InvalidSchedulingReferenceError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete(
    "/{business_id}/barbers/{barber_id}/time-off/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_business_access)],
)
async def delete_barber_time_off(business_id: UUID, barber_id: UUID, item_id: UUID, session: AsyncSession = Depends(get_db_session)) -> None:
    try:
        await AvailabilityService(session).delete_time_off(business_id=business_id, barber_id=barber_id, item_id=item_id)
    except (ResourceNotFoundError, InvalidSchedulingReferenceError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get(
    "/{business_id}/barbers/{barber_id}/availability",
    response_model=AvailabilityResponse,
    dependencies=[Depends(require_business_access)],
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


@router.post(
    "/{business_id}/assistant/messages",
    response_model=AssistantMessageResponse,
    dependencies=[Depends(require_business_access)],
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
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": "The AI provider could not generate a response.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "The OpenAI API key is not configured.",
        },
    },
)
async def send_assistant_message(
    business_id: UUID,
    payload: AssistantMessageRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AssistantMessageResponse:
    """Reply to a customer using the barber's current availability."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured.",
        )

    agent = AvailabilityAgent(
        AvailabilityService(session),
        AssistantBookingService(session),
        OpenAIResponsesClient(api_key=settings.openai_api_key, model=settings.openai_model),
        settings.openai_model,
    )
    try:
        return await agent.reply(
            business_id=business_id,
            barber_id=payload.barber_id,
            appointment_date=payload.appointment_date,
            message=payload.message,
            customer_id=payload.customer_id,
            conversation_id=payload.conversation_id,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InactiveBarberError, SchedulingConflictError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except InvalidSchedulingReferenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    except AIProviderError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.patch(
    "/{business_id}/appointments/{appointment_id}/confirm",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_business_access)],
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
    dependencies=[Depends(require_business_access)],
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


@router.patch(
    "/{business_id}/appointments/{appointment_id}/complete",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_business_access)],
)
async def complete_appointment(
    business_id: UUID,
    appointment_id: UUID,
    payload: AppointmentCompleteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AppointmentResponse:
    """Complete an appointment and record payment."""
    try:
        appointment = await AppointmentService(session).complete(
            business_id, appointment_id, payload.payment_method
        )
        return AppointmentResponse.model_validate(appointment)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InvalidSchedulingReferenceError, InvalidAppointmentStatusTransitionError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.patch(
    "/{business_id}/appointments/{appointment_id}/no-show",
    response_model=AppointmentResponse,
    dependencies=[Depends(require_business_access)],
)
async def mark_appointment_no_show(
    business_id: UUID,
    appointment_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AppointmentResponse:
    """Mark that the customer did not attend."""
    try:
        appointment = await AppointmentService(session).mark_no_show(business_id, appointment_id)
        return AppointmentResponse.model_validate(appointment)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InvalidSchedulingReferenceError, InvalidAppointmentStatusTransitionError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
