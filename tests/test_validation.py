"""Unit tests for the post-extraction validation module (EXT-02)."""
import pytest
from datetime import date
from decimal import Decimal

from policy_extractor.schemas.poliza import PolicyExtraction
from policy_extractor.extraction.validation import (
    validate_extraction,
    check_financial_invariant,
    check_date_logic,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_policy(**kwargs) -> PolicyExtraction:
    """Build a minimal PolicyExtraction for testing. Only required fields set."""
    defaults = {
        "numero_poliza": "TEST-0001",
        "aseguradora": "Test SA de CV",
    }
    defaults.update(kwargs)
    return PolicyExtraction(**defaults)


# ─── validate_extraction() ────────────────────────────────────────────────────

def test_validate_extraction_no_financial_fields_returns_empty():
    """validate_extraction() returns empty list when no financial/date fields set."""
    policy = make_policy()
    result = validate_extraction(policy)
    assert result == []


def test_validate_extraction_aggregates_warnings_from_all_validators():
    """validate_extraction() accumulates warnings from all registered validators."""
    policy = make_policy(
        prima_total=Decimal("10000"),
        primer_pago=Decimal("5000"),
        pago_subsecuente=Decimal("3000"),  # 20% off
        inicio_vigencia=date(2025, 12, 31),
        fin_vigencia=date(2025, 1, 1),  # fin < inicio
    )
    result = validate_extraction(policy)
    # Should have at least one financial warning + one date warning
    assert len(result) >= 2
    fields = {w["field"] for w in result}
    assert "prima_total" in fields
    assert "fin_vigencia" in fields


# ─── check_financial_invariant() ─────────────────────────────────────────────

def test_financial_invariant_mismatch_20pct_triggers_warning():
    """primer_pago(5000) + pago_subsecuente(3000) vs prima_total(10000) is 20% off — warning."""
    policy = make_policy(
        prima_total=Decimal("10000"),
        primer_pago=Decimal("5000"),
        pago_subsecuente=Decimal("3000"),
    )
    result = check_financial_invariant(policy)
    assert len(result) == 1
    w = result[0]
    assert w["field"] == "prima_total"
    assert "severity" in w
    assert "message" in w
    assert w["severity"] == "warning"
    assert "20.00%" in w["message"]


def test_financial_invariant_exact_match_no_warning():
    """primer_pago(5000) + pago_subsecuente(5000) == prima_total(10000) — no warning."""
    policy = make_policy(
        prima_total=Decimal("10000"),
        primer_pago=Decimal("5000"),
        pago_subsecuente=Decimal("5000"),
    )
    result = check_financial_invariant(policy)
    assert result == []


def test_financial_invariant_primer_pago_none_skips():
    """primer_pago is None — skip (cannot validate)."""
    policy = make_policy(
        prima_total=Decimal("10000"),
        pago_subsecuente=Decimal("5000"),
    )
    result = check_financial_invariant(policy)
    assert result == []


def test_financial_invariant_subsecuentes_none_skips():
    """pago_subsecuente is None — skip (cannot validate)."""
    policy = make_policy(
        prima_total=Decimal("10000"),
        primer_pago=Decimal("5000"),
    )
    result = check_financial_invariant(policy)
    assert result == []


def test_financial_invariant_prima_total_none_skips():
    """prima_total is None — skip (cannot validate)."""
    policy = make_policy(
        primer_pago=Decimal("5000"),
        pago_subsecuente=Decimal("5000"),
    )
    result = check_financial_invariant(policy)
    assert result == []


def test_financial_invariant_boundary_exactly_1pct_no_warning():
    """Exactly 1% difference — must NOT trigger (threshold is >1%, not >=1%)."""
    policy = make_policy(
        prima_total=Decimal("5000"),
        primer_pago=Decimal("4950"),
        pago_subsecuente=Decimal("0"),
    )
    result = check_financial_invariant(policy)
    assert result == []


def test_financial_invariant_just_over_1pct_triggers_warning():
    """1.01% difference — should trigger a warning."""
    policy = make_policy(
        prima_total=Decimal("5000"),
        primer_pago=Decimal("4949"),
        pago_subsecuente=Decimal("0"),
    )
    result = check_financial_invariant(policy)
    assert len(result) == 1
    assert result[0]["field"] == "prima_total"


def test_financial_invariant_warning_contains_percentage():
    """Warning message contains the difference percentage."""
    policy = make_policy(
        prima_total=Decimal("10000"),
        primer_pago=Decimal("5000"),
        pago_subsecuente=Decimal("3000"),
    )
    result = check_financial_invariant(policy)
    assert len(result) == 1
    assert "%" in result[0]["message"]


# ─── check_date_logic() ───────────────────────────────────────────────────────

def test_date_logic_fin_before_inicio_triggers_warning():
    """fin_vigencia < inicio_vigencia — date logic error warning."""
    policy = make_policy(
        inicio_vigencia=date(2025, 6, 1),
        fin_vigencia=date(2025, 1, 1),
    )
    result = check_date_logic(policy)
    assert len(result) >= 1
    assert any(w["field"] == "fin_vigencia" for w in result)


def test_date_logic_emision_after_inicio_triggers_warning():
    """fecha_emision > inicio_vigencia — date logic error warning."""
    policy = make_policy(
        fecha_emision=date(2025, 7, 1),
        inicio_vigencia=date(2025, 6, 1),
        fin_vigencia=date(2026, 6, 1),
    )
    result = check_date_logic(policy)
    assert len(result) >= 1
    assert any(w["field"] == "fecha_emision" for w in result)


def test_date_logic_valid_dates_no_warning():
    """fecha_emision <= inicio_vigencia < fin_vigencia — no warnings."""
    policy = make_policy(
        fecha_emision=date(2025, 1, 1),
        inicio_vigencia=date(2025, 6, 1),
        fin_vigencia=date(2026, 6, 1),
    )
    result = check_date_logic(policy)
    assert result == []


def test_date_logic_none_dates_no_warning():
    """All date fields None — no warnings (cannot validate)."""
    policy = make_policy()
    result = check_date_logic(policy)
    assert result == []


def test_date_logic_warning_has_required_keys():
    """Date warning dict has 'field', 'message', and 'severity' keys."""
    policy = make_policy(
        inicio_vigencia=date(2025, 6, 1),
        fin_vigencia=date(2025, 1, 1),
    )
    result = check_date_logic(policy)
    assert len(result) >= 1
    w = result[0]
    assert "field" in w
    assert "message" in w
    assert "severity" in w
