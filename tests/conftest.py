"""Shared test fixtures for policy_extractor tests."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from policy_extractor.storage.models import Base


@pytest.fixture
def engine():
    """In-memory SQLite engine with all tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """SQLAlchemy session bound to in-memory engine."""
    with Session(engine) as session:
        yield session
