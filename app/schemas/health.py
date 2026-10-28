"""Schemas returned by health endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Public status information for the API."""

    status: str
    application: str
    version: str
    revision: str | None = None


class DatabaseHealthResponse(BaseModel):
    """Public status information for the database connection."""

    status: str
