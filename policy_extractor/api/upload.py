"""PDF upload route with in-memory job store — Phase 8 Plan 01.

Provides:
- POST /polizas/upload  — Validate and queue a PDF for background extraction
- GET  /jobs/{job_id}   — Poll a single job by ID
- GET  /jobs            — List all active (non-expired) jobs

Job lifecycle: pending → processing → complete | failed
Expired jobs (1 h after terminal state) are purged on next read access.

Phase 14-02 additions:
- _run_batch_extraction: DB-backed batch worker for multi-file batch jobs
- _run_single_file_extraction: single-file helper with PDF retention
- PDFS_RETENTION_DIR: data/pdfs/{poliza_id}.pdf retention path
"""
from __future__ import annotations

import json
import shutil
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
PDFS_RETENTION_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pdfs"
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


def _run_extraction(job_id: str, pdf_path: Path, model: str | None, force: bool, evaluate: bool = False) -> None:
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
                result["evaluation_score"] = None
                result["evaluation_json"] = None
                _update_job(job_id, status="complete", result=result)
                # PDF retention — best-effort; failures do not fail the job
                try:
                    PDFS_RETENTION_DIR.mkdir(parents=True, exist_ok=True)
                    dest = PDFS_RETENTION_DIR / f"{poliza.id}.pdf"
                    shutil.copy2(str(pdf_path), str(dest))
                    pdf_path.unlink(missing_ok=True)
                except Exception:
                    pdf_path.unlink(missing_ok=True)
                return

            ingestion_result = ingest_pdf(pdf_path, session=session, force_reprocess=force)
            policy, _usage, _retries = extract_policy(ingestion_result, model=model)
            if policy is None:
                raise RuntimeError("Extraction returned None")
            poliza = upsert_policy(session, policy)
            result = policy.model_dump(mode="json")

            if evaluate:
                from policy_extractor.evaluation import evaluate_policy
                from policy_extractor.storage.writer import update_evaluation_columns
                eval_result = evaluate_policy(ingestion_result, policy)
                if eval_result is not None:
                    update_evaluation_columns(
                        session, policy.numero_poliza, policy.aseguradora,
                        eval_result.score, eval_result.evaluation_json,
                        eval_result.evaluated_at, eval_result.model_id,
                    )
                    result["evaluation_score"] = eval_result.score
                    result["evaluation_json"] = eval_result.evaluation_json
                else:
                    result["evaluation_score"] = None
                    result["evaluation_json"] = None
            else:
                result["evaluation_score"] = None
                result["evaluation_json"] = None

            _update_job(job_id, status="complete", result=result)
            # PDF retention — best-effort; failures do not fail the job
            try:
                PDFS_RETENTION_DIR.mkdir(parents=True, exist_ok=True)
                dest_path = PDFS_RETENTION_DIR / f"{poliza.id}.pdf"
                shutil.copy2(str(pdf_path), str(dest_path))
                pdf_path.unlink(missing_ok=True)
            except Exception:
                pdf_path.unlink(missing_ok=True)
        except Exception as exc:
            _update_job(job_id, status="failed", error=str(exc))
            # PDF kept on failure for debugging
        finally:
            session.close()
    except Exception as exc:
        _update_job(job_id, status="failed", error=str(exc))


# ---------------------------------------------------------------------------
# Batch extraction worker (Phase 14-02)
# ---------------------------------------------------------------------------


def _run_single_file_extraction(session, pdf_path: Path, model: str | None, force: bool) -> tuple[str, dict]:
    """Run the extraction pipeline for a single PDF file.

    Returns (status, summary_dict) where:
    - status: "complete" or "failed"
    - summary_dict: {"poliza_id", "numero_poliza", "aseguradora"} on success
                    {"error": str} on failure

    PDF retention: copies to data/pdfs/{poliza_id}.pdf then removes the temp upload.
    """
    try:
        from policy_extractor.ingestion.cache import compute_file_hash
        from policy_extractor.cli_helpers import is_already_extracted
        from policy_extractor.ingestion import ingest_pdf
        from policy_extractor.extraction import extract_policy
        from policy_extractor.storage.writer import upsert_policy, orm_to_schema
        from policy_extractor.storage.models import Poliza
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        file_hash = compute_file_hash(pdf_path)
        if not force and is_already_extracted(session, file_hash):
            poliza = session.execute(
                select(Poliza)
                .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
                .where(Poliza.source_file_hash == file_hash)
            ).scalar_one()
            # PDF retention (UI-06, D-25)
            PDFS_RETENTION_DIR.mkdir(parents=True, exist_ok=True)
            dest = PDFS_RETENTION_DIR / f"{poliza.id}.pdf"
            shutil.copy2(str(pdf_path), str(dest))
            pdf_path.unlink(missing_ok=True)
            return ("complete", {
                "poliza_id": poliza.id,
                "numero_poliza": poliza.numero_poliza,
                "aseguradora": poliza.aseguradora,
            })

        ingestion_result = ingest_pdf(pdf_path, session=session, force_reprocess=force)
        policy, _usage, _retries = extract_policy(ingestion_result, model=model)
        if policy is None:
            raise RuntimeError("Extraction returned None")
        poliza = upsert_policy(session, policy)

        # PDF retention (UI-06, D-25): copy to permanent location then remove temp
        PDFS_RETENTION_DIR.mkdir(parents=True, exist_ok=True)
        dest = PDFS_RETENTION_DIR / f"{poliza.id}.pdf"
        shutil.copy2(str(pdf_path), str(dest))
        pdf_path.unlink(missing_ok=True)

        return ("complete", {
            "poliza_id": poliza.id,
            "numero_poliza": policy.numero_poliza,
            "aseguradora": policy.aseguradora,
        })
    except Exception as exc:
        return ("failed", {"error": str(exc)})


def _run_batch_extraction(batch_id: str, file_entries: list[dict], model: str | None, force: bool) -> None:
    """Background batch extraction worker with DB-backed progress tracking.

    Per D-06: failed files do NOT stop remaining files from processing.
    Updates BatchJob.completed_files and failed_files atomically after each file.
    Stores per-file summaries in results_json on completion.

    Args:
        batch_id: UUID string matching BatchJob.id
        file_entries: list of {"filename": str, "pdf_path": str} dicts
        model: optional model override
        force: whether to force re-extraction of already-extracted files
    """
    from policy_extractor.storage.database import SessionLocal
    from policy_extractor.storage.models import BatchJob
    from sqlalchemy import update

    session = SessionLocal()
    summaries = []
    try:
        for entry in file_entries:
            pdf_path = Path(entry["pdf_path"])
            filename = entry["filename"]

            status, result = _run_single_file_extraction(session, pdf_path, model, force)

            summary = {
                "filename": filename,
                "status": status,
                "poliza_id": result.get("poliza_id"),
                "numero_poliza": result.get("numero_poliza"),
                "aseguradora": result.get("aseguradora"),
                "error": result.get("error"),
            }
            summaries.append(summary)

            # Atomic update per Pitfall 5 — avoids read-modify-write races
            if status == "complete":
                session.execute(
                    update(BatchJob)
                    .where(BatchJob.id == batch_id)
                    .values(completed_files=BatchJob.completed_files + 1)
                )
            else:
                session.execute(
                    update(BatchJob)
                    .where(BatchJob.id == batch_id)
                    .values(failed_files=BatchJob.failed_files + 1)
                )
            session.commit()

        # Mark batch complete with all results
        from datetime import datetime, timezone
        session.execute(
            update(BatchJob)
            .where(BatchJob.id == batch_id)
            .values(
                status="complete",
                completed_at=datetime.now(timezone.utc),
                results_json=json.dumps(summaries),
            )
        )
        session.commit()
    except Exception:
        # Batch-level failure — mark as failed but preserve any partial results
        try:
            from datetime import datetime, timezone
            session.execute(
                update(BatchJob)
                .where(BatchJob.id == batch_id)
                .values(
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    results_json=json.dumps(summaries) if summaries else None,
                )
            )
            session.commit()
        except Exception:
            pass
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/polizas/upload", status_code=202)
async def upload_pdf(
    file: UploadFile = File(...),
    model: str | None = Query(None, description="Override extraction model"),
    force: bool = Query(False, description="Reprocess even if already extracted"),
    evaluate: bool = Query(False, description="Run Sonnet quality evaluation after extraction"),
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
        args=(job["job_id"], save_path, model, force, evaluate),
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
