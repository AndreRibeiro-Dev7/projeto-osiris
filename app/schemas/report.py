"""Financial reporting API contracts."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.schemas.expense import ExpenseResponse


class RevenueBreakdown(BaseModel):
    id: UUID | None = None
    label: str
    total_cents: int
    appointments: int
    commission_percentage: int | None = None
    commission_cents: int | None = None


class DailyFinancialPoint(BaseModel):
    date: date
    appointments: int
    revenue_cents: int
    expense_cents: int
    result_cents: int


class FinancialReportResponse(BaseModel):
    date_from: date
    date_to: date
    total_revenue_cents: int
    total_commission_cents: int
    net_revenue_cents: int
    total_expenses_cents: int
    final_result_cents: int
    average_ticket_cents: int
    attendance_rate_percent: int
    completed: int
    scheduled: int
    confirmed: int
    cancelled: int
    no_show: int
    by_barber: list[RevenueBreakdown]
    by_service: list[RevenueBreakdown]
    by_payment_method: list[RevenueBreakdown]
    expenses: list[ExpenseResponse]
    daily: list[DailyFinancialPoint]
