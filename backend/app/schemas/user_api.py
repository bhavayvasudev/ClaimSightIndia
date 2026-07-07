"""Request/response schemas for `app/api/routes/users.py`."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.user import UserRecord

# Server-side contact-email shape check (no email-validator dependency in
# this project). Deliberately conservative: one @, no whitespace/angle
# brackets, a dot in the domain. This stores a *preferred contact*, it
# does not verify deliverability — the UI must never claim "verified".
_CONTACT_EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")

# Display names are plain text: reject anything that could read as
# markup when echoed into HTML by some future consumer.
_FORBIDDEN_NAME_CHARS = re.compile(r"[<>]")


class UserSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The raw Google OIDC ID token from the sign-in that just completed
    # (NextAuth's `account.id_token`) — never the claimed profile fields
    # themselves. The backend independently verifies this token's
    # signature/issuer/audience/expiry (app/core/google_oidc.py) and only
    # trusts `sub`/`email`/`name`/`picture` extracted from it, never
    # whatever a client might additionally assert in the request body.
    id_token: str = Field(description="Google OIDC ID token from the just-completed sign-in")


class UserResponse(BaseModel):
    id: int
    # Verified Google identity email — read-only inside ClaimSight.
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    # User-customizable tier; None means "use the provider-derived value".
    display_name: Optional[str] = None
    contact_email: Optional[str] = None
    custom_avatar_url: Optional[str] = None
    # Legal consent tier; None means never recorded (see POST /users/consent).
    terms_accepted_at: Optional[datetime] = None
    privacy_accepted_at: Optional[datetime] = None
    legal_version_accepted: Optional[str] = None

    @classmethod
    def from_record(cls, record: UserRecord) -> "UserResponse":
        return cls(
            id=record.id,
            email=record.email,
            name=record.name,
            avatar_url=record.avatar_url,
            display_name=record.display_name,
            contact_email=record.contact_email,
            custom_avatar_url=record.custom_avatar_url,
            terms_accepted_at=record.terms_accepted_at,
            privacy_accepted_at=record.privacy_accepted_at,
            legal_version_accepted=record.legal_version_accepted,
        )


class ClaimStats(BaseModel):
    """Compact per-user claim rollup for the profile page — a summary,
    not a second dashboard."""

    total: int
    active: int
    under_review: int
    completed: int
    failed: int


class UserProfileResponse(UserResponse):
    auth_provider: str = "google"
    created_at: Optional[datetime] = None
    claim_stats: Optional[ClaimStats] = None

    @classmethod
    def from_record_with_stats(
        cls, record: UserRecord, claim_stats: Optional[ClaimStats] = None
    ) -> "UserProfileResponse":
        base = UserResponse.from_record(record)
        return cls(**base.model_dump(), created_at=record.created_at, claim_stats=claim_stats)


class UserProfileUpdateRequest(BaseModel):
    """PATCH /users/me body. Omitted fields stay untouched; an explicit
    null clears the customization back to the provider-derived value.
    The Google identity email and google_sub are deliberately not
    accepted here at all (`extra="forbid"`)."""

    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = Field(default=None, max_length=64)
    contact_email: Optional[str] = Field(default=None, max_length=320)

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank.")
        if _FORBIDDEN_NAME_CHARS.search(value):
            raise ValueError("Display name contains unsupported characters.")
        return value

    @field_validator("contact_email")
    @classmethod
    def _validate_contact_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Contact email cannot be blank.")
        if not _CONTACT_EMAIL_RE.match(value):
            raise ValueError("Contact email is not a valid email address.")
        return value


class ConsentAcceptRequest(BaseModel):
    """POST /users/consent body. The client's reported version is never
    what gets persisted (the backend always stamps its own
    `CURRENT_LEGAL_VERSION`) — it's only compared against that constant
    to catch a stale frontend build serving outdated legal copy."""

    model_config = ConfigDict(extra="forbid")

    terms_version: str = Field(description="Legal version the frontend displayed for Terms of Service")
    privacy_version: str = Field(description="Legal version the frontend displayed for Privacy Policy")


class UserSyncResponse(BaseModel):
    user: UserResponse
    access_token: str = Field(description="Short-lived backend-issued bearer token for claim routes")
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until access_token expires")
