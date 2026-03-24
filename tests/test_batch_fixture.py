"""Unit tests for the batch-fixtures CLI subcommand.

Tests use mocked ingest_pdf and extract_policy to avoid real API calls.
All file I/O uses tmp_path (pytest built-in fixture).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from policy_extractor.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers / shared mock data
# ---------------------------------------------------------------------------

def _make_fake_policy(insurer="zurich", policy_type="auto"):
    """Return a MagicMock that behaves like a PolicyExtraction object."""
    policy = MagicMock()
    policy.model_dump.return_value = {
        "numero_poliza": "ZUR-001",
        "aseguradora": insurer,
        "tipo_seguro": policy_type,
        "nombre_contratante": "Juan Perez",  # PII — must be redacted
        "coberturas": [],
        "asegurados": [],
    }
    return policy


def _make_fake_usage():
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50
    return usage


# ---------------------------------------------------------------------------
# Test 1: two PDFs → two fixture files created in output dir
# ---------------------------------------------------------------------------

def test_batch_fixtures_creates_fixture_files(tmp_path):
    """batch_fixtures processes 2 PDFs and writes 2 fixture JSON files."""
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "fixtures"

    # Create fake PDF files (just empty files with .pdf extension)
    (pdf_dir / "zurich_auto_policy.pdf").write_bytes(b"%PDF-1.4 fake")
    (pdf_dir / "qualitas_auto_policy.pdf").write_bytes(b"%PDF-1.4 fake")

    fake_policy_zurich = _make_fake_policy("zurich", "auto")
    fake_policy_qualitas = _make_fake_policy("qualitas", "auto")

    call_count = {"n": 0}

    def mock_extract(ingestion_result, model=None):
        n = call_count["n"]
        call_count["n"] += 1
        p = fake_policy_zurich if n == 0 else fake_policy_qualitas
        return (p, _make_fake_usage(), 0)

    with (
        patch("policy_extractor.cli.ingest_pdf") as mock_ingest,
        patch("policy_extractor.cli.extract_policy", side_effect=mock_extract),
        patch("policy_extractor.cli._setup_db"),
        patch("policy_extractor.cli.SessionLocal"),
    ):
        mock_ingest.return_value = MagicMock()
        result = runner.invoke(
            app,
            ["batch-fixtures", str(pdf_dir), "--output", str(out_dir)],
        )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    fixture_files = list(out_dir.glob("*.json"))
    assert len(fixture_files) == 2


# ---------------------------------------------------------------------------
# Test 2: each fixture contains required metadata keys
# ---------------------------------------------------------------------------

def test_batch_fixtures_metadata_keys(tmp_path):
    """Each written fixture has _source_pdf, _insurer, _tipo_seguro, _created_at."""
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "fixtures"

    (pdf_dir / "zurich_auto_policy.pdf").write_bytes(b"%PDF-1.4 fake")

    fake_policy = _make_fake_policy("zurich", "auto")

    with (
        patch("policy_extractor.cli.ingest_pdf") as mock_ingest,
        patch("policy_extractor.cli.extract_policy", return_value=(fake_policy, _make_fake_usage(), 0)),
        patch("policy_extractor.cli._setup_db"),
        patch("policy_extractor.cli.SessionLocal"),
    ):
        mock_ingest.return_value = MagicMock()
        result = runner.invoke(
            app,
            ["batch-fixtures", str(pdf_dir), "--output", str(out_dir)],
        )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    fixture_files = list(out_dir.glob("*.json"))
    assert len(fixture_files) == 1

    data = json.loads(fixture_files[0].read_text(encoding="utf-8"))
    assert "_source_pdf" in data
    assert "_insurer" in data
    assert "_tipo_seguro" in data
    assert "_created_at" in data
    assert data["_source_pdf"] == "zurich_auto_policy.pdf"
    assert data["_insurer"] == "zurich"


# ---------------------------------------------------------------------------
# Test 3: fixture filename follows {insurer}_{type}_{seq:03d}.json pattern
# ---------------------------------------------------------------------------

def test_batch_fixtures_filename_naming_convention(tmp_path):
    """Fixture filenames follow {insurer}_{type}_{seq}.json e.g. zurich_auto_001.json."""
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "fixtures"

    (pdf_dir / "zurich_auto.pdf").write_bytes(b"%PDF-1.4 fake")

    fake_policy = _make_fake_policy("zurich", "auto")

    with (
        patch("policy_extractor.cli.ingest_pdf") as mock_ingest,
        patch("policy_extractor.cli.extract_policy", return_value=(fake_policy, _make_fake_usage(), 0)),
        patch("policy_extractor.cli._setup_db"),
        patch("policy_extractor.cli.SessionLocal"),
    ):
        mock_ingest.return_value = MagicMock()
        result = runner.invoke(
            app,
            ["batch-fixtures", str(pdf_dir), "--output", str(out_dir)],
        )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    fixture_files = list(out_dir.glob("*.json"))
    assert len(fixture_files) == 1
    assert fixture_files[0].name == "zurich_auto_001.json"


# ---------------------------------------------------------------------------
# Test 4: when extraction returns None, PDF is skipped (not a crash)
# ---------------------------------------------------------------------------

def test_batch_fixtures_skip_failed(tmp_path):
    """When extract_policy returns None, PDF is skipped with a warning, not a crash."""
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "fixtures"

    (pdf_dir / "zurich_auto.pdf").write_bytes(b"%PDF-1.4 fake")
    (pdf_dir / "qualitas_auto.pdf").write_bytes(b"%PDF-1.4 fake")

    call_count = {"n": 0}

    def mock_extract_with_fail(ingestion_result, model=None):
        n = call_count["n"]
        call_count["n"] += 1
        if n == 0:
            # First PDF fails
            return (None, None, 0)
        # Second PDF succeeds
        return (_make_fake_policy("qualitas", "auto"), _make_fake_usage(), 0)

    with (
        patch("policy_extractor.cli.ingest_pdf") as mock_ingest,
        patch("policy_extractor.cli.extract_policy", side_effect=mock_extract_with_fail),
        patch("policy_extractor.cli._setup_db"),
        patch("policy_extractor.cli.SessionLocal"),
    ):
        mock_ingest.return_value = MagicMock()
        result = runner.invoke(
            app,
            ["batch-fixtures", str(pdf_dir), "--output", str(out_dir)],
        )

    # Should not crash
    assert result.exit_code == 0, f"Command failed: {result.output}"
    # Only 1 fixture should be created (the one that succeeded)
    fixture_files = list(out_dir.glob("*.json"))
    assert len(fixture_files) == 1


# ---------------------------------------------------------------------------
# Test 5: --insurer-map flag applies correct insurer/type slugs
# ---------------------------------------------------------------------------

def test_batch_fixtures_insurer_map(tmp_path):
    """With --insurer-map, correct insurer slug is used in filename and metadata."""
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "fixtures"

    (pdf_dir / "doc_001.pdf").write_bytes(b"%PDF-1.4 fake")

    # insurer-map: maps the filename pattern to insurer/type
    insurer_map_file = tmp_path / "insurer_map.json"
    insurer_map_file.write_text(
        json.dumps({"doc_001": {"insurer": "mapfre", "type": "vida"}}),
        encoding="utf-8",
    )

    fake_policy = _make_fake_policy("mapfre", "vida")

    with (
        patch("policy_extractor.cli.ingest_pdf") as mock_ingest,
        patch("policy_extractor.cli.extract_policy", return_value=(fake_policy, _make_fake_usage(), 0)),
        patch("policy_extractor.cli._setup_db"),
        patch("policy_extractor.cli.SessionLocal"),
    ):
        mock_ingest.return_value = MagicMock()
        result = runner.invoke(
            app,
            [
                "batch-fixtures",
                str(pdf_dir),
                "--output",
                str(out_dir),
                "--insurer-map",
                str(insurer_map_file),
            ],
        )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    fixture_files = list(out_dir.glob("*.json"))
    assert len(fixture_files) == 1
    assert fixture_files[0].name == "mapfre_vida_001.json"

    data = json.loads(fixture_files[0].read_text(encoding="utf-8"))
    assert data["_insurer"] == "mapfre"
    assert data["_tipo_seguro"] == "vida"


# ---------------------------------------------------------------------------
# Test 6: PiiRedactor.redact() is called on each extracted policy
# ---------------------------------------------------------------------------

def test_batch_fixtures_pii_redaction_called(tmp_path):
    """PiiRedactor.redact() is called on each extracted policy before writing."""
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "fixtures"

    (pdf_dir / "zurich_auto.pdf").write_bytes(b"%PDF-1.4 fake")

    fake_policy = _make_fake_policy("zurich", "auto")
    raw_dump = fake_policy.model_dump.return_value

    with (
        patch("policy_extractor.cli.ingest_pdf") as mock_ingest,
        patch("policy_extractor.cli.extract_policy", return_value=(fake_policy, _make_fake_usage(), 0)),
        patch("policy_extractor.cli._setup_db"),
        patch("policy_extractor.cli.SessionLocal"),
        patch("policy_extractor.regression.pii_redactor.PiiRedactor.redact") as mock_redact,
    ):
        # Return something json-serializable from redact
        mock_redact.return_value = {**raw_dump, "_source_pdf": "zurich_auto.pdf",
                                    "_insurer": "zurich", "_tipo_seguro": "auto", "_created_at": "now"}
        mock_ingest.return_value = MagicMock()
        result = runner.invoke(
            app,
            ["batch-fixtures", str(pdf_dir), "--output", str(out_dir)],
        )

    assert result.exit_code == 0, f"Command failed: {result.output}"
    mock_redact.assert_called_once()
