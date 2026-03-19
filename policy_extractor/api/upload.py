"""PDF upload route with in-memory job store — Phase 8 Plan 01.

Provides:
- POST /polizas/upload  — Validate and queue a PDF for background extraction
- GET  /jobs/{job_id}   — Poll a single job by ID
- GET  /jobs            — List all active (non-expired) jobs

Job lifecycle: pending → processing → complete | failed
Expired jobs (1 h after terminal state) are purged on next read access.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
JOB_EXPIRY_HOURS = 1
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

_job_store: dict[str, dict] = {}
_store_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Job store helpers
# ---------------------------------------------------------------------------


def _create_job(filename: str) -> dict:
    """Create a new job entry in the store and return it."""
    job_id = str(uuid.uuid4())
    job: dict = {
        "job_id": job_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "result": None,
        "error": None,
        "expires_at": None,
    }
    with _store_lock:
        _job_store[job_id] = job
    return dict(job)


def _update_job(job_id: str, **fields) -> None:
    """Update fields on an existing job. Sets expires_at on terminal states."""
    with _store_lock:
        if job_id not in _job_store:
            return
        _job_store[job_id].update(fields)
        status = _job_store[job_id].get("status")
        if status in ("complete", "failed"):
            _job_store[job_id]["expires_at"] = (
                datetime.now(timezone.utc) + timedelta(hours=JOB_EXPIRY_HOURS)
            ).isoformat()


def _purge_expired() -> None:
    """Remove jobs whose expires_at timestamp has passed. Must be called under lock."""
    now = datetime.now(timezone.utc)
    expired_ids = [
        job_id
        for job_id, job in _job_store.items()
        if job.get("expires_at") is not None
        and datetime.fromisoformat(job["expires_at"]) < now
    ]
    for job_id in expired_ids:
        del _job_store[job_id]


def _get_job(job_id: str) -> dict | None:
    """Return a copy of the job dict, or None if not found / expired."""
    with _store_lock:
        _purge_expired()
        job = _job_store.get(job_id)
        return dict(job) if job is not None else None


def _list_jobs() -> list[dict]:
    """Return copies of all non-expired jobs."""
    with _store_lock:
        _purge_expired()
        return [dict(j) for j in _job_store.values()]


# ---------------------------------------------------------------------------
# Background extraction worker
# ---------------------------------------------------------------------------


def _run_extraction(job_id: str, pdf_path: Path, model: str | None, force: bool) -> None:
    """Background extraction worker. Full pipeline wired in Plan 02."""
    _update_job(job_id, status="processing")
    try:
        from policy_extractor.storage.database import SessionLocal
        from policy_extractor.ingestion.cache import compute_file_hash
        from policy_extractor.cli_helpers import is_already_extracted
        from policy_extractor.ingestion import ingest_pdf
        from policy_extractor.extraction import extract_policy
        from policy_extractor.storage.writer import upsert_policy, orm_to_schema
        from policy_extractor.storage.models import Poliza
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        session = SessionLocal()
        try:
            file_hash = compute_file_hash(pdf_path)
            if not force and is_already_extracted(session, file_hash):
                poliza = session.execute(
                    select(Poliza)
                    .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
                    .where(Poliza.source_file_hash == file_hash)
                ).scalar_one()
                result = orm_to_schema(poliza).model_dump(mode="json")
                _update_job(job_id, status="complete", result=result)
                pdf_path.unlink(missing_ok=True)
                return

            ingestion_result = ingest_pdf(pdf_path, session=session, force_reprocess=force)
            policy, _ = extract_policy(ingestion_result, model=model)
            if policy is None:
                raise RuntimeError("Extraction returned None")
            upsert_policy(session, policy)
            result = policy.model_dump(mode="json")
            _update_job(job_id, status="complete", result=result)
            pdf_path.unlink(missing_ok=True)
        except Exception as exc:
            _update_job(job_id, status="failed", error=str(exc))
            # PDF kept on failure for debugging
        finally:
            session.close()
    except Exception as exc:
        _update_job(job_id, status="failed", error=str(exc))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/polizas/upload", status_code=202)
async def upload_pdf(
    file: UploadFile = File(...),
    model: str | None = Query(None, description="Override extraction model"),
    force: bool = Query(False, description="Reprocess even if already extracted"),
) -> JSONResponse:
    """Accept a PDF upload, validate it, create a job, and dispatch background extraction."""
    contents = await file.read()

    # Validate extension
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="File must have .pdf extension")

    # Validate magic bytes
    if not contents[:4] == b"%PDF":
        raise HTTPException(status_code=422, detail="File is not a valid PDF")

    # Validate size
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")

    job = _create_job(filename=file.filename or "upload.pdf")
    save_path = UPLOADS_DIR / f"{job['job_id']}.pdf"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(contents)

    t = threading.Thread(
        target=_run_extraction,
        args=(job["job_id"], save_path, model, force),
        daemon=True,
        name=f"extract-{job['job_id'][:8]}",
    )
    t.start()

    return JSONResponse(content=job, status_code=202)


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> JSONResponse:
    """Return the job status dict for a given job_id. 404 if not found or expired."""
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=job)


@router.get("/jobs")
def list_jobs() -> JSONResponse:
    """Return all active (non-expired) jobs."""
    return JSONResponse(content=_list_jobs())
