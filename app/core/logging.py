"""Centralized, privacy-safe application logging."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

REDACTED = "[REDACTED]"

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_URL_CREDENTIAL_PATTERN = re.compile(r"(?P<scheme>\b[a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@", re.I)
_KEYED_SECRET_PATTERN = re.compile(
    r"(?i)\b(authorization|password|passwd|current_password|new_password|token|secret|"
    r"api[_-]?key|access[_-]?token|refresh[_-]?token|verification[_-]?code|code|email)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


def redact_text(value: object) -> str:
    """Remove common credentials and personal identifiers from log text."""
    text = str(value)
    text = _URL_CREDENTIAL_PATTERN.sub(r"\g<scheme>[REDACTED]@", text)
    text = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", text)
    text = _JWT_PATTERN.sub(REDACTED, text)
    text = _KEYED_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", text
    )
    return _EMAIL_PATTERN.sub(REDACTED, text)


class SanitizingJsonFormatter(logging.Formatter):
    """Render one redacted JSON object per line for centralized collectors."""

    extra_fields = (
        "event",
        "request_id",
        "method",
        "route",
        "status_code",
        "duration_ms",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        for field in self.extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = redact_text(value) if isinstance(value, str) else value
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class SanitizingTextFormatter(logging.Formatter):
    """Provide readable development logs while applying the same redaction."""

    def format(self, record: logging.LogRecord) -> str:
        clone = logging.makeLogRecord(record.__dict__.copy())
        clone.msg = redact_text(record.getMessage())
        clone.args = ()
        return redact_text(super().format(clone))


def configure_logging(*, level: str, json_logs: bool) -> None:
    """Configure a single stdout handler for application and server logs."""
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(SanitizingJsonFormatter())
    else:
        handler.setFormatter(
            SanitizingTextFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    logging.captureWarnings(True)

    for logger_name in ("uvicorn", "uvicorn.error", "fastapi"):
        configured_logger = logging.getLogger(logger_name)
        configured_logger.handlers.clear()
        configured_logger.propagate = True

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    for logger_name in ("httpx", "httpx2", "httpcore", "httpcore2"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
