"""SQLAlchemy ORM model tests covering DATA-01 through DATA-05.

DATA-01: asegurados one-to-many, tipo discriminator
DATA-02: JSON campos_adicionales round-trips on all three tables
DATA-03: Date column type (not String)
DATA-04: Monetary Numeric type (not Float)
DATA-05: Provenance columns existence and value round-trip
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from policy_extractor.storage.models import Asegurado, Cobertura, Poliza


# ---------------------------------------------------------------------------
# Table existence
# ---------------------------------------------------------------------------

def test_tables_created(engine):
    """polizas, asegurados, coberturas tables must all exist."""
    i = inspect(engine)
    tables = i.get_table_names()
    assert "polizas" in tables
    assert "asegurados" in tables
    assert "coberturas" in tables


# ---------------------------------------------------------------------------
# DATA-01: One-to-many FK relationships
# ---------------------------------------------------------------------------

def test_asegurado_one_to_many(session):
    """Insert 1 Poliza + 3 Asegurado rows, query back all 3 with correct poliza_id."""
    poliza = Poliza(numero_poliza="POL-001", aseguradora="AXA")
    session.add(poliza)
    session.flush()  # Assigns poliza.id

    asegurados = [
        Asegurado(poliza_id=poliza.id, tipo="persona", nombre_descripcion="Juan Perez"),
        Asegurado(poliza_id=poliza.id, tipo="persona", nombre_descripcion="Maria Lopez"),
        Asegurado(poliza_id=poliza.id, tipo="bien", nombre_descripcion="Toyota Corolla 2022"),
    ]
    session.add_all(asegurados)
    session.commit()

    result = session.query(Asegurado).filter_by(poliza_id=poliza.id).all()
    assert len(result) == 3
    tipos = {a.tipo for a in result}
    assert "persona" in tipos
    assert "bien" in tipos
    for a in result:
        assert a.poliza_id == poliza.id


def test_cobertura_one_to_many(session):
    """Insert 1 Poliza + 2 Cobertura rows, query back both with correct poliza_id."""
    poliza = Poliza(numero_poliza="POL-002", aseguradora="GNP")
    session.add(poliza)
    session.flush()

    coberturas = [
        Cobertura(poliza_id=poliza.id, nombre_cobertura="Daños a Terceros"),
        Cobertura(poliza_id=poliza.id, nombre_cobertura="Robo Total"),
    ]
    session.add_all(coberturas)
    session.commit()

    result = session.query(Cobertura).filter_by(poliza_id=poliza.id).all()
    assert len(result) == 2
    for c in result:
        assert c.poliza_id == poliza.id


# ---------------------------------------------------------------------------
# DATA-02: JSON overflow round-trips
# ---------------------------------------------------------------------------

def test_json_overflow_roundtrip_poliza(session):
    """campos_adicionales on Poliza survives commit/refresh cycle."""
    poliza = Poliza(
        numero_poliza="POL-003",
        aseguradora="HDI",
        campos_adicionales={"rfc_contratante": "GARC850101"},
    )
    session.add(poliza)
    session.commit()
    session.refresh(poliza)

    assert poliza.campos_adicionales["rfc_contratante"] == "GARC850101"


def test_json_overflow_roundtrip_asegurado(session):
    """campos_adicionales on Asegurado survives commit/refresh cycle."""
    poliza = Poliza(numero_poliza="POL-004", aseguradora="Qualitas")
    session.add(poliza)
    session.flush()

    asegurado = Asegurado(
        poliza_id=poliza.id,
        tipo="bien",
        nombre_descripcion="Honda Civic 2021",
        campos_adicionales={"vin": "1HGCM82633A004352", "placas": "ABC1234"},
    )
    session.add(asegurado)
    session.commit()
    session.refresh(asegurado)

    assert asegurado.campos_adicionales["vin"] == "1HGCM82633A004352"
    assert asegurado.campos_adicionales["placas"] == "ABC1234"


def test_json_overflow_roundtrip_cobertura(session):
    """campos_adicionales on Cobertura survives commit/refresh cycle."""
    poliza = Poliza(numero_poliza="POL-005", aseguradora="Mapfre")
    session.add(poliza)
    session.flush()

    cobertura = Cobertura(
        poliza_id=poliza.id,
        nombre_cobertura="Gastos Médicos",
        campos_adicionales={"coaseguro": "10%"},
    )
    session.add(cobertura)
    session.commit()
    session.refresh(cobertura)

    assert cobertura.campos_adicionales["coaseguro"] == "10%"


# ---------------------------------------------------------------------------
# DATA-03: Date column type inspection
# ---------------------------------------------------------------------------

def test_date_column_type(engine):
    """inicio_vigencia on polizas must be a DATE column, not a String column."""
    i = inspect(engine)
    cols = {c["name"]: c for c in i.get_columns("polizas")}
    assert "inicio_vigencia" in cols
    # SQLAlchemy inspect returns type class name for SQLite
    col_type = type(cols["inicio_vigencia"]["type"]).__name__.upper()
    assert "DATE" in col_type, f"Expected DATE type, got {col_type}"


# ---------------------------------------------------------------------------
# DATA-04: Monetary column type inspection
# ---------------------------------------------------------------------------

def test_monetary_numeric_type(engine):
    """prima_total on polizas must be NUMERIC, not FLOAT."""
    i = inspect(engine)
    cols = {c["name"]: c for c in i.get_columns("polizas")}
    assert "prima_total" in cols
    col_type = type(cols["prima_total"]["type"]).__name__.upper()
    assert "NUMERIC" in col_type or "DECIMAL" in col_type, (
        f"Expected NUMERIC/DECIMAL type, got {col_type}"
    )


# ---------------------------------------------------------------------------
# DATA-05: Provenance columns
# ---------------------------------------------------------------------------

def test_provenance_columns(engine):
    """polizas table must have all four provenance columns."""
    i = inspect(engine)
    col_names = [c["name"] for c in i.get_columns("polizas")]
    assert "source_file_hash" in col_names
    assert "model_id" in col_names
    assert "prompt_version" in col_names
    assert "extracted_at" in col_names


def test_provenance_values_roundtrip(session):
    """All four provenance field values must survive commit/refresh cycle."""
    now = datetime(2026, 3, 18, 15, 0, 0)
    poliza = Poliza(
        numero_poliza="POL-006",
        aseguradora="Zurich",
        source_file_hash="abc123def456" * 2,  # 24 chars, fits String(64)
        model_id="claude-sonnet-4-6-20250514",
        prompt_version="v1.0.0",
        extracted_at=now,
    )
    session.add(poliza)
    session.commit()
    session.refresh(poliza)

    assert poliza.source_file_hash == "abc123def456abc123def456"
    assert poliza.model_id == "claude-sonnet-4-6-20250514"
    assert poliza.prompt_version == "v1.0.0"
    assert poliza.extracted_at == now


# ---------------------------------------------------------------------------
# Cascade delete
# ---------------------------------------------------------------------------

def test_cascade_delete(session):
    """Deleting a Poliza must cascade-delete all related Asegurado and Cobertura rows."""
    poliza = Poliza(numero_poliza="POL-007", aseguradora="Chubb")
    session.add(poliza)
    session.flush()

    session.add(Asegurado(poliza_id=poliza.id, tipo="persona", nombre_descripcion="Test Person"))
    session.add(Cobertura(poliza_id=poliza.id, nombre_cobertura="Test Coverage"))
    session.commit()

    # Verify rows exist
    assert session.query(Asegurado).filter_by(poliza_id=poliza.id).count() == 1
    assert session.query(Cobertura).filter_by(poliza_id=poliza.id).count() == 1

    # Delete poliza and cascade
    session.delete(poliza)
    session.commit()

    assert session.query(Asegurado).filter_by(poliza_id=poliza.id).count() == 0
    assert session.query(Cobertura).filter_by(poliza_id=poliza.id).count() == 0
