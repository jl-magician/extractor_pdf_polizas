"""Golden dataset regression tests — run with `pytest -m regression`.

Each fixture JSON in tests/fixtures/golden/ defines expected extraction
output for a real PDF. The test re-runs extraction and compares field-by-field.
Tests skip gracefully if the corresponding real PDF is not present locally.
"""
import json
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
PDFS_DIR = Path(__file__).parent.parent / "pdfs-to-test"


def _discover_fixtures():
    """Discover fixture JSON files at collection time. Returns [] if dir empty/missing."""
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


@pytest.mark.regression
@pytest.mark.parametrize("fixture_path", _discover_fixtures(), ids=lambda p: p.stem)
def test_regression_fixture(fixture_path, session):
    """Compare live extraction against golden fixture for a single PDF."""
    from policy_extractor.extraction import extract_policy
    from policy_extractor.ingestion import ingest_pdf
    from policy_extractor.regression.field_differ import FieldDiffer

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Locate the real PDF
    source_pdf = fixture.get("_source_pdf")
    if source_pdf is None:
        # Fallback: derive from fixture filename pattern golden_{insurer}_{type}.json
        pytest.fail(f"Fixture {fixture_path.name} missing '_source_pdf' key")

    pdf_path = PDFS_DIR / source_pdf
    if not pdf_path.exists():
        pytest.skip(f"Real PDF not found: {pdf_path} (add to pdfs-to-test/)")

    # Run extraction
    ingestion_result = ingest_pdf(pdf_path, session=session)
    policy, _usage, _retries = extract_policy(ingestion_result)
    assert policy is not None, f"Extraction returned None for {source_pdf}"

    # Compare field-by-field
    actual = policy.model_dump(mode="json")
    differ = FieldDiffer(fixture, actual)
    drift = differ.compare()
    assert not drift.has_failures, f"\nRegression drift in {fixture_path.stem}:\n{drift.format_table()}"


@pytest.mark.parametrize("fixture_path", _discover_fixtures(), ids=lambda p: p.stem)
def test_fixture_format_valid(fixture_path):
    """Validate that fixture JSON has required structure (not regression-marked, runs in default suite)."""
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert "_source_pdf" in fixture, f"{fixture_path.name} missing _source_pdf"
    assert "numero_poliza" in fixture, f"{fixture_path.name} missing numero_poliza"
    assert "aseguradora" in fixture, f"{fixture_path.name} missing aseguradora"
    # PII fields should be redacted
    if "nombre_contratante" in fixture:
        assert fixture["nombre_contratante"] == "[REDACTED]", \
            f"{fixture_path.name} has unredacted nombre_contratante"
