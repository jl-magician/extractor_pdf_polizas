"""Database engine, session factory, and initialization with Alembic migration support."""
import shutil
from pathlib import Path

from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from .models import Base


def get_engine(db_path: str = "data/polizas.db"):
    """Create SQLAlchemy engine with WAL mode enabled."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()
    return engine


def init_db(db_path: str = "data/polizas.db"):
    """Ensure DB schema is current.

    Two paths:
    - Fresh DB (no alembic_version table): create_all() + stamp head
    - Existing DB (has alembic_version): run pending migrations with backup
    """
    engine = get_engine(db_path)
    insp = inspect(engine)

    if "alembic_version" not in insp.get_table_names():
        # Fresh DB or pre-Alembic DB: create all tables and stamp head
        Base.metadata.create_all(engine)
        _stamp_head(db_path)
        logger.debug("Fresh database initialized and stamped at head")
    else:
        # Existing DB with Alembic tracking: apply pending migrations
        _auto_migrate(db_path)

    return engine


def _get_alembic_cfg(db_path: str):
    """Build Alembic Config pointing at the correct DB path.

    Resolves alembic.ini relative to project root (not CWD) so CLI
    works from any directory.
    """
    from alembic.config import Config

    ini_path = Path(__file__).parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _stamp_head(db_path: str) -> None:
    """Stamp the current head without running migrations (schema already correct)."""
    from alembic import command

    cfg = _get_alembic_cfg(db_path)
    command.stamp(cfg, "head")


def _auto_migrate(db_path: str) -> None:
    """Apply any pending Alembic migrations. Creates backup before migrating."""
    from alembic import command
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    cfg = _get_alembic_cfg(db_path)

    # Check if there are pending migrations
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        migration_context = MigrationContext.configure(conn)
        current_rev = migration_context.get_current_revision()

    script = ScriptDirectory.from_config(cfg)
    head_rev = script.get_current_head()

    if current_rev != head_rev:
        # Create backup before migrating
        db_file = Path(db_path)
        if db_file.exists():
            backup_path = str(db_file) + ".bak"
            shutil.copy2(str(db_file), backup_path)
            logger.info(f"Migration backup created: {backup_path}")

        command.upgrade(cfg, "head")
        logger.info("Database migrations applied successfully")
    else:
        logger.debug("Database already at head revision")


SessionLocal = sessionmaker(autocommit=False, autoflush=False)


if __name__ == "__main__":
    engine = init_db()
    print(f"Database initialized: {engine.url}")
