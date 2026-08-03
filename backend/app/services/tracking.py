"""Paket-Tracking-Heuristik: Carrier-Erkennung & Tracking-URLs (best effort)."""

from __future__ import annotations

from typing import Optional

_TRACKING_URLS = {
    "dhl": "https://www.dhl.de/de/privatkunden/pakete-empfangen/verfolgen.html?piececode={n}",
    "dpd": "https://tracking.dpd.de/status/de_DE/parcel/{n}",
    "gls": "https://gls-group.com/DE/de/paketverfolgung?match={n}",
    "amazon": "https://track.amazon.de/tracking/{n}",
    "ups": "https://www.ups.com/track?tracknum={n}",
    "hermes": "https://www.myhermes.de/empfangen/sendungsverfolgung/sendungsinformation/#{n}",
}


def detect_carrier(tracking_number: Optional[str]) -> str:
    """Errät den Zusteller anhand des Trackingnummer-Musters."""
    if not tracking_number:
        return "other"
    t = tracking_number.upper().strip().replace(" ", "")
    if t.startswith("TBA"):
        return "amazon"
    if t.startswith("1Z"):
        return "ups"
    if t.startswith("JVGL") or t.startswith("GLS"):
        return "gls"
    if t.startswith("JJD") or (t.isdigit() and len(t) in (12, 14, 20)):
        return "dhl"
    if t.isdigit() and len(t) in (11, 15, 16):
        return "dpd"
    return "other"


def tracking_url(carrier: Optional[str], tracking_number: Optional[str]) -> Optional[str]:
    if not carrier or not tracking_number:
        return None
    template = _TRACKING_URLS.get(carrier.lower())
    return template.format(n=tracking_number.strip()) if template else None
