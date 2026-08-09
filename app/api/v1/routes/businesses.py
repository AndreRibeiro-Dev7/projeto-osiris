"""Endpoints for business, barber and customer registration."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateResourceError, ResourceNotFoundError
from app.database.session import get_db_session
from app.schemas.barber import BarberCreate, BarberResponse
from app.schemas.business import BusinessCreate, BusinessResponse
from app.schemas.customer import CustomerCreate, CustomerResponse
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
