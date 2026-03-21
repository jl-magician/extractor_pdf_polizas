"""Poliza list and detail UI routes."""
from __future__ import annotations
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from policy_extractor.api import get_db
from policy_extractor.api.ui import templates
from policy_extractor.config import settings
from policy_extractor.storage.models import Poliza

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


@poliza_ui_router.get("/ui/polizas/{poliza_id}", response_class=HTMLResponse)
def poliza_detail(poliza_id: int, request: Request, db: Session = Depends(get_db)):
    stmt = (
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
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

    return templates.TemplateResponse(
        request=request, name="poliza_detail.html",
        context={
            "active_page": "polizas",
            "poliza": poliza,
            "has_pdf": has_pdf,
            "warnings": warnings,
        }
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
