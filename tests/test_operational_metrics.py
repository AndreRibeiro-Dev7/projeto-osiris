import json
import logging
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from app.core.logging import SanitizingJsonFormatter
from app.main import app
from app.services.operational_metrics import (
    classify_critical_operation,
    record_critical_operation_metric,
)


@pytest.mark.parametrize(
    ("method", "route", "category", "operation"),
    [
        (
            "POST",
            "/api/v1/businesses/{business_id}/appointments",
            "scheduling",
            "appointment_created",
        ),
        (
            "POST",
            "/api/v1/public/businesses/{business_id}/appointments",
            "scheduling",
            "public_appointment_created",
        ),
        (
            "PATCH",
            "/api/v1/businesses/{business_id}/appointments/{appointment_id}/complete",
            "financial",
            "appointment_payment_recorded",
        ),
        (
            "PATCH",
            "/api/v1/businesses/{business_id}/expenses/{expense_id}/paid",
            "financial",
            "expense_marked_paid",
        ),
        (
            "GET",
            "/api/v1/businesses/{business_id}/reports/financial.xlsx",
            "financial",
            "financial_report_exported",
        ),
    ],
)
def test_classifies_critical_business_operations(
    method: str,
    route: str,
    category: str,
    operation: str,
) -> None:
    result = classify_critical_operation(method=method, route=route)

    assert result is not None
    assert result.category == category
    assert result.operation == operation


def test_ignores_non_critical_or_wrong_method_routes() -> None:
    assert classify_critical_operation(method="GET", route="/api/v1/health") is None
    assert (
        classify_critical_operation(method="GET", route="/api/v1/businesses/{business_id}/expenses")
        is None
    )


@pytest.mark.parametrize(
    ("status_code", "expected_outcome"),
    [(201, "success"), (409, "rejected"), (503, "error")],
)
def test_records_countable_outcomes(status_code: int, expected_outcome: str) -> None:
    metric = record_critical_operation_metric(
        method="POST",
        route="/api/v1/businesses/{business_id}/appointments",
        status_code=status_code,
        duration_ms=12.5,
        request_id="request-123",
    )

    assert metric is not None
    assert metric.outcome == expected_outcome
    assert metric.status_code == status_code
    assert metric.duration_ms == 12.5


def test_metric_json_contains_only_stable_privacy_safe_labels() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SanitizingJsonFormatter())
    metric_logger = logging.getLogger("app.metrics")
    original_handlers = metric_logger.handlers
    original_propagate = metric_logger.propagate
    original_level = metric_logger.level
    metric_logger.handlers = [handler]
    metric_logger.propagate = False
    metric_logger.setLevel(logging.INFO)

    try:
        record_critical_operation_metric(
            method="PATCH",
            route="/api/v1/businesses/{business_id}/expenses/{expense_id}/paid",
            status_code=200,
            duration_ms=8.75,
            request_id="request-safe",
        )
    finally:
        metric_logger.handlers = original_handlers
        metric_logger.propagate = original_propagate
        metric_logger.setLevel(original_level)

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "business.metric"
    assert payload["metric_name"] == "osiris_critical_operation_total"
    assert payload["metric_category"] == "financial"
    assert payload["metric_operation"] == "expense_marked_paid"
    assert payload["metric_outcome"] == "success"
    assert payload["metric_value"] == 1
    assert payload["request_id"] == "request-safe"
    assert "business_id" not in payload
    assert "expense_id" not in payload
    assert "amount" not in payload


def test_http_middleware_records_rejected_critical_operation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.metrics")
    client = TestClient(app)

    response = client.post(
        "/api/v1/public/businesses/00000000-0000-0000-0000-000000000001/appointments",
        json={},
    )

    assert response.status_code == 422
    record = next(
        item for item in caplog.records if getattr(item, "event", None) == "business.metric"
    )
    assert record.metric_category == "scheduling"
    assert record.metric_operation == "public_appointment_created"
    assert record.metric_outcome == "rejected"
    assert record.route == "/api/v1/public/businesses/{business_id}/appointments"
    assert record.metric_value == 1
