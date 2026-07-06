"""Persisted user record, sourced from Google OIDC sign-in.

Deliberately minimal: only the identity fields the frontend's NextAuth
Google provider already receives at sign-in (`sub`, `email`, `name`,
`picture`). No OAuth access/refresh tokens are stored here — this app
never calls the Google API on the user's behalf after sign-in, so there
is nothing for those tokens to authorize.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Google's stable per-account identifier ("sub" claim) — the durable key
    # for upsert-on-sign-in, unlike email which a user could in theory change.
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
