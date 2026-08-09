"""Shared SQLAlchemy declarative base for persistent entities."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class inherited by every database model."""
