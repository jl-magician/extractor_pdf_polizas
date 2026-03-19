"""End-to-end migration chain tests for Alembic schema versioning."""
import pytest
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session  # noqa: F401 (used in integration tests below)
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext

from policy_extractor.storage.models import Base, Poliza


def make_alembic_cfg(db_path: str) -> Config:
    """Create an Alembic Config pointing at the given DB file (absolute alembic.ini path)."""
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_fresh_db_upgrade_head(tmp_path):
    """Fresh DB: upgrade head creates all tables and lands at head revision."""
    db_file = str(tmp_path / "fresh.db")
    cfg = make_alembic_cfg(db_file)
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_file}")
    insp = inspect(engine)
    table_names = insp.get_table_names()

    assert "polizas" in table_names
    assert "asegurados" in table_names
    assert "coberturas" in table_names
    assert "ingestion_cache" in table_names
    assert "alembic_version" in table_names

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() is not None


def test_evaluation_columns_present_after_002(tmp_path):
    """After upgrade to head (002), polizas table has all four evaluation columns."""
    db_file = str(tmp_path / "test.db")
    cfg = make_alembic_cfg(db_file)
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_file}")
    insp = inspect(engine)
    col_names = [c["name"] for c in insp.get_columns("polizas")]

    assert "evaluation_score" in col_names
    assert "evaluation_json" in col_names
    assert "evaluated_at" in col_names
    assert "evaluated_model_id" in col_names


def test_existing_db_upgrade_head_no_data_loss(tmp_path):
    """Existing DB with data: upgrade from 001 to head preserves existing rows."""
    db_file = str(tmp_path / "existing.db")
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    # Insert a row before migration
    with Session(engine) as session:
        session.add(Poliza(numero_poliza="TEST-001", aseguradora="Test SA"))
        session.commit()

    # Stamp as 001 to simulate a pre-002 existing DB
    cfg = make_alembic_cfg(db_file)
    command.stamp(cfg, "001")

    # Apply migration 002
    command.upgrade(cfg, "head")

    # Row must still be present
    with Session(engine) as session:
        poliza = session.query(Poliza).filter_by(numero_poliza="TEST-001").first()
        assert poliza is not None
        assert poliza.aseguradora == "Test SA"

    # Evaluation columns must exist
    insp = inspect(engine)
    col_names = [c["name"] for c in insp.get_columns("polizas")]
    assert "evaluation_score" in col_names
    assert "evaluation_json" in col_names
    assert "evaluated_at" in col_names
    assert "evaluated_model_id" in col_names


def test_downgrade_002_removes_evaluation_columns(tmp_path):
    """Downgrade from 002 back to 001 removes all four evaluation columns."""
    db_file = str(tmp_path / "downgrade.db")
    cfg = make_alembic_cfg(db_file)
    command.upgrade(cfg, "head")

    # Downgrade to 001
    command.downgrade(cfg, "001")

    engine = create_engine(f"sqlite:///{db_file}")
    insp = inspect(engine)
    col_names = [c["name"] for c in insp.get_columns("polizas")]

    assert "evaluation_score" not in col_names
    assert "evaluation_json" not in col_names
    assert "evaluated_at" not in col_names
    assert "evaluated_model_id" not in col_names


def test_wal_mode_enabled_after_migration(tmp_path):
    """After upgrade head, SQLite is in WAL journal mode."""
    db_file = str(tmp_path / "wal.db")
    cfg = make_alembic_cfg(db_file)
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_file}")
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert result == "wal"


# --- Integration tests for init_db guard logic (Plan 02) ---

from policy_extractor.storage.database import get_engine, init_db, _get_alembic_cfg  # noqa: E402


def test_init_db_fresh_creates_and_stamps(tmp_path):
    """Fresh DB: init_db() creates all tables and stamps at head revision."""
    db_file = str(tmp_path / "fresh.db")
    init_db(db_file)

    engine = create_engine(f"sqlite:///{db_file}")
    insp = inspect(engine)
    table_names = insp.get_table_names()

    assert "polizas" in table_names
    assert "alembic_version" in table_names

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() is not None


def test_init_db_existing_db_auto_migrates(tmp_path):
    """Existing DB stamped at 001: init_db() auto-migrates to head and preserves data."""
    db_file = tmp_path / "existing.db"
    db_path = str(db_file)

    # Build schema and insert a row
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Poliza(numero_poliza="GUARD-001", aseguradora="Guard SA"))
        session.commit()
    engine.dispose()

    # Stamp at 001 to simulate a pre-002 existing DB
    cfg = _get_alembic_cfg(db_path)
    command.stamp(cfg, "001")

    # init_db should detect alembic_version and run _auto_migrate to apply 002
    init_db(db_path)

    engine2 = create_engine(f"sqlite:///{db_path}")
    # Row must still be present
    with Session(engine2) as session:
        poliza = session.query(Poliza).filter_by(numero_poliza="GUARD-001").first()
        assert poliza is not None
        assert poliza.aseguradora == "Guard SA"

    # Evaluation columns must exist after 002
    insp = inspect(engine2)
    col_names = [c["name"] for c in insp.get_columns("polizas")]
    assert "evaluation_score" in col_names
    assert "evaluation_json" in col_names
    assert "evaluated_at" in col_names
    assert "evaluated_model_id" in col_names


def test_auto_migrate_creates_backup(tmp_path):
    """When pending migrations exist, init_db() creates a .bak backup file."""
    db_file = tmp_path / "migrate.db"
    db_path = str(db_file)

    # Build schema and stamp at 001 (so 002 is pending)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()

    cfg = _get_alembic_cfg(db_path)
    command.stamp(cfg, "001")

    # Trigger auto-migrate via init_db
    init_db(db_path)

    # Backup must exist
    assert Path(db_path + ".bak").exists()


def test_get_engine_enables_wal(tmp_path):
    """get_engine() sets SQLite WAL journal mode on the returned engine."""
    engine = get_engine(str(tmp_path / "wal_test.db"))
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert result == "wal"
