"""Legt Demo-Daten an (Familienmitglieder, Erinnerung, Paket).

So zeigt das Dashboard auch ohne konfigurierte Connectors sinnvolle Inhalte.
Nutzung (aus ``backend/``): python -m scripts.seed_demo
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.database import SessionLocal, init_db
from app.models.family import FamilyMember
from app.models.package import Package
from app.models.reminder import Reminder


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        if db.query(FamilyMember).count() == 0:
            db.add_all(
                [
                    FamilyMember(name="Constantin", color="#4f46e5", role="admin", avatar="👨"),
                    FamilyMember(name="Carina", color="#ec4899", role="partner", avatar="👩",
                                 birthday=(datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")),
                    FamilyMember(name="Kind", color="#22c55e", role="child", avatar="🧒"),
                ]
            )

        if db.query(Reminder).count() == 0:
            db.add(
                Reminder(
                    title="Müll rausbringen",
                    due_at=datetime.now().replace(hour=19, minute=0, second=0, microsecond=0),
                    priority="important",
                    source="user",
                )
            )

        if db.query(Package).count() == 0:
            db.add(
                Package(
                    carrier="dhl",
                    description="Amazon-Bestellung",
                    status="out_for_delivery",
                    expected_at=datetime.now().replace(hour=16, minute=0, second=0, microsecond=0),
                )
            )

        db.commit()
        print("✅ Demo-Daten angelegt.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
