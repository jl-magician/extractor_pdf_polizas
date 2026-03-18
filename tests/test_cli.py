"""Tests for CLI helper utilities and CLI behavior stubs (Phase 4).

Tests 1-5: Unit tests for estimate_cost and is_already_extracted.
Tests 6-10: Placeholder stubs to be implemented in Plan 02.
"""
import pytest

from policy_extractor.cli_helpers import estimate_cost, is_already_extracted
from policy_extractor.storage.models import Poliza


# ---------------------------------------------------------------------------
# Tests — estimate_cost
# ---------------------------------------------------------------------------

def test_estimate_cost_haiku():
    """Haiku pricing: $1.00/M input, $5.00/M output."""
    result = estimate_cost("claude-haiku-4-5-20251001", 1000, 500)
    expected = (1000 * 1.00 + 500 * 5.00) / 1_000_000
    assert result == pytest.approx(expected)
    assert result == pytest.approx(0.0035)


def test_estimate_cost_sonnet():
    """Sonnet pricing: $3.00/M input, $15.00/M output."""
    result = estimate_cost("claude-sonnet-4-20250514", 1000, 500)
    expected = (1000 * 3.00 + 500 * 15.00) / 1_000_000
    assert result == pytest.approx(expected)
    assert result == pytest.approx(0.0105)


# ---------------------------------------------------------------------------
# Tests — is_already_extracted
# ---------------------------------------------------------------------------

def test_is_already_extracted_no_rows(session):
    """Empty DB returns False for any hash."""
    assert is_already_extracted(session, "abc123") is False


def test_is_already_extracted_match(session):
    """Row with matching source_file_hash returns True."""
    poliza = Poliza(
        source_file_hash="abc123",
        numero_poliza="TEST-001",
        aseguradora="Test",
    )
    session.add(poliza)
    session.commit()

    assert is_already_extracted(session, "abc123") is True


def test_is_already_extracted_no_match(session):
    """Row with different source_file_hash returns False for queried hash."""
    poliza = Poliza(
        source_file_hash="xyz789",
        numero_poliza="TEST-002",
        aseguradora="Test",
    )
    session.add(poliza)
    session.commit()

    assert is_already_extracted(session, "abc123") is False


# ---------------------------------------------------------------------------
# Placeholder stubs — to be implemented in Plan 02
# ---------------------------------------------------------------------------

def test_extract_single_file():
    pytest.skip("Implemented in plan 02")


def test_batch_directory():
    pytest.skip("Implemented in plan 02")


def test_batch_progress_display():
    pytest.skip("Implemented in plan 02")


def test_force_reprocess():
    pytest.skip("Implemented in plan 02")


def test_cost_tracking():
    pytest.skip("Implemented in plan 02")
