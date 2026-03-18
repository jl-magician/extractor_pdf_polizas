"""Tests for Pydantic v2 extraction schemas — data contract validation.

Covers: DATA-01 (AseguradoExtraction tipos), DATA-03 (date normalization),
DATA-04 (Decimal precision, currency default).
"""
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# DATA-01: AseguradoExtraction tipo discriminator
# ---------------------------------------------------------------------------

def test_asegurado_tipo_persona():
    from policy_extractor.schemas import AseguradoExtraction

    a = AseguradoExtraction(tipo="persona", nombre_descripcion="Juan Perez")
    assert a.tipo == "persona"
    assert a.nombre_descripcion == "Juan Perez"


def test_asegurado_tipo_bien():
    from policy_extractor.schemas import AseguradoExtraction

    a = AseguradoExtraction(
        tipo="bien",
        nombre_descripcion="Toyota Corolla 2022",
        campos_adicionales={"placas": "ABC1234", "vin": "1HGCM82633A004352"},
    )
    assert a.tipo == "bien"
    assert a.campos_adicionales["placas"] == "ABC1234"


def test_asegurado_tipo_equipo_rejected():
    from policy_extractor.schemas import AseguradoExtraction

    with pytest.raises(ValidationError):
        AseguradoExtraction(tipo="equipo", nombre_descripcion="Maquinaria X")


def test_asegurado_persona_fields_optional():
    from policy_extractor.schemas import AseguradoExtraction

    a = AseguradoExtraction(tipo="persona", nombre_descripcion="Maria Lopez")
    assert a.fecha_nacimiento is None
    assert a.rfc is None
    assert a.curp is None
    assert a.direccion is None
    assert a.parentesco is None


def test_asegurado_campos_adicionales_defaults_empty():
    from policy_extractor.schemas import AseguradoExtraction

    a = AseguradoExtraction(tipo="persona", nombre_descripcion="Ana")
    assert a.campos_adicionales == {}


# ---------------------------------------------------------------------------
# DATA-03: Date normalization
# ---------------------------------------------------------------------------

def test_date_normalization_ddmmyyyy():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(numero_poliza="POL-001", aseguradora="AXA", fecha_emision="15/01/2025")
    assert p.fecha_emision == date(2025, 1, 15)


def test_date_normalization_iso():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(numero_poliza="POL-001", aseguradora="AXA", fecha_emision="2025-01-15")
    assert p.fecha_emision == date(2025, 1, 15)


def test_date_normalization_none():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(numero_poliza="POL-001", aseguradora="AXA", fecha_emision=None)
    assert p.fecha_emision is None


def test_date_normalization_all_date_fields():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(
        numero_poliza="POL-001",
        aseguradora="AXA",
        fecha_emision="15/01/2025",
        inicio_vigencia="01/02/2025",
        fin_vigencia="2026-02-01",
    )
    assert p.fecha_emision == date(2025, 1, 15)
    assert p.inicio_vigencia == date(2025, 2, 1)
    assert p.fin_vigencia == date(2026, 2, 1)


# ---------------------------------------------------------------------------
# DATA-04: Decimal precision and currency
# ---------------------------------------------------------------------------

def test_decimal_precision_round_trip():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(
        numero_poliza="POL-001",
        aseguradora="AXA",
        prima_total=Decimal("1500000.00"),
    )
    assert p.prima_total == Decimal("1500000.00")


def test_decimal_no_float_corruption():
    from policy_extractor.schemas import PolicyExtraction

    # Decimal("1500000.00") must NOT become 1499999.9999...
    p = PolicyExtraction(
        numero_poliza="POL-001",
        aseguradora="AXA",
        prima_total=Decimal("1500000.00"),
    )
    assert str(p.prima_total) == "1500000.00"


def test_moneda_defaults_to_mxn():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(numero_poliza="POL-001", aseguradora="AXA")
    assert p.moneda == "MXN"


def test_moneda_accepts_usd():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(numero_poliza="POL-001", aseguradora="AXA", moneda="USD")
    assert p.moneda == "USD"


def test_cobertura_moneda_defaults_to_mxn():
    from policy_extractor.schemas import CoberturaExtraction

    c = CoberturaExtraction(nombre_cobertura="Daños a Terceros")
    assert c.moneda == "MXN"


def test_cobertura_suma_asegurada_decimal():
    from policy_extractor.schemas import CoberturaExtraction

    c = CoberturaExtraction(
        nombre_cobertura="Daños a Terceros",
        suma_asegurada=Decimal("500000.00"),
        deducible=Decimal("10000.00"),
    )
    assert c.suma_asegurada == Decimal("500000.00")
    assert c.deducible == Decimal("10000.00")


# ---------------------------------------------------------------------------
# DATA-05: Provenance fields on PolicyExtraction
# ---------------------------------------------------------------------------

def test_provenance_fields_exist():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(
        numero_poliza="POL-001",
        aseguradora="AXA",
        source_file_hash="abc123",
        model_id="claude-sonnet-4-6",
        prompt_version="v1.0.0",
    )
    assert p.source_file_hash == "abc123"
    assert p.model_id == "claude-sonnet-4-6"
    assert p.prompt_version == "v1.0.0"


def test_provenance_fields_default_none():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(numero_poliza="POL-001", aseguradora="AXA")
    assert p.source_file_hash is None
    assert p.model_id is None
    assert p.prompt_version is None
    assert p.extracted_at is None


# ---------------------------------------------------------------------------
# DATA-02: campos_adicionales overflow on all three models
# ---------------------------------------------------------------------------

def test_policy_campos_adicionales():
    from policy_extractor.schemas import PolicyExtraction

    p = PolicyExtraction(
        numero_poliza="POL-001",
        aseguradora="AXA",
        campos_adicionales={"rfc_contratante": "ABCD123456"},
    )
    assert p.campos_adicionales["rfc_contratante"] == "ABCD123456"


def test_cobertura_campos_adicionales():
    from policy_extractor.schemas import CoberturaExtraction

    c = CoberturaExtraction(
        nombre_cobertura="Gastos Medicos",
        campos_adicionales={"coaseguro": "10%", "copago": "500"},
    )
    assert c.campos_adicionales["coaseguro"] == "10%"


# ---------------------------------------------------------------------------
# Schema import smoke test
# ---------------------------------------------------------------------------

def test_imports():
    from policy_extractor.schemas import AseguradoExtraction, CoberturaExtraction, PolicyExtraction

    assert PolicyExtraction is not None
    assert AseguradoExtraction is not None
    assert CoberturaExtraction is not None


def test_policy_extraction_with_asegurados_and_coberturas():
    from policy_extractor.schemas import AseguradoExtraction, CoberturaExtraction, PolicyExtraction

    p = PolicyExtraction(
        numero_poliza="POL-001",
        aseguradora="GNP",
        asegurados=[
            AseguradoExtraction(tipo="persona", nombre_descripcion="Juan"),
            AseguradoExtraction(
                tipo="bien",
                nombre_descripcion="VW Golf 2023",
                campos_adicionales={"placas": "XYZ9999"},
            ),
        ],
        coberturas=[
            CoberturaExtraction(
                nombre_cobertura="Robo Total",
                suma_asegurada=Decimal("350000.00"),
            )
        ],
    )
    assert len(p.asegurados) == 2
    assert len(p.coberturas) == 1
    assert p.asegurados[0].tipo == "persona"
    assert p.asegurados[1].tipo == "bien"
