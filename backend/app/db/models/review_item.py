"""Manual review queue items (Task 8).

Deliberately neutral language throughout — a review item records that
*something needs a human look*, never an accusation. See
`app/services/risk/risk_engine.py` and `app/services/policy/coverage_analysis.py`
docstrings for the "no fraud accusation" language rules that also apply here.

No admin/reviewer role system exists yet in this codebase (only claimant
Google accounts). Rather than bolt on an insecure "admin" flag, this model
and its repository/service exist as a clean data/service boundary with NO
public HTTP route that resolves a review item — see
`app/api/routes/claims.py` for the read-only, ownership-scoped surface a
normal signed-in claimant gets (their own claim shows "Under Review", never
the raw queue). Resolution is an internal capability for whenever a real
reviewer role is built; wiring a public resolve endpoint without one would
be an unauthenticated write to another table, which is exactly the
insecure-admin-panel shape this task explicitly warns against.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewItemSource(str, enum.Enum):
    DAMAGE_ASSESSMENT = "damage_assessment"
    POLICY_ANALYSIS = "policy_analysis"
    RISK_SIGNAL = "risk_signal"


class ReviewItemStatus(str, enum.Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"


class ReviewItemRecord(Base):
    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)

    # None = claim-level reason (e.g. a risk signal not tied to one part).
    part: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ReviewItemStatus.PENDING.value
    )
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
