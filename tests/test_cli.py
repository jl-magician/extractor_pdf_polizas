"""Tests for CLI helper utilities and CLI commands (Phase 4).

Tests 1-5: Unit tests for estimate_cost and is_already_extracted (passing from Plan 01).
Tests 6-12: Full CLI command tests using typer.testing.CliRunner with mocked pipeline.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from policy_extractor.cli import app
from policy_extractor.cli_helpers import estimate_cost, is_already_extracted
from policy_extractor.schemas.poliza import PolicyExtraction
from policy_extractor.storage.models import Poliza

runner = CliRunner()


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def mock_ingestion_result():
    """Return a mock IngestionResult-like object with required attributes."""
    m = MagicMock()
    m.file_hash = "abc123"
    m.file_path = "/tmp/test.pdf"
    m.total_pages = 1
    m.pages = []
    m.file_size_bytes = 1000
    m.created_at = datetime.utcnow()
    m.ocr_applied = False
    m.ocr_language = "spa"
    m.from_cache = False
    return m


def mock_policy_extraction():
    """Return a real PolicyExtraction instance."""
    return PolicyExtraction(numero_poliza="POL-001", aseguradora="TestInsurer")


def mock_usage():
    """Return a mock Usage object."""
    m = MagicMock()
    m.input_tokens = 500
    m.output_tokens = 200
    return m


# ---------------------------------------------------------------------------
# Common patch targets
# ---------------------------------------------------------------------------

PATCH_INGEST = "policy_extractor.cli.ingest_pdf"
PATCH_EXTRACT = "policy_extractor.cli.extract_policy"
PATCH_INIT_DB = "policy_extractor.cli.init_db"
PATCH_SESSION = "policy_extractor.cli.SessionLocal"
PATCH_HASH = "policy_extractor.cli.compute_file_hash"
PATCH_IS_EXTRACTED = "policy_extractor.cli.is_already_extracted"


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
# CLI tests — extract subcommand
# ---------------------------------------------------------------------------


def test_extract_single_file(tmp_path):
    """Extract a single PDF — JSON with policy data on stdout (ING-03, CLI-01)."""
    temp_pdf = tmp_path / "test.pdf"
    temp_pdf.write_bytes(b"%PDF-1.4 fake")

    mock_session = MagicMock()

    with (
        patch(PATCH_INIT_DB) as mock_init_db,
        patch(PATCH_SESSION) as mock_session_cls,
        patch(PATCH_HASH, return_value="abc123"),
        patch(PATCH_IS_EXTRACTED, return_value=False),
        patch(PATCH_INGEST, return_value=mock_ingestion_result()),
        patch(PATCH_EXTRACT, return_value=(mock_policy_extraction(), mock_usage())),
    ):
        mock_session_cls.return_value = mock_session
        mock_session_cls.configure = MagicMock()

        result = runner.invoke(app, ["extract", str(temp_pdf)])

    assert result.exit_code == 0, result.output
    assert "POL-001" in result.output
    assert "TestInsurer" in result.output


def test_batch_directory(tmp_path):
    """Batch-process a directory with 2 PDFs (ING-04, CLI-02)."""
    pdf1 = tmp_path / "a.pdf"
    pdf2 = tmp_path / "b.pdf"
    pdf1.write_bytes(b"%PDF-1.4 fake")
    pdf2.write_bytes(b"%PDF-1.4 fake")

    mock_session = MagicMock()

    with (
        patch(PATCH_INIT_DB),
        patch(PATCH_SESSION) as mock_session_cls,
        patch(PATCH_HASH, return_value="abc123"),
        patch(PATCH_IS_EXTRACTED, return_value=False),
        patch(PATCH_INGEST, return_value=mock_ingestion_result()),
        patch(PATCH_EXTRACT, return_value=(mock_policy_extraction(), mock_usage())),
    ):
        mock_session_cls.return_value = mock_session
        mock_session_cls.configure = MagicMock()

        result = runner.invoke(app, ["batch", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Succeeded" in result.output


def test_batch_progress_display(tmp_path):
    """Batch with 3 PDFs shows progress and count info (CLI-03)."""
    for name in ["x.pdf", "y.pdf", "z.pdf"]:
        (tmp_path / name).write_bytes(b"%PDF-1.4 fake")

    mock_session = MagicMock()

    with (
        patch(PATCH_INIT_DB),
        patch(PATCH_SESSION) as mock_session_cls,
        patch(PATCH_HASH, return_value="abc123"),
        patch(PATCH_IS_EXTRACTED, return_value=False),
        patch(PATCH_INGEST, return_value=mock_ingestion_result()),
        patch(PATCH_EXTRACT, return_value=(mock_policy_extraction(), mock_usage())),
    ):
        mock_session_cls.return_value = mock_session
        mock_session_cls.configure = MagicMock()

        result = runner.invoke(app, ["batch", str(tmp_path)])

    assert result.exit_code == 0, result.output
    # Summary table always rendered; check processed count or 'Processed' label
    combined = result.output
    assert "Processed" in combined or "3" in combined


def test_force_reprocess(tmp_path):
    """--force bypasses idempotency skip; without it, already-extracted file is skipped."""
    temp_pdf = tmp_path / "policy.pdf"
    temp_pdf.write_bytes(b"%PDF-1.4 fake")

    mock_session = MagicMock()

    # With --force: extract_policy MUST be called despite is_already_extracted=True
    with (
        patch(PATCH_INIT_DB),
        patch(PATCH_SESSION) as mock_session_cls,
        patch(PATCH_HASH, return_value="abc123"),
        patch(PATCH_IS_EXTRACTED, return_value=True),
        patch(PATCH_INGEST, return_value=mock_ingestion_result()),
        patch(PATCH_EXTRACT, return_value=(mock_policy_extraction(), mock_usage())) as mock_ext,
    ):
        mock_session_cls.return_value = mock_session
        mock_session_cls.configure = MagicMock()
        result_force = runner.invoke(app, ["extract", str(temp_pdf), "--force"])
        assert mock_ext.called, "extract_policy should have been called with --force"

    assert result_force.exit_code == 0, result_force.output

    # Without --force: extract_policy must NOT be called
    with (
        patch(PATCH_INIT_DB),
        patch(PATCH_SESSION) as mock_session_cls,
        patch(PATCH_HASH, return_value="abc123"),
        patch(PATCH_IS_EXTRACTED, return_value=True),
        patch(PATCH_INGEST, return_value=mock_ingestion_result()),
        patch(PATCH_EXTRACT, return_value=(mock_policy_extraction(), mock_usage())) as mock_ext,
    ):
        mock_session_cls.return_value = mock_session
        mock_session_cls.configure = MagicMock()
        result_skip = runner.invoke(app, ["extract", str(temp_pdf)])
        assert not mock_ext.called, "extract_policy should NOT have been called without --force"

    assert result_skip.exit_code == 0
    assert "SKIP" in result_skip.output


def test_cost_tracking(tmp_path):
    """Cost string ($ sign) and token counts appear in output after extraction (CLI-05)."""
    temp_pdf = tmp_path / "policy.pdf"
    temp_pdf.write_bytes(b"%PDF-1.4 fake")

    mock_session = MagicMock()

    with (
        patch(PATCH_INIT_DB),
        patch(PATCH_SESSION) as mock_session_cls,
        patch(PATCH_HASH, return_value="abc123"),
        patch(PATCH_IS_EXTRACTED, return_value=False),
        patch(PATCH_INGEST, return_value=mock_ingestion_result()),
        patch(PATCH_EXTRACT, return_value=(mock_policy_extraction(), mock_usage())),
    ):
        mock_session_cls.return_value = mock_session
        mock_session_cls.configure = MagicMock()
        result = runner.invoke(app, ["extract", str(temp_pdf)])

    assert result.exit_code == 0, result.output
    # Cost info is printed to stderr which CliRunner captures in output
    combined = result.output
    assert "$" in combined or "500" in combined or "200" in combined


def test_batch_failure_continues(tmp_path):
    """A failure in one PDF does not stop batch; summary reports failed count."""
    pdf1 = tmp_path / "ok.pdf"
    pdf2 = tmp_path / "bad.pdf"
    # Sorted alphabetically: bad.pdf, ok.pdf
    pdf1.write_bytes(b"%PDF-1.4 fake")
    pdf2.write_bytes(b"%PDF-1.4 fake")

    mock_session = MagicMock()

    # extract_policy fails on first call, succeeds on second
    extract_results = [
        Exception("API error"),
        (mock_policy_extraction(), mock_usage()),
    ]

    def extract_side_effect(*args, **kwargs):
        result = extract_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    ingest_call_count = {"n": 0}

    def ingest_side_effect(*args, **kwargs):
        ingest_call_count["n"] += 1
        return mock_ingestion_result()

    with (
        patch(PATCH_INIT_DB),
        patch(PATCH_SESSION) as mock_session_cls,
        patch(PATCH_HASH, return_value="abc123"),
        patch(PATCH_IS_EXTRACTED, return_value=False),
        patch(PATCH_INGEST, side_effect=ingest_side_effect),
        patch(PATCH_EXTRACT, side_effect=extract_side_effect),
    ):
        mock_session_cls.return_value = mock_session
        mock_session_cls.configure = MagicMock()
        result = runner.invoke(app, ["batch", str(tmp_path)])

    # Both files were attempted
    assert ingest_call_count["n"] == 2
    assert "Failed" in result.output
    # Exit code 1 because of failure
    assert result.exit_code == 1


def test_idempotency_skip(tmp_path):
    """extract without --force skips already-extracted PDF (CLI-04)."""
    temp_pdf = tmp_path / "already.pdf"
    temp_pdf.write_bytes(b"%PDF-1.4 fake")

    mock_session = MagicMock()

    with (
        patch(PATCH_INIT_DB),
        patch(PATCH_SESSION) as mock_session_cls,
        patch(PATCH_HASH, return_value="abc123"),
        patch(PATCH_IS_EXTRACTED, return_value=True),
        patch(PATCH_INGEST, return_value=mock_ingestion_result()),
        patch(PATCH_EXTRACT, return_value=(mock_policy_extraction(), mock_usage())) as mock_ext,
    ):
        mock_session_cls.return_value = mock_session
        mock_session_cls.configure = MagicMock()
        result = runner.invoke(app, ["extract", str(temp_pdf)])

    assert result.exit_code == 0
    assert "SKIP" in result.output
    assert not mock_ext.called
