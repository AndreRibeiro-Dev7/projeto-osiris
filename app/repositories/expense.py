"""Database queries for expenses."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense


class ExpenseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, expense_id: UUID) -> Expense | None:
        return await self._session.get(Expense, expense_id)

    async def list_by_range(self, business_id: UUID, date_from: date, date_to: date) -> list[Expense]:
        statement = select(Expense).where(Expense.business_id == business_id, Expense.occurred_on >= date_from, Expense.occurred_on <= date_to).order_by(Expense.occurred_on.desc(), Expense.created_at.desc())
        return list((await self._session.scalars(statement)).all())

    async def create(self, business_id: UUID, **values: object) -> Expense:
        expense = Expense(business_id=business_id, **values)
        self._session.add(expense)
        return expense

    async def delete(self, expense: Expense) -> None:
        await self._session.delete(expense)
