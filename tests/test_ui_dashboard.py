"""Tests for Phase 14 Plan 04 — dashboard and job history UI pages."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from policy_extractor.storage.models import Base, BatchJob, Poliza

# ---------------------------------------------------------------------------
# In-memory DB shared across all connections via StaticPool
# Must be set up BEFORE importing app so the override takes effect.
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


from policy_extractor.api import app, get_db  # noqa: E402 — after DB setup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def apply_db_override():
    """Apply DB override for every test in this module, then restore."""
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest.fixture(autouse=True)
def clean_tables():
    """Truncate tables before each test for isolation."""
    db = TestingSessionLocal()
    try:
        db.query(Poliza).delete()
        db.query(BatchJob).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def db_with_poliza():
    """Seed a poliza with evaluation_score=0.5 (below threshold) for review tests."""
    db = TestingSessionLocal()
    try:
        poliza = Poliza(
            numero_poliza="TEST-001",
            aseguradora="Aseguradora Test",
            nombre_contratante="Juan Test",
            evaluation_score=0.5,  # Below 0.70 threshold — will appear in review list
            extracted_at=datetime(2026, 3, 1, 10, 0, 0),
        )
        db.add(poliza)
        db.commit()
    finally:
        db.close()
    return db


@pytest.fixture()
def db_with_batch_job():
    """Seed a BatchJob for job history tests."""
    db = TestingSessionLocal()
    try:
        job = BatchJob(
            id="test-job-uuid-1234",
            batch_name="Lote Marzo 2026",
            status="complete",
            total_files=5,
            completed_files=5,
            failed_files=0,
            created_at=datetime(2026, 3, 20, 9, 0, 0),
            completed_at=datetime(2026, 3, 20, 9, 10, 0),
        )
        db.add(job)
        db.commit()
    finally:
        db.close()
    return db


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------


def test_dashboard_returns_200(client: TestClient):
    """GET / returns 200 with HTML containing Dashboard heading."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard" in response.text


def test_dashboard_contains_total_polizas(client: TestClient):
    """GET / returns HTML containing 'Total Polizas' stat card label."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Total Polizas" in response.text


def test_dashboard_contains_requieren_revision(client: TestClient):
    """GET / returns HTML containing 'Requieren revision' table section."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Requieren revision" in response.text


def test_dashboard_periodo_7d_returns_200(client: TestClient):
    """GET /?periodo=7d returns 200."""
    response = client.get("/?periodo=7d")
    assert response.status_code == 200


def test_dashboard_periodo_30d_returns_200(client: TestClient):
    """GET /?periodo=30d returns 200."""
    response = client.get("/?periodo=30d")
    assert response.status_code == 200


def test_dashboard_custom_date_range_returns_200(client: TestClient):
    """GET /?desde=2026-01-01&hasta=2026-03-20 returns 200 (custom date range per D-17)."""
    response = client.get("/?desde=2026-01-01&hasta=2026-03-20")
    assert response.status_code == 200


def test_dashboard_htmx_request_returns_partial(client: TestClient):
    """GET / with HX-Request header returns partial (no full DOCTYPE page)."""
    response = client.get("/", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "<!DOCTYPE" not in response.text
    # Partial should still contain stat card content
    assert "Total Polizas" in response.text


def test_dashboard_contains_custom_date_inputs(client: TestClient):
    """GET / response contains type=\"date\" custom date inputs per D-17."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'type="date"' in response.text


def test_dashboard_review_table_shows_low_score_poliza(client: TestClient, db_with_poliza):
    """Dashboard review table shows poliza with score < 0.70."""
    response = client.get("/")
    assert response.status_code == 200
    assert "TEST-001" in response.text


def test_dashboard_empty_review_shows_all_en_orden(client: TestClient):
    """Dashboard shows empty state when no polizas need review."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Todo en orden" in response.text


# ---------------------------------------------------------------------------
# Job history tests
# ---------------------------------------------------------------------------


def test_job_history_returns_200(client: TestClient):
    """GET /ui/lotes returns 200 with HTML containing 'Historial de Lotes'."""
    response = client.get("/ui/lotes")
    assert response.status_code == 200
    assert "Historial de Lotes" in response.text


def test_job_history_empty_state(client: TestClient):
    """GET /ui/lotes with no jobs shows 'Sin lotes anteriores' empty state."""
    response = client.get("/ui/lotes")
    assert response.status_code == 200
    assert "Sin lotes anteriores" in response.text


def test_job_history_shows_batch_job(client: TestClient, db_with_batch_job):
    """GET /ui/lotes lists batch jobs when they exist."""
    response = client.get("/ui/lotes")
    assert response.status_code == 200
    # Should show the batch name or partial ID
    assert "Lote Marzo 2026" in response.text or "test-job" in response.text
