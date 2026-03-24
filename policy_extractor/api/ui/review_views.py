"""HITL review page routes — split-pane PDF viewer + inline field editing."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from policy_extractor.api import get_db
from policy_extractor.api.ui import templates
from policy_extractor.storage.models import Asegurado, Cobertura, Correction, Poliza

review_router = APIRouter()

# ---------------------------------------------------------------------------
# Field type constants
# ---------------------------------------------------------------------------

_NUMERIC_COLS: frozenset[str] = frozenset({"prima_total", "suma_asegurada", "deducible"})
_DATE_COLS: frozenset[str] = frozenset(
    {"fecha_emision", "inicio_vigencia", "fin_vigencia", "fecha_nacimiento"}
)
_NON_NULLABLE_COLS: frozenset[str] = frozenset(
    {"numero_poliza", "aseguradora", "tipo", "nombre_descripcion", "nombre_cobertura"}
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _coerce_value(col: str, raw_value: str):
    """Coerce a raw string value to the appropriate Python type for a column."""
    if raw_value == "":
        if col in _NON_NULLABLE_COLS:
            raise HTTPException(status_code=422, detail="Campo obligatorio")
        return None
    if col in _NUMERIC_COLS:
        try:
            return Decimal(raw_value)
        except InvalidOperation:
            raise HTTPException(status_code=422, detail="Valor numerico invalido")
    if col in _DATE_COLS:
        try:
            return date.fromisoformat(raw_value)
        except ValueError:
            raise HTTPException(status_code=422, detail="Fecha invalida (YYYY-MM-DD)")
    return raw_value


def _apply_field_update(db: Session, poliza: Poliza, field_path: str, raw_value: str):
    """Apply a field update identified by dot-notation field_path.

    Returns (old_value_str, new_value_str) for the correction log.
    Handles three namespaces:
    - Top-level poliza columns: "prima_total"
    - JSON bag: "campos_adicionales.key"
    - Nested rows: "asegurados.{id}.col" / "coberturas.{id}.col"
    """
    parts = field_path.split(".")

    if len(parts) == 1:
        # Top-level poliza column
        col = parts[0]
        old_raw = getattr(poliza, col, None)
        new_val = _coerce_value(col, raw_value)
        setattr(poliza, col, new_val)
        old_str = str(old_raw) if old_raw is not None else None
        return old_str, raw_value if raw_value != "" else None

    if parts[0] == "campos_adicionales" and len(parts) == 2:
        key = parts[1]
        current = dict(poliza.campos_adicionales or {})
        old_raw = current.get(key)
        current[key] = raw_value if raw_value != "" else None
        # Must reassign full dict for SQLAlchemy dirty-tracking (JSON column pitfall)
        poliza.campos_adicionales = current
        old_str = str(old_raw) if old_raw is not None else None
        return old_str, raw_value if raw_value != "" else None

    if parts[0] in ("asegurados", "coberturas") and len(parts) == 3:
        entity_type = parts[0]
        try:
            row_id = int(parts[1])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"ID invalido en campo: {field_path}")
        col = parts[2]
        if entity_type == "asegurados":
            obj = db.get(Asegurado, row_id)
        else:
            obj = db.get(Cobertura, row_id)
        if obj is None or obj.poliza_id != poliza.id:
            raise HTTPException(status_code=404, detail=f"Registro no encontrado: {field_path}")
        old_raw = getattr(obj, col, None)
        new_val = _coerce_value(col, raw_value)
        setattr(obj, col, new_val)
        old_str = str(old_raw) if old_raw is not None else None
        return old_str, raw_value if raw_value != "" else None

    raise HTTPException(status_code=400, detail=f"Campo desconocido: {field_path}")


def _field_label(field_path: str) -> str:
    """Return a human-readable label for a dot-notation field path."""
    last_segment = field_path.split(".")[-1]
    return last_segment.replace("_", " ").title()


def _input_type(field_path: str) -> str:
    """Return HTML input type based on the column name (last dot segment)."""
    col = field_path.split(".")[-1]
    if col in _NUMERIC_COLS:
        return "number"
    if col in _DATE_COLS:
        return "date"
    return "text"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@review_router.get("/ui/polizas/{poliza_id}/review", response_class=HTMLResponse)
def poliza_review(poliza_id: int, request: Request, db: Session = Depends(get_db)):
    """Split-pane review page: PDF iframe on left, editable fields on right."""
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

    # PDF must exist for the review page to be useful
    pdf_path = Path("data/pdfs") / f"{poliza_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF no disponible")

    # Build set of already-corrected field paths for indicator rendering
    corrected_fields = {c.field_path for c in poliza.corrections}

    def _field(fp: str, val) -> dict:
        return {
            "field_path": fp,
            "label": _field_label(fp),
            "value": str(val) if val is not None else "",
            "input_type": _input_type(fp),
            "is_corrected": fp in corrected_fields,
        }

    # Build field groups matching the detail page structure
    field_groups = []

    # General
    field_groups.append({
        "title": "Informacion General",
        "fields": [
            _field("numero_poliza", poliza.numero_poliza),
            _field("aseguradora", poliza.aseguradora),
            _field("tipo_seguro", poliza.tipo_seguro),
            _field("fecha_emision", poliza.fecha_emision),
        ],
    })

    # Vigencia
    field_groups.append({
        "title": "Vigencia",
        "fields": [
            _field("inicio_vigencia", poliza.inicio_vigencia),
            _field("fin_vigencia", poliza.fin_vigencia),
        ],
    })

    # Financiero
    field_groups.append({
        "title": "Financiero",
        "fields": [
            _field("prima_total", poliza.prima_total),
            _field("moneda", poliza.moneda),
            _field("forma_pago", poliza.forma_pago),
            _field("frecuencia_pago", poliza.frecuencia_pago),
        ],
    })

    # Personas
    field_groups.append({
        "title": "Personas",
        "fields": [
            _field("nombre_contratante", poliza.nombre_contratante),
            _field("nombre_agente", poliza.nombre_agente),
        ],
    })

    # Per-asegurado groups
    for aseg in poliza.asegurados:
        fields = [_field(f"asegurados.{aseg.id}.nombre_descripcion", aseg.nombre_descripcion)]
        fields.append(_field(f"asegurados.{aseg.id}.tipo", aseg.tipo))
        if aseg.rfc is not None:
            fields.append(_field(f"asegurados.{aseg.id}.rfc", aseg.rfc))
        if aseg.curp is not None:
            fields.append(_field(f"asegurados.{aseg.id}.curp", aseg.curp))
        if aseg.fecha_nacimiento is not None:
            fields.append(_field(f"asegurados.{aseg.id}.fecha_nacimiento", aseg.fecha_nacimiento))
        if aseg.parentesco is not None:
            fields.append(_field(f"asegurados.{aseg.id}.parentesco", aseg.parentesco))
        if aseg.direccion is not None:
            fields.append(_field(f"asegurados.{aseg.id}.direccion", aseg.direccion))
        field_groups.append({
            "title": f"Asegurado: {aseg.nombre_descripcion}",
            "fields": fields,
        })

    # Per-cobertura groups
    for cob in poliza.coberturas:
        fields = [_field(f"coberturas.{cob.id}.nombre_cobertura", cob.nombre_cobertura)]
        fields.append(_field(f"coberturas.{cob.id}.suma_asegurada", cob.suma_asegurada))
        fields.append(_field(f"coberturas.{cob.id}.deducible", cob.deducible))
        fields.append(_field(f"coberturas.{cob.id}.moneda", cob.moneda))
        field_groups.append({
            "title": f"Cobertura: {cob.nombre_cobertura}",
            "fields": fields,
        })

    # Campos adicionales (skip internal confianza key)
    if poliza.campos_adicionales:
        ca_fields = [
            _field(f"campos_adicionales.{k}", v)
            for k, v in poliza.campos_adicionales.items()
            if k != "confianza"
        ]
        if ca_fields:
            field_groups.append({"title": "Campos Adicionales", "fields": ca_fields})

    return templates.TemplateResponse(
        request=request,
        name="poliza_review.html",
        context={
            "poliza": poliza,
            "field_groups": field_groups,
            "corrections": poliza.corrections,
            "corrections_count": len(poliza.corrections),
        },
    )


@review_router.patch("/ui/polizas/{poliza_id}/review/field", response_class=HTMLResponse)
def patch_review_field(
    poliza_id: int,
    request: Request,
    field_path: str = Form(...),
    value: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """PATCH a single field — updates ORM row + logs correction in one transaction."""
    poliza = db.get(Poliza, poliza_id)
    if poliza is None:
        raise HTTPException(status_code=404, detail="Poliza no encontrada")

    old_value, new_value = _apply_field_update(db, poliza, field_path, value)

    # Only log if value actually changed
    response_headers = {}
    if old_value != new_value:
        correction = Correction(
            poliza_id=poliza_id,
            field_path=field_path,
            old_value=old_value,
            new_value=new_value,
            corrected_at=datetime.utcnow(),
        )
        db.add(correction)
        response_headers["HX-Trigger"] = "correctionSaved"

    db.commit()

    # Determine if field has any corrections in DB (post-commit count)
    is_corrected = bool(
        db.scalar(
            select(func.count(Correction.id)).where(
                Correction.poliza_id == poliza_id,
                Correction.field_path == field_path,
            )
        )
    )

    display_value = new_value if new_value is not None else ""

    return templates.TemplateResponse(
        request=request,
        name="partials/field_row.html",
        context={
            "poliza_id": poliza_id,
            "field_path": field_path,
            "label": _field_label(field_path),
            "value": display_value,
            "input_type": _input_type(field_path),
            "is_corrected": is_corrected,
        },
        headers=response_headers,
    )


@review_router.get("/ui/polizas/{poliza_id}/corrections-partial", response_class=HTMLResponse)
def corrections_partial(poliza_id: int, request: Request, db: Session = Depends(get_db)):
    """Return the correction history HTML fragment (for HTMX refresh)."""
    stmt = (
        select(Poliza)
        .options(selectinload(Poliza.corrections))
        .where(Poliza.id == poliza_id)
    )
    poliza = db.execute(stmt).scalar_one_or_none()
    if poliza is None:
        raise HTTPException(status_code=404, detail="Poliza no encontrada")

    return templates.TemplateResponse(
        request=request,
        name="partials/correction_history.html",
        context={
            "corrections": poliza.corrections,
            "corrections_count": len(poliza.corrections),
        },
    )
