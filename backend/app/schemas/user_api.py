"""Request/response schemas for `app/api/routes/users.py`."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.user import UserRecord


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
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None

    @classmethod
    def from_record(cls, record: UserRecord) -> "UserResponse":
        return cls(id=record.id, email=record.email, name=record.name, avatar_url=record.avatar_url)


class UserSyncResponse(BaseModel):
    user: UserResponse
    access_token: str = Field(description="Short-lived backend-issued bearer token for claim routes")
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until access_token expires")
