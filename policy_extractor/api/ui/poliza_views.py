"""Poliza list and detail UI routes."""
from __future__ import annotations
import asyncio
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from policy_extractor.api import get_db
from policy_extractor.api.ui import templates
from policy_extractor.config import settings
from policy_extractor.storage.models import Correction, Poliza

poliza_ui_router = APIRouter()
PAGE_SIZE = 25


@poliza_ui_router.get("/ui/polizas", response_class=HTMLResponse)
def poliza_list(
    request: Request,
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None),
    aseguradora: Optional[str] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
):
    # Build query with filters
    stmt = select(Poliza).options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))

    if q:
        like_q = f"%{q}%"
        stmt = stmt.where(or_(
            Poliza.numero_poliza.ilike(like_q),
            Poliza.nombre_contratante.ilike(like_q),
            Poliza.aseguradora.ilike(like_q),
        ))
    if aseguradora:
        stmt = stmt.where(Poliza.aseguradora == aseguradora)
    if desde:
        stmt = stmt.where(Poliza.inicio_vigencia >= desde)
    if hasta:
        stmt = stmt.where(Poliza.fin_vigencia <= hasta)

    stmt = stmt.order_by(Poliza.id.desc()).offset(skip).limit(PAGE_SIZE + 1)
    rows = db.execute(stmt).scalars().all()
    has_more = len(rows) > PAGE_SIZE
    polizas = list(rows[:PAGE_SIZE])

    # Summary bar stats (D-11): total processed, total warnings, needs review count
    total_count = db.scalar(select(func.count(Poliza.id)))
    warning_count = db.scalar(
        select(func.count(Poliza.id)).where(Poliza.validation_warnings.is_not(None))
    )
    review_count = db.scalar(
        select(func.count(Poliza.id)).where(
            or_(
                Poliza.evaluation_score < settings.REVIEW_SCORE_THRESHOLD,
                Poliza.validation_warnings.is_not(None),
            )
        )
    )

    # Get distinct aseguradoras for filter dropdown
    aseguradoras = [r[0] for r in db.execute(
        select(Poliza.aseguradora).distinct().order_by(Poliza.aseguradora)
    ).all()]

    # If HTMX request (search/load-more), return only rows partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="partials/poliza_rows.html",
            context={
                "polizas": polizas, "has_more": has_more,
                "next_skip": skip + PAGE_SIZE,
                "q": q, "aseguradora": aseguradora, "desde": desde, "hasta": hasta,
            }
        )

    return templates.TemplateResponse(
        request=request, name="poliza_list.html",
        context={
            "active_page": "polizas",
            "polizas": polizas, "has_more": has_more,
            "next_skip": PAGE_SIZE,
            "total_count": total_count or 0,
            "warning_count": warning_count or 0,
            "review_count": review_count or 0,
            "aseguradoras": aseguradoras,
            "q": q or "", "aseguradora_filter": aseguradora or "",
            "desde": desde, "hasta": hasta,
        }
    )


@poliza_ui_router.get("/ui/reglas", response_class=HTMLResponse)
def extraction_rules_page(request: Request):
    """Show all learned extraction rules."""
    from policy_extractor.extraction.rules import load_rules
    rules = load_rules()
    return templates.TemplateResponse(
        request=request, name="extraction_rules.html",
        context={"active_page": "reglas", "rules": rules},
    )


@poliza_ui_router.post("/ui/reglas/{rule_id}/delete")
def delete_extraction_rule(rule_id: int):
    """Delete a single extraction rule."""
    from policy_extractor.extraction.rules import remove_rule
    remove_rule(rule_id)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui/reglas", status_code=303)


@poliza_ui_router.post("/ui/polizas/evaluate-all")
def evaluate_all(request: Request, db: Session = Depends(get_db)):
    """Evaluate all unevaluated polizas that have a retained PDF."""
    unevaluated = db.execute(
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.evaluation_score.is_(None))
    ).scalars().all()

    from policy_extractor.ingestion import ingest_pdf
    from policy_extractor.evaluation import evaluate_policy, build_swap_warnings
    from policy_extractor.storage.writer import orm_to_schema, update_evaluation_columns

    for poliza in unevaluated:
        pdf_path = Path("data/pdfs") / f"{poliza.id}.pdf"
        if not pdf_path.exists():
            continue

        ingestion_result = ingest_pdf(pdf_path, session=db, force_reprocess=False)
        policy_schema = orm_to_schema(poliza)
        eval_result = evaluate_policy(ingestion_result, policy_schema)

        if eval_result is not None:
            update_evaluation_columns(
                db, poliza.numero_poliza, poliza.aseguradora,
                eval_result.score, eval_result.evaluation_json,
                eval_result.evaluated_at, eval_result.model_id,
            )
            swap_warnings = build_swap_warnings(eval_result.evaluation_json)
            if swap_warnings:
                existing = poliza.validation_warnings or []
                poliza.validation_warnings = existing + swap_warnings
                db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui/polizas", status_code=303)


@poliza_ui_router.get("/ui/polizas/{poliza_id}", response_class=HTMLResponse)
def poliza_detail(poliza_id: int, request: Request, db: Session = Depends(get_db)):
    stmt = (
        select(Poliza)
        .options(
            selectinload(Poliza.asegurados),
            selectinload(Poliza.coberturas),
            selectinload(Poliza.corrections),
        )
        .where(Poliza.id == poliza_id)
    )
    poliza = db.execute(stmt).scalar_one_or_none()
    if poliza is None:
        raise HTTPException(status_code=404, detail="Poliza no encontrada")

    # Check if PDF exists for viewer link
    pdf_path = Path("data/pdfs") / f"{poliza.id}.pdf"
    has_pdf = pdf_path.exists()

    # Parse validation_warnings for display
    warnings = poliza.validation_warnings or []

    # Parse evaluation details and extract flagged field names
    eval_details = None
    flagged_fields = {}
    if poliza.evaluation_json:
        try:
            eval_details = json.loads(poliza.evaluation_json)
            for flag in eval_details.get("flags", []):
                flagged_fields[flag["field"]] = flag["issue"]
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    return templates.TemplateResponse(
        request=request, name="poliza_detail.html",
        context={
            "active_page": "polizas",
            "poliza": poliza,
            "has_pdf": has_pdf,
            "warnings": warnings,
            "eval_details": eval_details,
            "flagged_fields": flagged_fields,
            "corrections": poliza.corrections or [],
        }
    )


@poliza_ui_router.get("/ui/polizas/{poliza_id}/report")
async def poliza_report(poliza_id: int, db: Session = Depends(get_db)):
    """Generate and download a PDF report for a poliza (per D-02: on-the-fly, no caching)."""
    poliza = db.execute(
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.id == poliza_id)
    ).scalar_one_or_none()
    if poliza is None:
        raise HTTPException(status_code=404, detail="Poliza not found")

    from policy_extractor.reports import generate_poliza_report

    loop = asyncio.get_event_loop()
    pdf_bytes = await loop.run_in_executor(None, generate_poliza_report, poliza)

    # Per D-06: filename format poliza_{numero}_{aseguradora}.pdf
    safe_numero = (poliza.numero_poliza or "sin_numero").replace("/", "_").replace("\\", "_")
    safe_aseg = (poliza.aseguradora or "desconocida").lower().replace(" ", "_")
    filename = f"poliza_{safe_numero}_{safe_aseg}.pdf"

    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@poliza_ui_router.get("/ui/polizas/{poliza_id}/export/{fmt}")
def poliza_export(
    poliza_id: int, fmt: str,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    # fmt must be xlsx, csv, or json
    if fmt not in ("xlsx", "csv", "json"):
        raise HTTPException(status_code=400, detail="Formato no soportado")

    stmt = (
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.id == poliza_id)
    )
    poliza = db.execute(stmt).scalar_one_or_none()
    if poliza is None:
        raise HTTPException(status_code=404)

    if fmt == "json":
        from policy_extractor.storage.writer import orm_to_schema
        data = orm_to_schema(poliza).model_dump(mode="json")
        # Return as downloadable JSON file
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.close()
        background_tasks.add_task(os.unlink, tmp.name)
        return FileResponse(
            path=tmp.name,
            filename=f"poliza_{poliza.numero_poliza}.json",
            media_type="application/json",
        )

    tmp = tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False)
    tmp.close()
    if fmt == "xlsx":
        from policy_extractor.export import export_xlsx
        export_xlsx([poliza], Path(tmp.name))
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        from policy_extractor.export import export_csv
        export_csv([poliza], Path(tmp.name))
        media = "text/csv"
    background_tasks.add_task(os.unlink, tmp.name)
    return FileResponse(
        path=tmp.name,
        filename=f"poliza_{poliza.numero_poliza}.{fmt}",
        media_type=media,
    )


@poliza_ui_router.post("/ui/polizas/{poliza_id}/evaluate")
def evaluate_single(poliza_id: int, request: Request, db: Session = Depends(get_db)):
    """Evaluate a single poliza using Sonnet and redirect back to detail page."""
    poliza = db.execute(
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.id == poliza_id)
    ).scalar_one_or_none()
    if poliza is None:
        raise HTTPException(status_code=404, detail="Poliza no encontrada")

    pdf_path = Path("data/pdfs") / f"{poliza.id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=400, detail="PDF no disponible para evaluar")

    from policy_extractor.ingestion import ingest_pdf
    from policy_extractor.evaluation import evaluate_policy, build_swap_warnings
    from policy_extractor.storage.writer import orm_to_schema, update_evaluation_columns

    ingestion_result = ingest_pdf(pdf_path, session=db, force_reprocess=False)
    policy_schema = orm_to_schema(poliza)

    eval_result = evaluate_policy(ingestion_result, policy_schema)
    if eval_result is not None:
        update_evaluation_columns(
            db, poliza.numero_poliza, poliza.aseguradora,
            eval_result.score, eval_result.evaluation_json,
            eval_result.evaluated_at, eval_result.model_id,
        )
        swap_warnings = build_swap_warnings(eval_result.evaluation_json)
        if swap_warnings:
            existing = poliza.validation_warnings or []
            poliza.validation_warnings = existing + swap_warnings
            db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/ui/polizas/{poliza_id}", status_code=303)


@poliza_ui_router.post("/ui/polizas/{poliza_id}/re-extract")
async def re_extract_with_improvements(
    poliza_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Re-extract a poliza with additional instructions from selected evaluation flags."""
    form_data = await request.form()
    flags = form_data.getlist("flags")

    poliza = db.execute(
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.id == poliza_id)
    ).scalar_one_or_none()
    if poliza is None:
        raise HTTPException(status_code=404, detail="Poliza no encontrada")

    pdf_path = Path("data/pdfs") / f"{poliza.id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=400, detail="PDF no disponible")

    # Parse flags: each is "field:::issue"
    corrections = []
    for flag in flags:
        parts = flag.split(":::", 1)
        if len(parts) == 2:
            corrections.append({"field": parts[0], "issue": parts[1]})

    if not corrections:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/ui/polizas/{poliza_id}", status_code=303)

    # Save corrections as permanent extraction rules
    from policy_extractor.extraction.rules import add_rule
    for c in corrections:
        add_rule(
            field=c["field"],
            instruction=c["issue"],
            source_poliza=poliza.numero_poliza,
        )

    # Re-extract with the rules now baked into the system prompt
    from policy_extractor.ingestion import ingest_pdf
    from policy_extractor.extraction import extract_policy
    from policy_extractor.storage.writer import upsert_policy

    ingestion_result = ingest_pdf(pdf_path, session=db, force_reprocess=False)

    try:
        policy, _usage, _retries = extract_policy(ingestion_result)
        if policy is None:
            raise RuntimeError("Re-extraction returned None")
        upsert_policy(db, policy)

        # Clear old evaluation since extraction changed
        poliza = db.execute(
            select(Poliza).where(Poliza.id == poliza_id)
        ).scalar_one_or_none()
        if poliza:
            poliza.evaluation_score = None
            poliza.evaluation_json = None
            poliza.evaluated_at = None
            db.commit()
    except Exception:
        pass  # Fall through to redirect; old data preserved

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/ui/polizas/{poliza_id}", status_code=303)


@poliza_ui_router.get("/ui/polizas/{poliza_id}/pdf")
def poliza_pdf(poliza_id: int, db: Session = Depends(get_db)):
    """Serve the retained PDF for iframe viewing."""
    poliza = db.get(Poliza, poliza_id)
    if poliza is None:
        raise HTTPException(status_code=404)
    pdf_path = Path("data/pdfs") / f"{poliza_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF no disponible")
    return FileResponse(path=str(pdf_path), media_type="application/pdf")
