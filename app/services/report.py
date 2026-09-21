"""Financial and operational reporting use cases."""

from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.appointment import AppointmentStatus
from app.repositories.appointment import AppointmentRepository
from app.repositories.barber import BarberRepository
from app.repositories.business import BusinessRepository
from app.repositories.expense import ExpenseRepository
from app.repositories.service import ServiceRepository
from app.schemas.report import DailyFinancialPoint, FinancialReportResponse, RevenueBreakdown


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self._businesses = BusinessRepository(session)
        self._appointments = AppointmentRepository(session)
        self._barbers = BarberRepository(session)
        self._services = ServiceRepository(session)
        self._expenses = ExpenseRepository(session)

    async def financial(
        self, business_id: UUID, date_from: date, date_to: date
    ) -> FinancialReportResponse:
        business = await self._businesses.get_by_id(business_id)
        if business is None:
            raise ResourceNotFoundError("Business not found.")
        timezone = ZoneInfo(business.timezone)
        starts_at = datetime.combine(date_from, time.min, tzinfo=timezone)
        ends_at = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone)
        appointments = await self._appointments.list_by_business_range(
            business_id=business_id, starts_at=starts_at, ends_at=ends_at
        )
        expenses = await self._expenses.list_by_range(business_id, date_from, date_to)
        barber_items = await self._barbers.list_by_business(business_id)
        barbers = {item.id: item.full_name for item in barber_items}
        commissions = {item.id: item.commission_percentage for item in barber_items}
        services = {item.id: item.name for item in await self._services.list_by_business(business_id)}
        statuses = {status.value: 0 for status in AppointmentStatus}
        barber_totals: dict[UUID, list[int]] = {}
        service_totals: dict[UUID | None, list[int]] = {}
        payment_totals: dict[str, list[int]] = {}
        revenue = 0
        # appointments, revenue, commission and expenses for each local day
        daily_values: dict[date, list[int]] = {}
        cursor = date_from
        while cursor <= date_to:
            daily_values[cursor] = [0, 0, 0, 0]
            cursor += timedelta(days=1)
        for appointment in appointments:
            statuses[appointment.status.value] += 1
            if appointment.status != AppointmentStatus.COMPLETED:
                continue
            amount = appointment.price_cents or 0
            revenue += amount
            local_day = appointment.starts_at.astimezone(timezone).date()
            daily = daily_values.setdefault(local_day, [0, 0, 0, 0])
            daily[0] += 1
            daily[1] += amount
            daily[2] += amount * commissions.get(appointment.barber_id, 0) // 100
            barber_total = barber_totals.setdefault(appointment.barber_id, [0, 0])
            barber_total[0] += amount
            barber_total[1] += 1
            service_total = service_totals.setdefault(appointment.service_id, [0, 0])
            service_total[0] += amount
            service_total[1] += 1
            payment = appointment.payment_method.value if appointment.payment_method else "not_informed"
            payment_total = payment_totals.setdefault(payment, [0, 0])
            payment_total[0] += amount
            payment_total[1] += 1
        def rows(values: dict, labels: dict) -> list[RevenueBreakdown]:
            return sorted([RevenueBreakdown(id=key if isinstance(key, UUID) else None, label=labels.get(key, "Não informado"), total_cents=value[0], appointments=value[1]) for key, value in values.items()], key=lambda item: item.total_cents, reverse=True)
        payment_labels = {"pix": "Pix", "cash": "Dinheiro", "credit_card": "Crédito", "debit_card": "Débito", "not_informed": "Não informado"}
        barber_rows = rows(barber_totals, barbers)
        for row in barber_rows:
            percentage = commissions.get(row.id, 0) if row.id else 0
            row.commission_percentage = percentage
            row.commission_cents = row.total_cents * percentage // 100
        total_commission = sum(row.commission_cents or 0 for row in barber_rows)
        for expense in expenses:
            daily_values.setdefault(expense.occurred_on, [0, 0, 0, 0])[3] += expense.amount_cents
        total_expenses = sum(expense.amount_cents for expense in expenses)
        completed = statuses["completed"]
        attendance_base = completed + statuses["no_show"]
        return FinancialReportResponse(
            date_from=date_from, date_to=date_to, total_revenue_cents=revenue,
            total_commission_cents=total_commission,
            net_revenue_cents=revenue - total_commission,
            total_expenses_cents=total_expenses,
            final_result_cents=revenue - total_commission - total_expenses,
            average_ticket_cents=revenue // completed if completed else 0,
            attendance_rate_percent=round(completed / attendance_base * 100) if attendance_base else 0,
            completed=completed, scheduled=statuses["scheduled"],
            confirmed=statuses["confirmed"], cancelled=statuses["cancelled"],
            no_show=statuses["no_show"], by_barber=barber_rows,
            by_service=rows(service_totals, services),
            by_payment_method=rows(payment_totals, payment_labels),
            expenses=expenses,
            daily=[
                DailyFinancialPoint(
                    date=day,
                    appointments=values[0],
                    revenue_cents=values[1],
                    expense_cents=values[3],
                    result_cents=values[1] - values[2] - values[3],
                )
                for day, values in daily_values.items()
            ],
        )
