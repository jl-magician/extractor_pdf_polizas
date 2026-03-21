"""FastAPI REST API for poliza-extractor — Phase 5 Plan 02.

Provides full CRUD for insurance policies with filtering and pagination.

Exports:
    app     — FastAPI application instance
    get_db  — SQLAlchemy session dependency (overridable in tests)
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Generator, Optional
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from policy_extractor.config import settings
from policy_extractor.schemas.poliza import PolicyExtraction
from policy_extractor.storage.database import SessionLocal, init_db
from policy_extractor.storage.models import Asegurado, Cobertura, Poliza
from policy_extractor.storage.writer import orm_to_schema, upsert_policy

# ---------------------------------------------------------------------------
# Static and templates directories
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Poliza Extractor API",
    version="1.0.0",
    description="REST API for querying and managing extracted insurance policy data.",
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Shared templates instance
from policy_extractor.api.ui import templates  # noqa: E402


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
def on_startup() -> None:
    """Initialise the database on application startup."""
    engine = init_db(settings.DB_PATH)
    SessionLocal.configure(bind=engine)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# DB dependency
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session. Override this in tests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbDep = Annotated[Session, Depends(get_db)]

# ---------------------------------------------------------------------------
# Scalar fields to update on PUT (mirrors writer._SCALAR_FIELDS)
# ---------------------------------------------------------------------------

_SCALAR_FIELDS = [
    "tipo_seguro",
    "fecha_emision",
    "inicio_vigencia",
    "fin_vigencia",
    "nombre_contratante",
    "nombre_agente",
    "prima_total",
    "moneda",
    "forma_pago",
    "frecuencia_pago",
    "source_file_hash",
    "model_id",
    "prompt_version",
    "extracted_at",
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/polizas")
def list_polizas(
    db: DbDep,
    aseguradora: Optional[str] = Query(None, description="Filter by insurer name"),
    tipo_seguro: Optional[str] = Query(None, description="Filter by insurance type"),
    nombre_agente: Optional[str] = Query(None, description="Filter by agent name"),
    desde: Optional[date] = Query(None, description="Filter: inicio_vigencia >= desde"),
    hasta: Optional[date] = Query(None, description="Filter: fin_vigencia <= hasta"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Maximum records to return"),
) -> JSONResponse:
    """Return a JSON array of policies matching the given filters."""
    stmt = (
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
    )
    if aseguradora is not None:
        stmt = stmt.where(Poliza.aseguradora == aseguradora)
    if tipo_seguro is not None:
        stmt = stmt.where(Poliza.tipo_seguro == tipo_seguro)
    if nombre_agente is not None:
        stmt = stmt.where(Poliza.nombre_agente == nombre_agente)
    if desde is not None:
        stmt = stmt.where(Poliza.inicio_vigencia >= desde)
    if hasta is not None:
        stmt = stmt.where(Poliza.fin_vigencia <= hasta)

    stmt = stmt.offset(skip).limit(limit)
    rows = db.execute(stmt).scalars().all()
    data = [orm_to_schema(p).model_dump(mode="json") for p in rows]
    return JSONResponse(content=data)


@app.get("/polizas/{poliza_id}")
def get_poliza(poliza_id: int, db: DbDep) -> JSONResponse:
    """Return a single policy by ID. Returns 404 if not found."""
    stmt = (
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.id == poliza_id)
    )
    poliza = db.execute(stmt).scalar_one_or_none()
    if poliza is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return JSONResponse(content=orm_to_schema(poliza).model_dump(mode="json"))


@app.post("/polizas", status_code=201)
def create_poliza(extraction: PolicyExtraction, db: DbDep) -> JSONResponse:
    """Create a new policy from a PolicyExtraction JSON body. Returns 201."""
    poliza = upsert_policy(db, extraction)
    # Reload with relationships for response
    stmt = (
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.id == poliza.id)
    )
    poliza = db.execute(stmt).scalar_one()
    return JSONResponse(
        content=orm_to_schema(poliza).model_dump(mode="json"),
        status_code=201,
    )


@app.put("/polizas/{poliza_id}")
def update_poliza(poliza_id: int, extraction: PolicyExtraction, db: DbDep) -> JSONResponse:
    """Update an existing policy by ID. Returns 404 if not found."""
    # Verify the policy exists
    poliza = db.get(Poliza, poliza_id)
    if poliza is None:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Clear old children
    poliza.asegurados.clear()
    poliza.coberturas.clear()
    db.flush()

    # Update scalar fields
    for field in _SCALAR_FIELDS:
        setattr(poliza, field, getattr(extraction, field))

    # Update numero_poliza and aseguradora
    poliza.numero_poliza = extraction.numero_poliza
    poliza.aseguradora = extraction.aseguradora

    # Store confianza inside campos_adicionales
    merged = dict(extraction.campos_adicionales)
    merged["confianza"] = extraction.confianza
    poliza.campos_adicionales = merged

    # Rebuild children
    for aseg_ext in extraction.asegurados:
        poliza.asegurados.append(
            Asegurado(
                tipo=aseg_ext.tipo,
                nombre_descripcion=aseg_ext.nombre_descripcion,
                fecha_nacimiento=aseg_ext.fecha_nacimiento,
                rfc=aseg_ext.rfc,
                curp=aseg_ext.curp,
                direccion=aseg_ext.direccion,
                parentesco=aseg_ext.parentesco,
                campos_adicionales=aseg_ext.campos_adicionales or None,
            )
        )
    for cob_ext in extraction.coberturas:
        poliza.coberturas.append(
            Cobertura(
                nombre_cobertura=cob_ext.nombre_cobertura,
                suma_asegurada=cob_ext.suma_asegurada,
                deducible=cob_ext.deducible,
                moneda=cob_ext.moneda,
                campos_adicionales=cob_ext.campos_adicionales or None,
            )
        )

    db.commit()

    # Reload with relationships
    stmt = (
        select(Poliza)
        .options(selectinload(Poliza.asegurados), selectinload(Poliza.coberturas))
        .where(Poliza.id == poliza_id)
    )
    poliza = db.execute(stmt).scalar_one()
    return JSONResponse(content=orm_to_schema(poliza).model_dump(mode="json"))


@app.delete("/polizas/{poliza_id}")
def delete_poliza(poliza_id: int, db: DbDep) -> JSONResponse:
    """Delete a policy and its children by ID. Returns 404 if not found."""
    poliza = db.get(Poliza, poliza_id)
    if poliza is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete(poliza)
    db.commit()
    return JSONResponse(content={"detail": "Policy deleted"})


# ---------------------------------------------------------------------------
# Upload router (Phase 8)
# ---------------------------------------------------------------------------

from policy_extractor.api.upload import router as upload_router, UPLOADS_DIR  # noqa: E402

app.include_router(upload_router)

from policy_extractor.api.ui.poliza_views import poliza_ui_router  # noqa: E402
from policy_extractor.api.ui.upload_views import upload_ui_router  # noqa: E402
from policy_extractor.api.ui.dashboard_views import dashboard_router  # noqa: E402

app.include_router(poliza_ui_router)
app.include_router(upload_ui_router)
app.include_router(dashboard_router)
