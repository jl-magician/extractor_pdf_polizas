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
from unittest.mock import MagicMock, patch

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


# ---------------------------------------------------------------------------
# Pipeline integration tests (Phase 8 Plan 02)
# Tests call _run_extraction directly (synchronously) with mocked pipeline
# ---------------------------------------------------------------------------


@patch("policy_extractor.storage.database.SessionLocal")
@patch("policy_extractor.storage.writer.orm_to_schema")
@patch("policy_extractor.storage.writer.upsert_policy")
@patch("policy_extractor.extraction.extract_policy")
@patch("policy_extractor.ingestion.ingest_pdf")
@patch("policy_extractor.cli_helpers.is_already_extracted", return_value=False)
@patch("policy_extractor.ingestion.cache.compute_file_hash", return_value="abc123")
def test_pipeline_success_sets_complete(
    mock_hash, mock_already, mock_ingest, mock_extract, mock_upsert, mock_orm, mock_session, tmp_path
):
    """Successful pipeline sets job status=complete with result dict."""
    from policy_extractor.api import upload

    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test")
    job = upload._create_job("test.pdf")

    fake_extraction = MagicMock()
    fake_extraction.model_dump.return_value = {"numero_poliza": "POL-001"}
    mock_extract.return_value = (fake_extraction, MagicMock(), 0)
    mock_session.return_value = MagicMock()

    upload._run_extraction(job["job_id"], pdf_file, None, False)

    result_job = upload._get_job(job["job_id"])
    assert result_job["status"] == "complete"
    assert result_job["result"] is not None
    mock_ingest.assert_called_once()
    mock_extract.assert_called_once()
    mock_upsert.assert_called_once()


@patch("policy_extractor.storage.database.SessionLocal")
@patch("policy_extractor.storage.writer.orm_to_schema")
@patch("policy_extractor.storage.writer.upsert_policy")
@patch("policy_extractor.extraction.extract_policy")
@patch("policy_extractor.ingestion.ingest_pdf")
@patch("policy_extractor.cli_helpers.is_already_extracted", return_value=False)
@patch("policy_extractor.ingestion.cache.compute_file_hash", return_value="abc123")
def test_pipeline_failure_sets_failed(
    mock_hash, mock_already, mock_ingest, mock_extract, mock_upsert, mock_orm, mock_session, tmp_path
):
    """When extract_policy raises, job status becomes failed with error message."""
    from policy_extractor.api import upload

    pdf_file = tmp_path / "fail.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test")
    job = upload._create_job("fail.pdf")

    mock_extract.side_effect = RuntimeError("Claude API error")
    mock_session.return_value.__enter__ = lambda s: s
    mock_session.return_value.__exit__ = lambda s, *a: None

    upload._run_extraction(job["job_id"], pdf_file, None, False)

    result_job = upload._get_job(job["job_id"])
    assert result_job["status"] == "failed"
    assert "Claude API error" in result_job["error"]


@patch("policy_extractor.storage.database.SessionLocal")
@patch("policy_extractor.storage.writer.orm_to_schema")
@patch("policy_extractor.storage.writer.upsert_policy")
@patch("policy_extractor.extraction.extract_policy")
@patch("policy_extractor.ingestion.ingest_pdf")
@patch("policy_extractor.cli_helpers.is_already_extracted", return_value=False)
@patch("policy_extractor.ingestion.cache.compute_file_hash", return_value="abc123")
def test_pdf_cleanup_on_success(
    mock_hash, mock_already, mock_ingest, mock_extract, mock_upsert, mock_orm, mock_session, tmp_path
):
    """After successful extraction, the uploaded PDF is deleted from disk."""
    from policy_extractor.api import upload

    pdf_file = tmp_path / "cleanup.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test")
    job = upload._create_job("cleanup.pdf")

    fake_extraction = MagicMock()
    fake_extraction.model_dump.return_value = {"numero_poliza": "POL-002"}
    mock_extract.return_value = (fake_extraction, MagicMock(), 0)
    mock_session.return_value = MagicMock()

    upload._run_extraction(job["job_id"], pdf_file, None, False)

    assert not pdf_file.exists(), "PDF should be deleted after successful extraction"


@patch("policy_extractor.storage.database.SessionLocal")
@patch("policy_extractor.storage.writer.orm_to_schema")
@patch("policy_extractor.storage.writer.upsert_policy")
@patch("policy_extractor.extraction.extract_policy")
@patch("policy_extractor.ingestion.ingest_pdf")
@patch("policy_extractor.cli_helpers.is_already_extracted", return_value=False)
@patch("policy_extractor.ingestion.cache.compute_file_hash", return_value="abc123")
def test_pdf_kept_on_failure(
    mock_hash, mock_already, mock_ingest, mock_extract, mock_upsert, mock_orm, mock_session, tmp_path
):
    """After failed extraction, the uploaded PDF is kept on disk for debugging."""
    from policy_extractor.api import upload

    pdf_file = tmp_path / "kept.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test")
    job = upload._create_job("kept.pdf")

    mock_extract.side_effect = RuntimeError("Extraction failed")
    mock_session.return_value = MagicMock()

    upload._run_extraction(job["job_id"], pdf_file, None, False)

    assert pdf_file.exists(), "PDF should be kept after failed extraction"


@patch("policy_extractor.storage.database.SessionLocal")
@patch("policy_extractor.storage.writer.orm_to_schema")
@patch("policy_extractor.cli_helpers.is_already_extracted", return_value=True)
@patch("policy_extractor.ingestion.ingest_pdf")
@patch("policy_extractor.extraction.extract_policy")
@patch("policy_extractor.ingestion.cache.compute_file_hash", return_value="abc123")
def test_idempotent_upload_skips_extraction(
    mock_hash, mock_extract, mock_ingest, mock_already, mock_orm, mock_session, tmp_path
):
    """When hash already extracted and force=False, extraction is skipped."""
    from policy_extractor.api import upload

    pdf_file = tmp_path / "idempotent.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test")
    job = upload._create_job("idempotent.pdf")

    # Mock the DB session + query chain for the selectinload path
    fake_poliza = MagicMock()
    mock_session_instance = MagicMock()
    mock_session.return_value = mock_session_instance
    mock_session_instance.execute.return_value.scalar_one.return_value = fake_poliza

    fake_schema = MagicMock()
    fake_schema.model_dump.return_value = {"numero_poliza": "POL-EXISTING"}
    mock_orm.return_value = fake_schema

    upload._run_extraction(job["job_id"], pdf_file, None, False)

    mock_ingest.assert_not_called()
    mock_extract.assert_not_called()
    result_job = upload._get_job(job["job_id"])
    assert result_job["status"] == "complete"
    assert result_job["result"] is not None


@patch("policy_extractor.storage.database.SessionLocal")
@patch("policy_extractor.storage.writer.orm_to_schema")
@patch("policy_extractor.storage.writer.upsert_policy")
@patch("policy_extractor.extraction.extract_policy")
@patch("policy_extractor.ingestion.ingest_pdf")
@patch("policy_extractor.cli_helpers.is_already_extracted", return_value=True)
@patch("policy_extractor.ingestion.cache.compute_file_hash", return_value="abc123")
def test_force_upload_reprocesses(
    mock_hash, mock_already, mock_ingest, mock_extract, mock_upsert, mock_orm, mock_session, tmp_path
):
    """When force=True, extraction runs even if hash already exists in DB."""
    from policy_extractor.api import upload

    pdf_file = tmp_path / "force.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test")
    job = upload._create_job("force.pdf")

    fake_extraction = MagicMock()
    fake_extraction.model_dump.return_value = {"numero_poliza": "POL-FORCED"}
    mock_extract.return_value = (fake_extraction, MagicMock(), 0)
    mock_session.return_value = MagicMock()

    upload._run_extraction(job["job_id"], pdf_file, None, True)

    mock_ingest.assert_called_once()
    # Verify force_reprocess=True was passed to ingest_pdf
    call_kwargs = mock_ingest.call_args
    assert call_kwargs.kwargs.get("force_reprocess") is True or (
        len(call_kwargs.args) >= 3 and call_kwargs.args[2] is True
    )


@patch("policy_extractor.storage.database.SessionLocal")
@patch("policy_extractor.storage.writer.orm_to_schema")
@patch("policy_extractor.storage.writer.upsert_policy")
@patch("policy_extractor.extraction.extract_policy")
@patch("policy_extractor.ingestion.ingest_pdf")
@patch("policy_extractor.cli_helpers.is_already_extracted", return_value=False)
@patch("policy_extractor.ingestion.cache.compute_file_hash", return_value="abc123")
def test_extraction_thread_creates_own_session(
    mock_hash, mock_already, mock_ingest, mock_extract, mock_upsert, mock_orm, mock_session, tmp_path
):
    """Verify SessionLocal() is called inside _run_extraction and session is closed."""
    from policy_extractor.api import upload

    pdf_file = tmp_path / "session_test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test")
    job = upload._create_job("session_test.pdf")

    fake_extraction = MagicMock()
    fake_extraction.model_dump.return_value = {"numero_poliza": "POL-SESSION"}
    mock_extract.return_value = (fake_extraction, MagicMock(), 0)
    mock_session_instance = MagicMock()
    mock_session.return_value = mock_session_instance

    upload._run_extraction(job["job_id"], pdf_file, None, False)

    # SessionLocal() must be called once inside _run_extraction
    mock_session.assert_called_once()
    # Session must be closed in the finally block
    mock_session_instance.close.assert_called_once()


# ---------------------------------------------------------------------------
# Evaluate query parameter tests (Phase 10 Plan 02)
# ---------------------------------------------------------------------------


@patch("policy_extractor.api.upload._run_extraction")
def test_upload_evaluate_param(mock_run):
    """POST /polizas/upload?evaluate=true passes evaluate=True to _run_extraction."""
    response = client.post(
        "/polizas/upload?evaluate=true",
        files={"file": ("test.pdf", io.BytesIO(_VALID_PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 202
    # Verify _run_extraction was called with evaluate=True as 5th positional arg
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    # evaluate is passed as 5th positional arg: (job_id, save_path, model, force, evaluate)
    assert call_args.args[4] is True, f"Expected evaluate=True, got args={call_args.args}"


@patch("policy_extractor.api.upload._run_extraction")
def test_upload_no_evaluate_by_default(mock_run):
    """POST /polizas/upload without evaluate param passes evaluate=False to _run_extraction."""
    response = client.post(
        "/polizas/upload",
        files={"file": ("test.pdf", io.BytesIO(_VALID_PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 202
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    # evaluate is passed as 5th positional arg defaulting to False
    assert call_args.args[4] is False, f"Expected evaluate=False, got args={call_args.args}"
