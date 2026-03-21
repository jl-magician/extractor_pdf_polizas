"""Tests for Phase 14-02 batch upload UI endpoints.

Covers:
- GET /subir — upload page renders with correct HTML
- POST /ui/batch/upload — creates BatchJob, returns progress partial
- GET /ui/batch/{id}/status — returns 404 for unknown batch, progress or summary
- GET /ui/batch/{id}/export/{fmt} — returns correct errors and downloadable files
"""
import io
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from policy_extractor.storage.models import Base, BatchJob, Poliza

# ---------------------------------------------------------------------------
# In-memory DB override — must happen before app import
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


from policy_extractor.api import app, get_db  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_PDF_BYTES = b"%PDF-1.4 test content for upload UI tests"


@pytest.fixture(autouse=True)
def override_db():
    """Apply and restore DB override for each test."""
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def db_session():
    """Provide a direct DB session for seeding test data."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_batch(db_session, *, status="complete", total=2, completed=2, failed=0, results=None):
    """Helper to create a BatchJob in the test DB."""
    batch_id = str(uuid.uuid4())
    if results is None:
        results = []
    batch = BatchJob(
        id=batch_id,
        batch_name="Test Lote",
        status=status,
        total_files=total,
        completed_files=completed,
        failed_files=failed,
        created_at=datetime.now(timezone.utc),
        results_json=json.dumps(results) if results else None,
    )
    db_session.add(batch)
    db_session.commit()
    return batch_id


def _make_poliza(db_session, *, numero_poliza="POL-001", aseguradora="Zurich"):
    """Helper to create a minimal Poliza in the test DB."""
    poliza = Poliza(
        numero_poliza=numero_poliza,
        aseguradora=aseguradora,
        tipo_seguro="auto",
        moneda="MXN",
    )
    db_session.add(poliza)
    db_session.commit()
    db_session.refresh(poliza)
    return poliza.id


# ---------------------------------------------------------------------------
# Task 3 tests: GET /subir
# ---------------------------------------------------------------------------


def test_get_upload_page_returns_200(client):
    """GET /subir returns 200 with text/html."""
    response = client.get("/subir")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_get_upload_page_contains_arrastra(client):
    """GET /subir returns HTML containing 'Arrastra tus PDFs'."""
    response = client.get("/subir")
    assert "Arrastra tus PDFs" in response.text


def test_get_upload_page_contains_procesar_lote(client):
    """GET /subir returns HTML containing 'Procesar Lote'."""
    response = client.get("/subir")
    assert "Procesar Lote" in response.text


def test_get_upload_page_contains_hx_post(client):
    """GET /subir contains hx-post='/ui/batch/upload'."""
    response = client.get("/subir")
    assert "hx-post" in response.text
    assert "/ui/batch/upload" in response.text


def test_get_upload_page_contains_nombre_lote(client):
    """GET /subir contains batch name input."""
    response = client.get("/subir")
    assert "Nombre del lote" in response.text


# ---------------------------------------------------------------------------
# POST /ui/batch/upload
# ---------------------------------------------------------------------------


def test_upload_batch_returns_200_html(client):
    """POST /ui/batch/upload with valid PDF returns 200 HTML with batch-status div."""
    with patch("policy_extractor.api.ui.upload_views.threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        response = client.post(
            "/ui/batch/upload",
            files=[("files", ("test.pdf", io.BytesIO(_VALID_PDF_BYTES), "application/pdf"))],
            data={"batch_name": "Test Batch"},
        )
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "batch-status" in response.text


def test_upload_batch_no_pdf_returns_400(client):
    """POST /ui/batch/upload with no PDF file returns 400."""
    response = client.post(
        "/ui/batch/upload",
        files=[("files", ("notapdf.txt", io.BytesIO(b"text content"), "text/plain"))],
        data={"batch_name": "Test"},
    )
    assert response.status_code == 400


def test_upload_batch_creates_batch_job(client, db_session):
    """POST /ui/batch/upload creates a BatchJob row in the DB."""
    with patch("policy_extractor.api.ui.upload_views.threading.Thread") as mock_thread:
        mock_thread.return_value.start = lambda: None
        client.post(
            "/ui/batch/upload",
            files=[("files", ("test.pdf", io.BytesIO(_VALID_PDF_BYTES), "application/pdf"))],
            data={"batch_name": "My Batch"},
        )
    batches = db_session.query(BatchJob).all()
    assert len(batches) >= 1
    batch = batches[-1]
    assert batch.batch_name == "My Batch"
    assert batch.total_files == 1
    assert batch.status == "processing"


# ---------------------------------------------------------------------------
# GET /ui/batch/{id}/status
# ---------------------------------------------------------------------------


def test_batch_status_404_for_unknown(client):
    """GET /ui/batch/{id}/status returns 404 for non-existent batch."""
    response = client.get(f"/ui/batch/{uuid.uuid4()}/status")
    assert response.status_code == 404


def test_batch_status_returns_progress_when_processing(client, db_session):
    """GET /ui/batch/{id}/status returns progress partial for processing batch."""
    batch_id = _make_batch(db_session, status="processing", total=3, completed=1, failed=0)
    response = client.get(f"/ui/batch/{batch_id}/status")
    assert response.status_code == 200
    assert "batch-status" in response.text
    # Should poll every 2s
    assert "every 2s" in response.text


def test_batch_status_returns_summary_when_complete(client, db_session):
    """GET /ui/batch/{id}/status returns summary partial and HX-Trigger when complete."""
    results = [
        {"filename": "pol1.pdf", "status": "complete", "poliza_id": None, "numero_poliza": "P-001", "aseguradora": "Zurich", "error": None}
    ]
    batch_id = _make_batch(db_session, status="complete", total=1, completed=1, results=results)
    response = client.get(f"/ui/batch/{batch_id}/status")
    assert response.status_code == 200
    assert "Resultados del lote" in response.text
    assert "HX-Trigger" in response.headers or "hx-trigger" in response.headers


# ---------------------------------------------------------------------------
# GET /ui/batch/{id}/export/{fmt}
# ---------------------------------------------------------------------------


def test_batch_export_404_for_unknown_batch(client):
    """GET /ui/batch/{id}/export/xlsx returns 404 for non-existent batch."""
    response = client.get(f"/ui/batch/{uuid.uuid4()}/export/xlsx")
    assert response.status_code == 404


def test_batch_export_400_when_not_complete(client, db_session):
    """GET /ui/batch/{id}/export/xlsx returns 400 when batch is not complete."""
    batch_id = _make_batch(db_session, status="processing", results=None)
    response = client.get(f"/ui/batch/{batch_id}/export/xlsx")
    assert response.status_code == 400


def test_batch_export_400_invalid_format(client, db_session):
    """GET /ui/batch/{id}/export/invalid_fmt returns 400 with 'no soportado'."""
    batch_id = _make_batch(db_session, status="complete")
    response = client.get(f"/ui/batch/{batch_id}/export/invalid_fmt")
    assert response.status_code == 400
    assert "no soportado" in response.text.lower() or "no soportado" in response.json().get("detail", "").lower()


def test_batch_export_xlsx_returns_spreadsheet(client, db_session):
    """GET /ui/batch/{id}/export/xlsx returns 200 with spreadsheet content-type."""
    poliza_id = _make_poliza(db_session, numero_poliza="EXP-XLSX-001", aseguradora="AXA")
    results = [
        {
            "filename": "pol.pdf",
            "status": "complete",
            "poliza_id": poliza_id,
            "numero_poliza": "EXP-XLSX-001",
            "aseguradora": "AXA",
            "error": None,
        }
    ]
    batch_id = _make_batch(db_session, status="complete", total=1, completed=1, results=results)
    response = client.get(f"/ui/batch/{batch_id}/export/xlsx")
    assert response.status_code == 200
    ct = response.headers.get("content-type", "")
    assert "spreadsheet" in ct or "excel" in ct or "openxmlformats" in ct


def test_batch_export_csv_returns_csv(client, db_session):
    """GET /ui/batch/{id}/export/csv returns 200 with text/csv content-type."""
    poliza_id = _make_poliza(db_session, numero_poliza="EXP-CSV-001", aseguradora="GNP")
    results = [
        {
            "filename": "pol.pdf",
            "status": "complete",
            "poliza_id": poliza_id,
            "numero_poliza": "EXP-CSV-001",
            "aseguradora": "GNP",
            "error": None,
        }
    ]
    batch_id = _make_batch(db_session, status="complete", total=1, completed=1, results=results)
    response = client.get(f"/ui/batch/{batch_id}/export/csv")
    assert response.status_code == 200
    ct = response.headers.get("content-type", "")
    assert "csv" in ct or "text" in ct


def test_batch_export_json_returns_json(client, db_session):
    """GET /ui/batch/{id}/export/json returns 200 with application/json content-type."""
    poliza_id = _make_poliza(db_session, numero_poliza="EXP-JSON-001", aseguradora="Mapfre")
    results = [
        {
            "filename": "pol.pdf",
            "status": "complete",
            "poliza_id": poliza_id,
            "numero_poliza": "EXP-JSON-001",
            "aseguradora": "Mapfre",
            "error": None,
        }
    ]
    batch_id = _make_batch(db_session, status="complete", total=1, completed=1, results=results)
    response = client.get(f"/ui/batch/{batch_id}/export/json")
    assert response.status_code == 200
    ct = response.headers.get("content-type", "")
    assert "application/json" in ct
