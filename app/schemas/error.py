"""Common error contracts exposed by the HTTP API."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error body returned by FastAPI endpoints."""

    detail: str
