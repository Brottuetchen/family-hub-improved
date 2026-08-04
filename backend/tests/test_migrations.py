"""Tests für die Alembic-Migrationen (Schema-Treue + Bestandsschutz)."""

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (registriert alle Tabellen)
from app.config import settings
from app.core.database import Base, _alembic_config
from app.core.security import get_password_hash
from app.models.user import User


def _schema(engine):
    insp = inspect(engine)
    return {
        t: sorted(c["name"] for c in insp.get_columns(t))
        for t in insp.get_table_names()
        if t != "alembic_version"
    }


def test_alembic_head_matches_models(tmp_path, monkeypatch):
    # 'create_all' (Modell-Wahrheit) muss identisch zu 'upgrade head' sein.
    ref = create_engine(f"sqlite:///{tmp_path}/ref.db")
    Base.metadata.create_all(ref)
    ref_schema = _schema(ref)

    mig_url = f"sqlite:///{tmp_path}/mig.db"
    monkeypatch.setattr(settings, "database_url", mig_url)
    command.upgrade(_alembic_config(), "head")
    mig_schema = _schema(create_engine(mig_url))

    assert mig_schema == ref_schema
    assert "users" in mig_schema  # sanity


def test_stamp_preserves_existing_data(tmp_path, monkeypatch):
    # Alt-Installation: via create_all entstanden, mit Daten, OHNE alembic_version.
    url = f"sqlite:///{tmp_path}/existing.db"
    eng = create_engine(url)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(User(username="old", email="o@e.de", hashed_password=get_password_hash("x"),
                   role="admin", is_admin=True))
        s.commit()
    eng.dispose()

    monkeypatch.setattr(settings, "database_url", url)
    cfg = _alembic_config()
    insp = inspect(create_engine(url))
    assert insp.has_table("users") and not insp.has_table("alembic_version")

    # Bestandsschutz-Pfad (spiegelt init_db): Baseline stampen, dann upgrade head.
    base = ScriptDirectory.from_config(cfg).get_bases()[0]
    command.stamp(cfg, base)
    command.upgrade(cfg, "head")

    eng2 = create_engine(url)
    with eng2.connect() as conn:
        from sqlalchemy import text
        assert conn.execute(text("SELECT COUNT(*) FROM users WHERE username='old'")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar() == 1
