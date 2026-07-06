"""Shared SQLAlchemy declarative base. Every ORM model imports this so
Alembic's autogenerate (`Base.metadata`) sees the full schema from one
place, regardless of which `app/db/models/*` module defines the table."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
