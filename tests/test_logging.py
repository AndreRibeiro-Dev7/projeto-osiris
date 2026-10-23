import json
import logging
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from app.core.logging import REDACTED, SanitizingJsonFormatter, redact_text
from app.main import app


def test_redact_text_removes_credentials_and_personal_data() -> None:
    message = (
        "email=andre@example.com password=correct-horse "
        "authorization=Bearer secret-token "
        "database=postgresql://osiris:database-password@database.internal/osiris"
    )

    redacted = redact_text(message)

    assert "andre@example.com" not in redacted
    assert "correct-horse" not in redacted
    assert "secret-token" not in redacted
    assert "database-password" not in redacted
    assert redacted.count(REDACTED) >= 4


def test_json_formatter_sanitizes_message_and_exception() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SanitizingJsonFormatter())
    test_logger = logging.getLogger("tests.secure-logging")
    test_logger.handlers = [handler]
    test_logger.propagate = False
    test_logger.setLevel(logging.INFO)

    try:
        raise RuntimeError("token=top-secret for andre@example.com")
    except RuntimeError:
        test_logger.exception("password=never-log-this")

    payload = json.loads(stream.getvalue())
    rendered = json.dumps(payload)
    assert payload["message"] == f"password={REDACTED}"
    assert "never-log-this" not in rendered
    assert "top-secret" not in rendered
    assert "andre@example.com" not in rendered


def test_request_log_uses_route_template_without_query_or_authorization(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.http")
    client = TestClient(app)

    response = client.get(
        "/api/v1/health?token=query-secret",
        headers={"Authorization": "Bearer header-secret"},
    )

    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 32
    request_record = next(
        record for record in caplog.records if getattr(record, "event", None) == "request.completed"
    )
    assert request_record.route == "/api/v1/health"
    assert request_record.status_code == 200
    assert "query-secret" not in request_record.getMessage()
    assert "header-secret" not in request_record.getMessage()
