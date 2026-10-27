"""Reconcile report cards, breakdowns and chart values using integer cents."""

import asyncio
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import AppointmentStatus, PaymentMethod
from app.models.expense import Expense
from app.services.report import ReportService


def test_report_reconciles_commission_cents_with_daily_results() -> None:
    business_id, barber_id, service_id = (uuid4() for _ in range(3))
    report = ReportService(AsyncMock(spec=AsyncSession))
    report._businesses = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(timezone="America/Sao_Paulo"))
    )
    report._barbers = SimpleNamespace(
        list_by_business=AsyncMock(
            return_value=[
                SimpleNamespace(id=barber_id, full_name="Test barber", commission_percentage=50),
            ]
        )
    )
    report._services = SimpleNamespace(
        list_by_business=AsyncMock(
            return_value=[
                SimpleNamespace(id=service_id, name="Test service"),
            ]
        )
    )
    appointments = []
    for status, starts, payment in [
        (AppointmentStatus.COMPLETED, datetime(2030, 1, 16, 1, tzinfo=UTC), PaymentMethod.PIX),
        (AppointmentStatus.COMPLETED, datetime(2030, 1, 16, 14, tzinfo=UTC), PaymentMethod.CASH),
        (AppointmentStatus.CANCELLED, datetime(2030, 1, 16, 15, tzinfo=UTC), None),
        (AppointmentStatus.NO_SHOW, datetime(2030, 1, 16, 16, tzinfo=UTC), None),
        (AppointmentStatus.SCHEDULED, datetime(2030, 1, 16, 17, tzinfo=UTC), None),
        (AppointmentStatus.CONFIRMED, datetime(2030, 1, 16, 18, tzinfo=UTC), None),
    ]:
        appointments.append(
            SimpleNamespace(
                status=status,
                starts_at=starts,
                payment_method=payment,
                barber_id=barber_id,
                service_id=service_id,
                price_cents=1001,
            )
        )
    report._appointments = SimpleNamespace(
        list_by_business_range=AsyncMock(return_value=appointments)
    )
    expenses = [
        Expense(
            id=uuid4(),
            business_id=business_id,
            category="other",
            description="Test expense",
            amount_cents=amount,
            occurred_on=day,
            is_fixed=False,
            is_paid=paid,
            paid_at=datetime(2030, 1, 16, tzinfo=UTC) if paid else None,
            created_at=datetime(2030, 1, 15, tzinfo=UTC),
        )
        for amount, day, paid in [(75, date(2030, 1, 15), False), (25, date(2030, 1, 16), True)]
    ]
    report._expenses = SimpleNamespace(list_by_range=AsyncMock(return_value=expenses))

    result = asyncio.run(report.financial(business_id, date(2030, 1, 15), date(2030, 1, 16)))

    assert result.total_revenue_cents == 2002
    assert result.total_commission_cents == 1000
    assert result.by_barber[0].commission_cents == 1000
    assert result.net_revenue_cents == 1002
    assert result.total_expenses_cents == 100
    assert result.final_result_cents == 902
    assert sum(item.result_cents for item in result.daily) == result.final_result_cents
    assert sum(item.revenue_cents for item in result.daily) == result.total_revenue_cents
    assert sum(item.expense_cents for item in result.daily) == result.total_expenses_cents
    assert [item.result_cents for item in result.daily] == [426, 476]
    assert result.completed == 2 and result.scheduled == result.confirmed == 1
    assert result.cancelled == result.no_show == 1
    assert result.average_ticket_cents == 1001 and result.attendance_rate_percent == 67
    assert sorted(item.label for item in result.by_payment_method) == ["Dinheiro", "Pix"]
    assert sum(item.total_cents for item in result.by_payment_method) == result.total_revenue_cents
    assert sum(item.total_cents for item in result.by_service) == result.total_revenue_cents
    bounds = report._appointments.list_by_business_range.await_args.kwargs
    assert bounds["starts_at"].hour == 0 and bounds["ends_at"].day == 17


def test_empty_report_has_zero_totals_and_all_requested_days() -> None:
    report = ReportService(AsyncMock(spec=AsyncSession))
    report._businesses = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(timezone="America/Sao_Paulo"))
    )
    report._barbers = SimpleNamespace(list_by_business=AsyncMock(return_value=[]))
    report._services = SimpleNamespace(list_by_business=AsyncMock(return_value=[]))
    report._appointments = SimpleNamespace(list_by_business_range=AsyncMock(return_value=[]))
    report._expenses = SimpleNamespace(list_by_range=AsyncMock(return_value=[]))
    result = asyncio.run(report.financial(uuid4(), date(2030, 1, 1), date(2030, 1, 3)))
    assert (
        result.total_revenue_cents
        == result.total_commission_cents
        == result.final_result_cents
        == 0
    )
    assert result.average_ticket_cents == result.attendance_rate_percent == 0
    assert result.by_barber == result.by_payment_method == result.by_service == []
    assert len(result.daily) == 3 and all(item.result_cents == 0 for item in result.daily)
