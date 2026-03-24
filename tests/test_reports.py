"""Tests for Phase 16 Plan 01 — PDF report generation.

Tests use SimpleNamespace mock objects to avoid DB dependency.
PDF content verification uses PyMuPDF (fitz) to extract text from PDF bytes.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_poliza(**kwargs) -> SimpleNamespace:
    """Build a mock Poliza-like object with sensible defaults."""
    defaults = dict(
        id=1,
        numero_poliza="POL-TEST-001",
        aseguradora="zurich",
        tipo_seguro="Auto",
        fecha_emision=None,
        inicio_vigencia=None,
        fin_vigencia=None,
        nombre_agente="Agente Test",
        nombre_contratante="Juan Perez",
        prima_total=Decimal("10500.00"),
        moneda="MXN",
        forma_pago="Anual",
        frecuencia_pago="Anual",
        campos_adicionales={},
        asegurados=[],
        coberturas=[],
        evaluation_score=None,
        validation_warnings=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_asegurado(**kwargs) -> SimpleNamespace:
    defaults = dict(
        tipo="persona",
        nombre_descripcion="Maria Lopez",
        fecha_nacimiento=None,
        rfc="LOPM800101ABC",
        parentesco="Conyugue",
        campos_adicionales=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_cobertura(**kwargs) -> SimpleNamespace:
    defaults = dict(
        nombre_cobertura="Responsabilidad Civil",
        suma_asegurada=Decimal("500000.00"),
        deducible=Decimal("5000.00"),
        moneda="MXN",
        campos_adicionales=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _pdf_text(pdf_bytes: bytearray) -> str:
    """Extract all text from PDF bytes using PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=bytes(pdf_bytes), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_generate_poliza_report_returns_valid_pdf_bytes():
    """Test 1: generate_poliza_report returns bytearray starting with %PDF."""
    from policy_extractor.reports import generate_poliza_report

    poliza = _make_poliza()
    result = generate_poliza_report(poliza)
    assert isinstance(result, bytearray)
    assert result[:5] == bytearray(b"%PDF-"), "Output must start with PDF header"


def test_generate_poliza_report_zurich_loads_brand_color():
    """Test 2: Zurich poliza loads zurich.yaml config (brand_color = [0, 82, 160])."""
    from policy_extractor.reports.config_loader import load_insurer_config

    config = load_insurer_config("zurich")
    assert config["brand_color"] == [0, 82, 160], (
        "Zurich brand color should be [0, 82, 160]"
    )


def test_generate_poliza_report_unknown_insurer_falls_back():
    """Test 3: Unknown insurer falls back to default.yaml without raising."""
    from policy_extractor.reports import generate_poliza_report

    poliza = _make_poliza(aseguradora="insurer_that_does_not_exist_xyz")
    # Must not raise any exception
    result = generate_poliza_report(poliza)
    assert isinstance(result, bytearray)
    assert result[:5] == bytearray(b"%PDF-")


def test_load_insurer_config_zurich_has_required_keys():
    """Test 4: load_insurer_config('zurich') returns dict with required keys."""
    from policy_extractor.reports.config_loader import load_insurer_config

    config = load_insurer_config("zurich")
    assert "brand_color" in config
    assert "display_name" in config
    assert "sections" in config


def test_load_insurer_config_nonexistent_returns_default():
    """Test 5: load_insurer_config('nonexistent') returns default config dict."""
    from policy_extractor.reports.config_loader import load_insurer_config

    config = load_insurer_config("nonexistent_insurer_xyz")
    assert "brand_color" in config
    assert "display_name" in config
    assert "sections" in config


def test_generated_pdf_contains_numero_poliza():
    """Test 6: Generated PDF contains poliza.numero_poliza text."""
    from policy_extractor.reports import generate_poliza_report

    poliza = _make_poliza(numero_poliza="POLIZA-UNIQUE-9876")
    result = generate_poliza_report(poliza)
    text = _pdf_text(result)
    assert "POLIZA-UNIQUE-9876" in text, (
        f"PDF text should contain numero_poliza. Got: {text[:500]}"
    )


def test_generated_pdf_with_asegurados_contains_section_header():
    """Test 7: Generated PDF with asegurados list includes 'Asegurados' section header."""
    from policy_extractor.reports import generate_poliza_report

    asegurado = _make_asegurado()
    poliza = _make_poliza(asegurados=[asegurado])
    result = generate_poliza_report(poliza)
    text = _pdf_text(result)
    assert "Asegurados" in text, (
        f"PDF should contain 'Asegurados' section. Got: {text[:500]}"
    )


def test_generated_pdf_with_empty_campos_adicionales_shows_sin_campos():
    """Test 8: Generated PDF with empty campos_adicionales includes 'Sin campos adicionales'."""
    from policy_extractor.reports import generate_poliza_report

    poliza = _make_poliza(campos_adicionales={})
    result = generate_poliza_report(poliza)
    text = _pdf_text(result)
    assert "Sin campos adicionales" in text, (
        f"PDF should contain 'Sin campos adicionales'. Got: {text[:500]}"
    )
