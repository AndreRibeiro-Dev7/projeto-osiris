"""UTC clock shared by time-sensitive booking rules."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current instant independently of the host or business timezone."""
    return datetime.now(UTC)
