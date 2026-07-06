"""Upserts a user record from a Google OIDC identity.

Framework-free like `claim_service` — called from the `/users/sync` route,
which the frontend's NextAuth `signIn` callback hits once per sign-in.
"""

from __future__ import annotations

from typing import Optional

from app.db.models.user import UserRecord
from app.db.user_repository import UserRepository


async def upsert_from_google(
    repo: UserRepository,
    *,
    google_sub: str,
    email: str,
    name: Optional[str],
    avatar_url: Optional[str],
) -> UserRecord:
    """First sign-in creates the user; later sign-ins refresh only the
    provider-derived tier (email/name/avatar_url — see the field-tier
    docstring on `UserRecord`). The user-customizable tier
    (display_name, contact_email, custom_avatar_url) is deliberately
    never written here: a Google re-sign-in must not overwrite what the
    user chose in ClaimSight."""
    record = await repo.get_by_google_sub(google_sub)
    if record is None:
        return await repo.create(
            google_sub=google_sub, email=email, name=name, avatar_url=avatar_url
        )

    record.email = email
    record.name = name
    record.avatar_url = avatar_url
    return await repo.save(record)
