"""Infrastructure tests for Phase 14 web UI foundation."""
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from policy_extractor.storage.models import Base, BatchJob
from policy_extractor.config import settings


# ---------------------------------------------------------------------------
# Task 1: BatchJob model and config tests
# ---------------------------------------------------------------------------


def _make_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


def test_batch_job_has_all_columns():
    """BatchJob model has all 9 required columns."""
    engine = _make_engine()
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("batch_jobs")}
    required = {
        "id",
        "batch_name",
        "status",
        "total_files",
        "completed_files",
        "failed_files",
        "created_at",
        "completed_at",
        "results_json",
    }
    assert required.issubset(columns), f"Missing columns: {required - columns}"


def test_batch_job_default_status_is_pending():
    """BatchJob default status is 'pending'."""
    import uuid

    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        job = BatchJob(id=str(uuid.uuid4()))
        db.add(job)
        db.commit()
        db.refresh(job)
        assert job.status == "pending"
    finally:
        db.close()


def test_review_score_threshold_default():
    """REVIEW_SCORE_THRESHOLD setting defaults to 0.70."""
    assert hasattr(settings, "REVIEW_SCORE_THRESHOLD")
    assert abs(settings.REVIEW_SCORE_THRESHOLD - 0.70) < 1e-9


def test_migration_004_creates_batch_jobs():
    """Alembic migration 004 source code contains batch_jobs table and inspector guard."""
    import pathlib

    migration_path = (
        pathlib.Path(__file__).parent.parent
        / "alembic"
        / "versions"
        / "004_batch_jobs.py"
    )
    assert migration_path.exists(), f"Migration file not found: {migration_path}"
    content = migration_path.read_text()
    assert "batch_jobs" in content
    assert "inspector" in content or "get_table_names" in content


# ---------------------------------------------------------------------------
# Task 2: Base template and HTTP route tests
# ---------------------------------------------------------------------------


def test_get_root_returns_200_html():
    """GET / returns 200 with text/html content type."""
    from fastapi.testclient import TestClient
    from policy_extractor.api import app

    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_get_root_contains_app_title():
    """Response body contains 'Extractor de Polizas' (app title in sidebar)."""
    from fastapi.testclient import TestClient
    from policy_extractor.api import app

    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/")
    assert "Extractor de Polizas" in response.text


def test_get_root_contains_tailwind_cdn():
    """Response body contains tailwindcss/browser@4 CDN tag."""
    from fastapi.testclient import TestClient
    from policy_extractor.api import app

    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/")
    assert "tailwindcss/browser@4" in response.text


def test_get_root_contains_htmx_cdn():
    """Response body contains htmx.org@2.0.8 CDN tag."""
    from fastapi.testclient import TestClient
    from policy_extractor.api import app

    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/")
    assert "htmx.org@2.0.8" in response.text


def test_get_root_contains_dashboard_nav():
    """Response body contains 'Dashboard' (sidebar nav item)."""
    from fastapi.testclient import TestClient
    from policy_extractor.api import app

    client = TestClient(app, raise_server_exceptions=True)
    response = client.get("/")
    assert "Dashboard" in response.text
