"""Tests for PDF upload API endpoints -- Phase 8 Plan 01.

Covers:
- POST /polizas/upload validation (PDF magic bytes, extension, size)
- 202 response with job object
- GET /jobs/{job_id} polling
- GET /jobs list
- Job expiry purge
"""
import io
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from policy_extractor.storage.models import Base

# ---------------------------------------------------------------------------
# In-memory DB for tests — must happen BEFORE importing app
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


from policy_extractor.api import app, get_db  # noqa: E402 — must be after DB setup

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_PDF_BYTES = b"%PDF-1.4 test content"


@pytest.fixture(autouse=True)
def override_db():
    """Apply DB override scoped to each upload test, then restore previous override."""
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest.fixture(autouse=True)
def clean_job_store():
    """Clear the in-memory job store before and after each test."""
    from policy_extractor.api import upload

    upload._job_store.clear()
    yield
    upload._job_store.clear()


@pytest.fixture(autouse=True)
def use_tmp_uploads(tmp_path):
    """Redirect UPLOADS_DIR to a temporary directory for each test."""
    from policy_extractor.api import upload

    original = upload.UPLOADS_DIR
    upload.UPLOADS_DIR = tmp_path
    yield tmp_path
    upload.UPLOADS_DIR = original


# ---------------------------------------------------------------------------
# Upload validation tests
# ---------------------------------------------------------------------------


@patch("policy_extractor.api.upload._run_extraction")
def test_upload_valid_pdf_returns_202(mock_run):
    """POST /polizas/upload with a valid PDF returns 202 with job object."""
    response = client.post(
        "/polizas/upload",
        files={"file": ("test.pdf", io.BytesIO(_VALID_PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "pending"
    assert body["filename"] == "test.pdf"
    assert "created_at" in body
    mock_run.assert_called_once()


@patch("policy_extractor.api.upload._run_extraction")
def test_upload_non_pdf_extension_rejected(mock_run):
    """POST /polizas/upload with a non-.pdf filename returns 422."""
    response = client.post(
        "/polizas/upload",
        files={"file": ("test.txt", io.BytesIO(_VALID_PDF_BYTES), "text/plain")},
    )
    assert response.status_code == 422
    assert "pdf extension" in response.json()["detail"].lower()
    mock_run.assert_not_called()


@patch("policy_extractor.api.upload._run_extraction")
def test_upload_non_pdf_magic_bytes_rejected(mock_run):
    """POST /polizas/upload with .pdf extension but non-PDF content returns 422."""
    response = client.post(
        "/polizas/upload",
        files={"file": ("test.pdf", io.BytesIO(b"not a pdf file"), "application/pdf")},
    )
    assert response.status_code == 422
    assert "not a valid pdf" in response.json()["detail"].lower()
    mock_run.assert_not_called()


@patch("policy_extractor.api.upload._run_extraction")
def test_upload_oversized_file_rejected(mock_run):
    """POST /polizas/upload with a file over 50 MB returns 413."""
    oversized = b"%PDF" + b"\x00" * (50 * 1024 * 1024 - 3)
    response = client.post(
        "/polizas/upload",
        files={"file": ("big.pdf", io.BytesIO(oversized), "application/pdf")},
    )
    assert response.status_code == 413
    assert "50 mb" in response.json()["detail"].lower()
    mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Job polling tests
# ---------------------------------------------------------------------------


@patch("policy_extractor.api.upload._run_extraction")
def test_get_job_returns_job(mock_run):
    """GET /jobs/{job_id} returns the job object after a valid upload."""
    upload_resp = client.post(
        "/polizas/upload",
        files={"file": ("test.pdf", io.BytesIO(_VALID_PDF_BYTES), "application/pdf")},
    )
    assert upload_resp.status_code == 202
    job_id = upload_resp.json()["job_id"]

    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert body["status"] == "pending"


def test_get_job_unknown_returns_404():
    """GET /jobs/<nonexistent-id> returns 404."""
    response = client.get("/jobs/nonexistent-id-that-does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@patch("policy_extractor.api.upload._run_extraction")
def test_list_jobs_returns_all(mock_run):
    """GET /jobs returns a list containing all uploaded jobs."""
    client.post(
        "/polizas/upload",
        files={"file": ("first.pdf", io.BytesIO(_VALID_PDF_BYTES), "application/pdf")},
    )
    client.post(
        "/polizas/upload",
        files={"file": ("second.pdf", io.BytesIO(_VALID_PDF_BYTES), "application/pdf")},
    )

    response = client.get("/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 2
    filenames = {j["filename"] for j in jobs}
    assert "first.pdf" in filenames
    assert "second.pdf" in filenames


def test_list_jobs_empty():
    """GET /jobs with no uploads returns an empty list."""
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Job expiry test
# ---------------------------------------------------------------------------


def test_job_expiry_purges_expired():
    """Jobs with a past expires_at are removed from the store on next read."""
    from policy_extractor.api import upload

    job = upload._create_job("expired.pdf")
    job_id = job["job_id"]

    # Force the job into a completed-but-expired state
    with upload._store_lock:
        upload._job_store[job_id]["status"] = "complete"
        upload._job_store[job_id]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat()

    # Polling should purge and return 404
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 404
