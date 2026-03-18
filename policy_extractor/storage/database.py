"""Database engine, session factory, and initialization."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base


def get_engine(db_path: str = "data/polizas.db"):
    """Create SQLAlchemy engine for the given SQLite database path."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return engine


def init_db(db_path: str = "data/polizas.db"):
    """Create all tables. Safe to call repeatedly (CREATE TABLE IF NOT EXISTS)."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


SessionLocal = sessionmaker(autocommit=False, autoflush=False)


if __name__ == "__main__":
    engine = init_db()
    print(f"Database initialized: {engine.url}")
