"""Upload UI routes — batch workflow with HTMX polling."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from policy_extractor.api import get_db
from policy_extractor.api.ui import templates
from policy_extractor.storage.models import BatchJob, Poliza

upload_ui_router = APIRouter()

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "uploads"


@upload_ui_router.get("/subir", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="upload.html",
        context={"active_page": "upload"}
    )


@upload_ui_router.post("/ui/batch/upload", response_class=HTMLResponse)
def upload_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    batch_name: str = Form(""),
    model: str | None = Form(None),
    force: bool = Form(False),
    db: Session = Depends(get_db),
):
    # Validate at least one PDF
    pdf_files = [f for f in files if f.filename and f.filename.lower().endswith(".pdf")]
    if not pdf_files:
        raise HTTPException(status_code=400, detail="Se requiere al menos un archivo PDF")

    # Auto-generate batch name if empty (per D-08)
    if not batch_name.strip():
        batch_name = f"Lote {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # Create BatchJob row in DB
    batch_id = str(uuid.uuid4())
    batch = BatchJob(
        id=batch_id,
        batch_name=batch_name.strip(),
        status="processing",
        total_files=len(pdf_files),
        completed_files=0,
        failed_files=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.commit()

    # Save all PDF files to uploads/ directory
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_entries = []
    for f in pdf_files:
        dest = UPLOADS_DIR / f"{batch_id}_{f.filename}"
        with open(dest, "wb") as out:
            out.write(f.file.read())
        file_entries.append({"filename": f.filename, "pdf_path": str(dest)})

    # Spawn single background thread calling _run_batch_extraction
    from policy_extractor.api.upload import _run_batch_extraction
    thread = threading.Thread(
        target=_run_batch_extraction,
        args=(batch_id, file_entries, model, force),
        daemon=True,
    )
    thread.start()

    # Return batch_progress.html partial with batch_id for HTMX polling
    pct = 0
    return templates.TemplateResponse(
        request=request, name="partials/batch_progress.html",
        context={"batch": batch, "pct": pct, "active_page": "upload"}
    )


@upload_ui_router.get("/ui/batch/{batch_id}/status", response_class=HTMLResponse)
def batch_status(batch_id: str, request: Request, db: Session = Depends(get_db)):
    batch = db.get(BatchJob, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if batch.status in ("complete", "failed"):
        # Return summary partial, set HX-Trigger header to stop polling
        results = json.loads(batch.results_json) if batch.results_json else []
        resp = templates.TemplateResponse(
            request=request, name="partials/batch_summary.html",
            context={"batch": batch, "results": results, "active_page": "upload"}
        )
        resp.headers["HX-Trigger"] = "batchDone"
        return resp
    pct = int(batch.completed_files / max(batch.total_files, 1) * 100)
    return templates.TemplateResponse(
        request=request, name="partials/batch_progress.html",
        context={"batch": batch, "pct": pct, "active_page": "upload"}
    )


@upload_ui_router.get("/ui/batch/{batch_id}/export/{fmt}")
def batch_export(
    batch_id: str,
    fmt: str,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Export batch results as xlsx, csv, or json (D-05, D-09).

    Loads the BatchJob, extracts poliza_ids from results_json,
    queries full Poliza rows, and returns a FileResponse.
    """
    # Validate format
    if fmt not in ("xlsx", "csv", "json"):
        raise HTTPException(status_code=400, detail=f"Formato '{fmt}' no soportado. Use xlsx, csv, o json.")

    # Load BatchJob
    batch = db.get(BatchJob, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if batch.status != "complete":
        raise HTTPException(status_code=400, detail="El lote aun no ha terminado de procesarse")

    # Parse results_json to get poliza_ids
    results = json.loads(batch.results_json) if batch.results_json else []
    poliza_ids = [r["poliza_id"] for r in results if r.get("poliza_id") is not None]
    if not poliza_ids:
        raise HTTPException(status_code=404, detail="No hay polizas para exportar en este lote")

    # Query full Poliza rows with relationships
    stmt = (
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.id.in_(poliza_ids))
    )
    polizas = list(db.execute(stmt).scalars().all())
    if not polizas:
        raise HTTPException(status_code=404, detail="No se encontraron polizas para este lote")

    safe_name = (batch.batch_name or "lote").replace(" ", "_")[:50]

    # Handle JSON export (D-05)
    if fmt == "json":
        from policy_extractor.storage.writer import orm_to_schema
        data = [orm_to_schema(p).model_dump(mode="json") for p in polizas]
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.close()
        if background_tasks:
            background_tasks.add_task(os.unlink, tmp.name)
        return FileResponse(
            path=tmp.name,
            filename=f"{safe_name}.json",
            media_type="application/json",
        )

    # Handle xlsx/csv export
    tmp = tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False)
    tmp.close()
    if fmt == "xlsx":
        from policy_extractor.export import export_xlsx
        export_xlsx(polizas, Path(tmp.name))
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:  # csv
        from policy_extractor.export import export_csv
        export_csv(polizas, Path(tmp.name))
        media = "text/csv"

    if background_tasks:
        background_tasks.add_task(os.unlink, tmp.name)
    return FileResponse(
        path=tmp.name,
        filename=f"{safe_name}.{fmt}",
        media_type=media,
    )
