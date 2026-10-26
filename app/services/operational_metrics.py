"""Privacy-safe metrics for critical scheduling and financial operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

MetricCategory = Literal["scheduling", "financial"]
MetricOutcome = Literal["success", "rejected", "error"]

logger = logging.getLogger("app.metrics")


@dataclass(frozen=True, slots=True)
class CriticalOperation:
    """Stable labels for one business operation without tenant or customer data."""

    category: MetricCategory
    operation: str


@dataclass(frozen=True, slots=True)
class CriticalOperationMetric:
    """One recorded attempt at a critical business operation."""

    category: MetricCategory
    operation: str
    outcome: MetricOutcome
    status_code: int
    duration_ms: float


_CRITICAL_OPERATIONS: dict[tuple[str, str], CriticalOperation] = {
    # Scheduling performed by the owner, customer or assigned barber.
    ("POST", "/api/v1/businesses/{business_id}/appointments"): CriticalOperation(
        "scheduling", "appointment_created"
    ),
    ("POST", "/api/v1/public/businesses/{business_id}/appointments"): CriticalOperation(
        "scheduling", "public_appointment_created"
    ),
    (
        "PATCH",
        "/api/v1/businesses/{business_id}/appointments/{appointment_id}/reschedule",
    ): CriticalOperation("scheduling", "appointment_rescheduled"),
    (
        "PATCH",
        "/api/v1/public/businesses/appointments/{public_token}/reschedule",
    ): CriticalOperation("scheduling", "public_appointment_rescheduled"),
    (
        "PATCH",
        "/api/v1/businesses/{business_id}/appointments/{appointment_id}/confirm",
    ): CriticalOperation("scheduling", "appointment_confirmed"),
    (
        "PATCH",
        "/api/v1/public/businesses/appointments/{public_token}/confirm",
    ): CriticalOperation("scheduling", "public_appointment_confirmed"),
    (
        "PATCH",
        "/api/v1/auth/barber/appointments/{appointment_id}/confirm",
    ): CriticalOperation("scheduling", "barber_appointment_confirmed"),
    (
        "PATCH",
        "/api/v1/businesses/{business_id}/appointments/{appointment_id}/cancel",
    ): CriticalOperation("scheduling", "appointment_cancelled"),
    (
        "PATCH",
        "/api/v1/public/businesses/appointments/{public_token}/cancel",
    ): CriticalOperation("scheduling", "public_appointment_cancelled"),
    (
        "PATCH",
        "/api/v1/businesses/{business_id}/appointments/{appointment_id}/no-show",
    ): CriticalOperation("scheduling", "appointment_no_show"),
    (
        "PATCH",
        "/api/v1/auth/barber/appointments/{appointment_id}/no-show",
    ): CriticalOperation("scheduling", "barber_appointment_no_show"),
    # Completing an appointment records revenue and a payment method.
    (
        "PATCH",
        "/api/v1/businesses/{business_id}/appointments/{appointment_id}/complete",
    ): CriticalOperation("financial", "appointment_payment_recorded"),
    (
        "PATCH",
        "/api/v1/auth/barber/appointments/{appointment_id}/complete",
    ): CriticalOperation("financial", "barber_appointment_payment_recorded"),
    # Expense lifecycle and financial reporting.
    ("POST", "/api/v1/businesses/{business_id}/expenses"): CriticalOperation(
        "financial", "expense_created"
    ),
    (
        "PATCH",
        "/api/v1/businesses/{business_id}/expenses/{expense_id}",
    ): CriticalOperation("financial", "expense_updated"),
    (
        "DELETE",
        "/api/v1/businesses/{business_id}/expenses/{expense_id}",
    ): CriticalOperation("financial", "expense_deleted"),
    (
        "PATCH",
        "/api/v1/businesses/{business_id}/expenses/{expense_id}/paid",
    ): CriticalOperation("financial", "expense_marked_paid"),
    (
        "PATCH",
        "/api/v1/businesses/{business_id}/expenses/{expense_id}/pending",
    ): CriticalOperation("financial", "expense_marked_pending"),
    (
        "POST",
        "/api/v1/businesses/{business_id}/expenses/fixed/generate",
    ): CriticalOperation("financial", "fixed_expenses_generated"),
    ("GET", "/api/v1/businesses/{business_id}/reports/financial"): CriticalOperation(
        "financial", "financial_report_generated"
    ),
    ("GET", "/api/v1/businesses/{business_id}/reports/financial.xlsx"): CriticalOperation(
        "financial", "financial_report_exported"
    ),
}


def classify_critical_operation(*, method: str, route: str) -> CriticalOperation | None:
    """Return stable metric labels for a monitored route and HTTP method."""
    return _CRITICAL_OPERATIONS.get((method.upper(), route))


def record_critical_operation_metric(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
    request_id: str | None = None,
) -> CriticalOperationMetric | None:
    """Log one countable metric event without business, customer or financial values."""
    operation = classify_critical_operation(method=method, route=route)
    if operation is None:
        return None

    if status_code < 400:
        outcome: MetricOutcome = "success"
    elif status_code < 500:
        outcome = "rejected"
    else:
        outcome = "error"

    metric = CriticalOperationMetric(
        category=operation.category,
        operation=operation.operation,
        outcome=outcome,
        status_code=status_code,
        duration_ms=duration_ms,
    )
    logger.log(
        logging.ERROR if outcome == "error" else logging.INFO,
        (
            "business.metric name=osiris_critical_operation_total "
            f"category={metric.category} operation={metric.operation} outcome={metric.outcome}"
        ),
        extra={
            "event": "business.metric",
            "metric_name": "osiris_critical_operation_total",
            "metric_category": metric.category,
            "metric_operation": metric.operation,
            "metric_outcome": metric.outcome,
            "metric_value": 1,
            "request_id": request_id,
            "method": method.upper(),
            "route": route,
            "status_code": status_code,
            "duration_ms": duration_ms,
        },
    )
    return metric
