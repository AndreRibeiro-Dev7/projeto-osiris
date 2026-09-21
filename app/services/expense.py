"""Expense management use cases."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.expense import Expense
from app.repositories.business import BusinessRepository
from app.repositories.expense import ExpenseRepository
from app.schemas.expense import ExpenseCreate, ExpenseUpdate


class ExpenseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._businesses = BusinessRepository(session)
        self._expenses = ExpenseRepository(session)

    async def create(self, business_id: UUID, payload: ExpenseCreate) -> Expense:
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        expense = await self._expenses.create(business_id, **payload.model_dump())
        await self._session.commit()
        await self._session.refresh(expense)
        return expense

    async def list(self, business_id: UUID, date_from: date, date_to: date) -> list[Expense]:
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        return await self._expenses.list_by_range(business_id, date_from, date_to)

    async def delete(self, business_id: UUID, expense_id: UUID) -> None:
        expense = await self._expenses.get_by_id(expense_id)
        if expense is None or expense.business_id != business_id:
            raise ResourceNotFoundError("Expense not found.")
        await self._expenses.delete(expense)
        await self._session.commit()

    async def update(
        self, business_id: UUID, expense_id: UUID, payload: ExpenseUpdate
    ) -> Expense:
        expense = await self._expenses.get_by_id(expense_id)
        if expense is None or expense.business_id != business_id:
            raise ResourceNotFoundError("Expense not found.")
        for field, value in payload.model_dump().items():
            setattr(expense, field, value)
        await self._session.commit()
        await self._session.refresh(expense)
        return expense

    async def mark_paid(self, business_id: UUID, expense_id: UUID) -> Expense:
        expense = await self._expenses.get_by_id(expense_id)
        if expense is None or expense.business_id != business_id:
            raise ResourceNotFoundError("Expense not found.")
        expense.is_paid = True
        expense.paid_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(expense)
        return expense

    async def mark_pending(self, business_id: UUID, expense_id: UUID) -> Expense:
        expense = await self._expenses.get_by_id(expense_id)
        if expense is None or expense.business_id != business_id:
            raise ResourceNotFoundError("Expense not found.")
        expense.is_paid = False
        expense.paid_at = None
        await self._session.commit()
        await self._session.refresh(expense)
        return expense

    async def generate_fixed_for_month(
        self, business_id: UUID, target_month: date
    ) -> list[Expense]:
        if await self._businesses.get_by_id(business_id) is None:
            raise ResourceNotFoundError("Business not found.")
        target_start = target_month.replace(day=1)
        target_end = target_start.replace(
            day=monthrange(target_start.year, target_start.month)[1]
        )
        previous_end = target_start - timedelta(days=1)
        previous_start = previous_end.replace(day=1)
        sources = [
            item
            for item in await self._expenses.list_by_range(
                business_id, previous_start, previous_end
            )
            if item.is_fixed
        ]
        existing = await self._expenses.list_by_range(
            business_id, target_start, target_end
        )
        existing_keys = {
            (item.category, item.description.casefold(), item.amount_cents)
            for item in existing
            if item.is_fixed
        }
        created: list[Expense] = []
        for source in sources:
            key = (source.category, source.description.casefold(), source.amount_cents)
            if key in existing_keys:
                continue
            occurred_on = target_start.replace(
                day=min(source.occurred_on.day, target_end.day)
            )
            created.append(
                await self._expenses.create(
                    business_id,
                    category=source.category,
                    description=source.description,
                    amount_cents=source.amount_cents,
                    occurred_on=occurred_on,
                    is_fixed=True,
                    is_paid=False,
                )
            )
            existing_keys.add(key)
        await self._session.commit()
        for expense in created:
            await self._session.refresh(expense)
        return created
