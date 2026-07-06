"""Persisted user record, sourced from Google OIDC sign-in.

Two clearly-separated field tiers:

- Provider-derived identity (google_sub, email, name, avatar_url):
  written only from a *verified* Google ID token at sign-in
  (`user_service.upsert_from_google`) and refreshed on every sign-in.
  `email` is the authenticated Google identity email — read-only inside
  ClaimSight, never editable through any profile route.
- User-customizable profile (display_name, contact_email,
  custom_avatar_url): written only through the authenticated
  `/users/me` routes and NEVER touched by sign-in sync, so a Google
  re-sign-in can't clobber what the user chose. Each is nullable; when
  unset the provider-derived value is the effective one.

No OAuth access/refresh tokens are stored here — this app never calls
the Google API on the user's behalf after sign-in, so there is nothing
for those tokens to authorize.
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

    # User-customizable profile tier — see module docstring.
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Always a path under this application's own /avatars/ route
    # (app/api/routes/avatars.py), never an arbitrary user-supplied URL.
    custom_avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
