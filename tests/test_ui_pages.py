"""Tests for Phase 14 Plan 03 — poliza list and detail UI pages."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from policy_extractor.storage.models import Base, Poliza

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
def clean_polizas_table():
    """Truncate polizas table before each test for isolation."""
    db = TestingSessionLocal()
    try:
        db.query(Poliza).delete()
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def test_poliza():
    """Insert and yield a seeded Poliza record."""
    db = TestingSessionLocal()
    try:
        poliza = Poliza(
            numero_poliza="TEST-001",
            aseguradora="Zurich",
            tipo_seguro="Auto",
            nombre_contratante="Juan Perez",
            moneda="MXN",
        )
        db.add(poliza)
        db.commit()
        db.refresh(poliza)
        poliza_id = poliza.id
    finally:
        db.close()

    # Re-fetch so the object is detached-safe for use in tests
    db2 = TestingSessionLocal()
    try:
        obj = db2.get(Poliza, poliza_id)
        db2.expunge(obj)
        return obj
    finally:
        db2.close()


client = TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Poliza list tests
# ---------------------------------------------------------------------------


def test_poliza_list_returns_200():
    """GET /ui/polizas returns 200 with text/html content type."""
    response = client.get("/ui/polizas")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_poliza_list_contains_polizas_heading():
    """GET /ui/polizas HTML response contains 'Polizas'."""
    response = client.get("/ui/polizas")
    assert "Polizas" in response.text


def test_poliza_list_contains_poliza_rows_id(test_poliza):
    """GET /ui/polizas contains the 'poliza-rows' table body id."""
    response = client.get("/ui/polizas")
    assert "poliza-rows" in response.text


def test_poliza_list_htmx_request_returns_partial(test_poliza):
    """GET /ui/polizas with HX-Request header returns rows partial only (no DOCTYPE)."""
    response = client.get("/ui/polizas", headers={"HX-Request": "true"})
    assert response.status_code == 200
    # Partial should NOT contain full page DOCTYPE
    assert "<!DOCTYPE" not in response.text


def test_poliza_detail_returns_200_for_existing(test_poliza):
    """GET /ui/polizas/{id} returns 200 for an existing poliza."""
    response = client.get(f"/ui/polizas/{test_poliza.id}")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_poliza_detail_returns_404_for_missing():
    """GET /ui/polizas/99999 returns 404 for a non-existent poliza."""
    response = client.get("/ui/polizas/99999")
    assert response.status_code == 404


def test_poliza_list_search_returns_200(test_poliza):
    """GET /ui/polizas?q=test returns 200 (search works without error)."""
    response = client.get("/ui/polizas?q=test")
    assert response.status_code == 200


def test_poliza_list_search_finds_poliza(test_poliza):
    """Search by poliza number returns matching record."""
    response = client.get(f"/ui/polizas?q={test_poliza.numero_poliza}")
    assert response.status_code == 200
    assert test_poliza.numero_poliza in response.text


def test_poliza_detail_contains_numero_poliza(test_poliza):
    """Detail page shows the poliza numero_poliza value."""
    response = client.get(f"/ui/polizas/{test_poliza.id}")
    assert test_poliza.numero_poliza in response.text


def test_poliza_detail_contains_export_link(test_poliza):
    """Detail page contains 'Descargar Excel' export link."""
    response = client.get(f"/ui/polizas/{test_poliza.id}")
    assert "Descargar Excel" in response.text


# ---------------------------------------------------------------------------
# Phase 16 Plan 01 — PDF report download tests
# ---------------------------------------------------------------------------


def test_poliza_report_download(test_poliza):
    """GET /ui/polizas/{id}/report returns 200 with application/pdf content type."""
    response = client.get(f"/ui/polizas/{test_poliza.id}/report")
    assert response.status_code == 200
    assert "application/pdf" in response.headers.get("content-type", "")
    assert "attachment" in response.headers.get("content-disposition", "")
    assert response.content[:5] == b"%PDF-", "Response body must start with PDF header"


def test_poliza_report_404(test_poliza):
    """GET /ui/polizas/99999/report returns 404 for non-existent poliza."""
    response = client.get("/ui/polizas/99999/report")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Evaluation score badge and dashboard eval stats tests (Phase 16 Plan 03)
# ---------------------------------------------------------------------------


def test_dashboard_eval_stats_no_evaluations():
    """GET / with no evaluated polizas shows 'sin evaluaciones' or '--'."""
    response = client.get("/")
    assert response.status_code == 200
    # When no polizas are evaluated, avg_score_display is None → shows 'sin evaluaciones' or '--'
    assert "sin evaluaciones" in response.text or "--" in response.text


def test_dashboard_eval_stats_with_evaluations():
    """GET / with evaluated polizas shows 'Evaluacion de Calidad' card with counts."""
    db = TestingSessionLocal()
    try:
        db.add(Poliza(
            numero_poliza="EVAL-001",
            aseguradora="Zurich",
            evaluation_score=0.85,
        ))
        db.add(Poliza(
            numero_poliza="EVAL-002",
            aseguradora="AXA",
            evaluation_score=0.65,
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/")
    assert response.status_code == 200
    assert "Evaluacion de Calidad" in response.text
    assert "2 de" in response.text


def test_poliza_list_score_badge():
    """Poliza with evaluation_score=0.9 shows green badge (bg-green-100) on list."""
    db = TestingSessionLocal()
    try:
        db.add(Poliza(
            numero_poliza="GREEN-001",
            aseguradora="Zurich",
            evaluation_score=0.9,
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/ui/polizas")
    assert response.status_code == 200
    assert "bg-green-100" in response.text


def test_poliza_list_no_score():
    """Poliza with evaluation_score=None shows '--' on list (no crash)."""
    db = TestingSessionLocal()
    try:
        db.add(Poliza(
            numero_poliza="NOSCORE-001",
            aseguradora="Zurich",
            evaluation_score=None,
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/ui/polizas")
    assert response.status_code == 200
    assert "--" in response.text
