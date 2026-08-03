"""Paket-Tracking (DHL, DPD, GLS, Amazon, ...)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    carrier = Column(String, nullable=False)  # dhl | dpd | gls | amazon | other
    tracking_number = Column(String, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String, default="in_transit")  # in_transit | out_for_delivery | delivered
    expected_at = Column(DateTime, nullable=True)
    family_member_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def tracking_url(self) -> str | None:
        """Zusteller-Sendungsverfolgungs-Link (falls Trackingnummer vorhanden)."""
        from app.services.tracking import tracking_url

        return tracking_url(self.carrier, self.tracking_number)
