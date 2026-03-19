"""Persistence writer — maps PolicyExtraction Pydantic models to ORM rows and back.

Exports:
    upsert_policy(session, extraction) -> Poliza
    orm_to_schema(poliza) -> PolicyExtraction
    update_evaluation_columns(session, numero_poliza, aseguradora, score, evaluation_json, evaluated_at, model_id) -> None
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session


def _json_safe(obj: dict) -> dict:
    """Convert a dict to JSON-safe types (handles datetime, date, Decimal)."""
    return json.loads(json.dumps(obj, default=_json_serializer))


def _json_serializer(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

from policy_extractor.schemas.asegurado import AseguradoExtraction
from policy_extractor.schemas.cobertura import CoberturaExtraction
from policy_extractor.schemas.poliza import PolicyExtraction
from policy_extractor.storage.models import Asegurado, Cobertura, Poliza

# Scalar fields to copy directly between PolicyExtraction and Poliza (same names).
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


def upsert_policy(session: Session, extraction: PolicyExtraction) -> Poliza:
    """Insert or update a Poliza row from a PolicyExtraction.

    Deduplicates by (numero_poliza, aseguradora). On update, all child
    asegurados and coberturas are replaced (not merged) to keep data consistent.

    Args:
        session: Active SQLAlchemy session (caller owns the lifecycle).
        extraction: Validated PolicyExtraction Pydantic model.

    Returns:
        The persisted Poliza ORM row (committed, ID populated).
    """
    # Dedup query
    poliza = (
        session.query(Poliza)
        .filter_by(numero_poliza=extraction.numero_poliza, aseguradora=extraction.aseguradora)
        .first()
    )

    if poliza is not None:
        # Clear old children so cascade delete-orphan removes them
        poliza.asegurados.clear()
        poliza.coberturas.clear()
        session.flush()
    else:
        poliza = Poliza(
            numero_poliza=extraction.numero_poliza,
            aseguradora=extraction.aseguradora,
        )
        session.add(poliza)

    # Copy scalar fields
    for field in _SCALAR_FIELDS:
        setattr(poliza, field, getattr(extraction, field))

    # Store campos_adicionales merged with confianza (STOR-01: confianza stored in DB)
    # Convert to JSON-safe types (datetime, Decimal in _raw_response)
    merged = dict(extraction.campos_adicionales)
    merged["confianza"] = extraction.confianza
    poliza.campos_adicionales = _json_safe(merged)

    # Append new children
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

    session.commit()
    return poliza


def update_evaluation_columns(
    session: Session,
    numero_poliza: str,
    aseguradora: str,
    score: float,
    evaluation_json: str,
    evaluated_at: datetime,
    model_id: str,
) -> None:
    """Write evaluation results to an existing Poliza row.

    Sets evaluation_score, evaluation_json, evaluated_at, and evaluated_model_id
    on the Poliza identified by (numero_poliza, aseguradora).

    Args:
        session: Active SQLAlchemy session (caller owns the lifecycle).
        numero_poliza: Policy number to update.
        aseguradora: Insurer name to update.
        score: Overall evaluation score (average of completeness, accuracy, 1-hallucination_risk).
        evaluation_json: JSON string from EvaluationResult.evaluation_json.
        evaluated_at: UTC datetime when evaluation was performed.
        model_id: Model ID used for evaluation (e.g., EVAL_MODEL_ID).

    Raises:
        ValueError: If no Poliza row matches (numero_poliza, aseguradora).
    """
    poliza = (
        session.query(Poliza)
        .filter_by(numero_poliza=numero_poliza, aseguradora=aseguradora)
        .first()
    )

    if poliza is None:
        raise ValueError(f"Poliza not found: {numero_poliza} / {aseguradora}")

    poliza.evaluation_score = score
    poliza.evaluation_json = evaluation_json
    poliza.evaluated_at = evaluated_at
    poliza.evaluated_model_id = model_id

    session.commit()


def orm_to_schema(poliza: Poliza) -> PolicyExtraction:
    """Convert a Poliza ORM row (with loaded relationships) back to PolicyExtraction.

    Extracts confianza from campos_adicionales back to its dedicated top-level field.
    The returned campos_adicionales will NOT contain the 'confianza' key.

    Args:
        poliza: Poliza ORM row with asegurados and coberturas relationships loaded.

    Returns:
        PolicyExtraction Pydantic model populated from ORM columns.
    """
    # Separate confianza from other campos_adicionales
    raw_campos = dict(poliza.campos_adicionales or {})
    confianza = raw_campos.pop("confianza", {})

    # Reconstruct asegurados
    asegurados = [
        AseguradoExtraction(
            tipo=aseg.tipo,
            nombre_descripcion=aseg.nombre_descripcion,
            fecha_nacimiento=aseg.fecha_nacimiento,
            rfc=aseg.rfc,
            curp=aseg.curp,
            direccion=aseg.direccion,
            parentesco=aseg.parentesco,
            campos_adicionales=aseg.campos_adicionales or {},
        )
        for aseg in poliza.asegurados
    ]

    # Reconstruct coberturas
    coberturas = [
        CoberturaExtraction(
            nombre_cobertura=cob.nombre_cobertura,
            suma_asegurada=cob.suma_asegurada,
            deducible=cob.deducible,
            moneda=cob.moneda,
            campos_adicionales=cob.campos_adicionales or {},
        )
        for cob in poliza.coberturas
    ]

    return PolicyExtraction(
        numero_poliza=poliza.numero_poliza,
        aseguradora=poliza.aseguradora,
        tipo_seguro=poliza.tipo_seguro,
        fecha_emision=poliza.fecha_emision,
        inicio_vigencia=poliza.inicio_vigencia,
        fin_vigencia=poliza.fin_vigencia,
        nombre_contratante=poliza.nombre_contratante,
        nombre_agente=poliza.nombre_agente,
        prima_total=poliza.prima_total,
        moneda=poliza.moneda,
        forma_pago=poliza.forma_pago,
        frecuencia_pago=poliza.frecuencia_pago,
        source_file_hash=poliza.source_file_hash,
        model_id=poliza.model_id,
        prompt_version=poliza.prompt_version,
        extracted_at=poliza.extracted_at,
        campos_adicionales=raw_campos,
        confianza=confianza,
        asegurados=asegurados,
        coberturas=coberturas,
    )
