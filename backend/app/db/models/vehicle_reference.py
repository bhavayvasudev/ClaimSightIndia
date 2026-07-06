"""Cached resolution of a "reference vehicle image" — a generic, licensed
visual representing the vehicle a claim describes (by make/model/year/
category), never the claimant's actual photographed vehicle.

Keyed by `normalized_query` (make+model+year+type, lowercased) rather than
by claim, since many claims share the same vehicle and resolution is a
pure function of those four fields — see `app/services/vehicle_reference.py`
for the resolver this caches.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VehicleReferenceImageRecord(Base):
    __tablename__ = "vehicle_reference_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    normalized_query: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    # e.g. "curated_catalog" | "category_fallback" — never a live external
    # search provider in the current MVP (see resolver module docstring).
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    match_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
