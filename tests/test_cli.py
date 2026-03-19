"""Tests for CLI helper utilities and CLI commands (Phase 4 + Phase 5 Plan 02).

Tests 1-5: Unit tests for estimate_cost and is_already_extracted (passing from Plan 01).
Tests 6-12: Full CLI command tests using typer.testing.CliRunner with mocked pipeline.
Tests 13-20: Export, import, and serve subcommand tests (Plan 02).
"""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from policy_extractor.cli import app
from policy_extractor.cli_helpers import estimate_cost, is_already_extracted
from policy_extractor.schemas.poliza import PolicyExtraction
from policy_extractor.storage.models import Asegurado, Base, Cobertura, Poliza

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


# ---------------------------------------------------------------------------
# Tests — export/import/serve subcommands (Plan 02)
# ---------------------------------------------------------------------------


@pytest.fixture
def mem_engine():
    """In-memory SQLite engine for CLI export/import tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def seeded_session(mem_engine):
    """Session with one Poliza row (AXA, vida) pre-inserted."""
    with Session(mem_engine) as session:
        poliza = Poliza(
            numero_poliza="POL-AXA-001",
            aseguradora="AXA",
            tipo_seguro="vida",
            nombre_agente="Juan Lopez",
            campos_adicionales={"confianza": {}},
        )
        aseg = Asegurado(tipo="persona", nombre_descripcion="Carlos Ruiz")
        cob = Cobertura(nombre_cobertura="Muerte", moneda="MXN")
        poliza.asegurados.append(aseg)
        poliza.coberturas.append(cob)
        session.add(poliza)
        session.commit()
        yield session


def _make_mock_session_cls(mem_engine):
    """Return a mock SessionLocal class that yields real sessions against mem_engine."""
    from sqlalchemy.orm import sessionmaker
    RealSession = sessionmaker(bind=mem_engine)

    class FakeSessionCls:
        _instance = None

        def __call__(self):
            self._instance = RealSession()
            return self._instance

        def configure(self, **kwargs):
            pass

    return FakeSessionCls()


def test_export_empty_db(mem_engine):
    """export with empty DB outputs empty JSON array."""
    mock_session_factory = _make_mock_session_cls(mem_engine)

    with (
        patch("policy_extractor.cli.init_db"),
        patch("policy_extractor.cli.SessionLocal", mock_session_factory),
    ):
        result = runner.invoke(app, ["export"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "[]"


def test_export_with_data(mem_engine, seeded_session):
    """export with seeded DB returns JSON array with policy including nested objects."""
    mock_session_factory = _make_mock_session_cls(mem_engine)

    with (
        patch("policy_extractor.cli.init_db"),
        patch("policy_extractor.cli.SessionLocal", mock_session_factory),
    ):
        result = runner.invoke(app, ["export"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["numero_poliza"] == "POL-AXA-001"
    assert data[0]["aseguradora"] == "AXA"
    assert "asegurados" in data[0]
    assert "coberturas" in data[0]


def test_export_filter_insurer(mem_engine, seeded_session):
    """export --insurer filters to matching aseguradora only."""
    mock_session_factory = _make_mock_session_cls(mem_engine)

    with (
        patch("policy_extractor.cli.init_db"),
        patch("policy_extractor.cli.SessionLocal", mock_session_factory),
    ):
        # Match filter
        result_match = runner.invoke(app, ["export", "--insurer", "AXA"])
        # No-match filter
        result_no_match = runner.invoke(app, ["export", "--insurer", "MAPFRE"])

    assert result_match.exit_code == 0
    data_match = json.loads(result_match.output)
    assert len(data_match) == 1

    assert result_no_match.exit_code == 0
    data_no_match = json.loads(result_no_match.output)
    assert len(data_no_match) == 0


def test_export_to_file(tmp_path, mem_engine, seeded_session):
    """export --output writes JSON to file instead of stdout."""
    out_file = tmp_path / "polizas.json"
    mock_session_factory = _make_mock_session_cls(mem_engine)

    with (
        patch("policy_extractor.cli.init_db"),
        patch("policy_extractor.cli.SessionLocal", mock_session_factory),
    ):
        result = runner.invoke(app, ["export", "--output", str(out_file)])

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1


def test_import_json_array(tmp_path, mem_engine):
    """import loads a JSON array into DB, creating Poliza rows."""
    records = [
        {"numero_poliza": "IMP-001", "aseguradora": "MAPFRE"},
        {"numero_poliza": "IMP-002", "aseguradora": "GNP"},
    ]
    json_file = tmp_path / "policies.json"
    json_file.write_text(json.dumps(records), encoding="utf-8")

    mock_session_factory = _make_mock_session_cls(mem_engine)

    with (
        patch("policy_extractor.cli.init_db"),
        patch("policy_extractor.cli.SessionLocal", mock_session_factory),
    ):
        result = runner.invoke(app, ["import", str(json_file)])

    assert result.exit_code == 0, result.output
    assert "2" in result.output  # "Imported 2 policy/policies"

    # Verify DB state
    with Session(mem_engine) as s:
        count = s.query(Poliza).count()
    assert count == 2


def test_import_single_object(tmp_path, mem_engine):
    """import handles single-object JSON (wraps in list)."""
    record = {"numero_poliza": "SINGLE-001", "aseguradora": "Qualitas"}
    json_file = tmp_path / "single.json"
    json_file.write_text(json.dumps(record), encoding="utf-8")

    mock_session_factory = _make_mock_session_cls(mem_engine)

    with (
        patch("policy_extractor.cli.init_db"),
        patch("policy_extractor.cli.SessionLocal", mock_session_factory),
    ):
        result = runner.invoke(app, ["import", str(json_file)])

    assert result.exit_code == 0, result.output
    assert "1" in result.output

    with Session(mem_engine) as s:
        count = s.query(Poliza).count()
    assert count == 1


def test_import_export_roundtrip(tmp_path, mem_engine, seeded_session):
    """Round-trip: export then import produces equivalent DB state."""
    mock_session_factory = _make_mock_session_cls(mem_engine)
    out_file = tmp_path / "export.json"

    # Export existing seeded data
    with (
        patch("policy_extractor.cli.init_db"),
        patch("policy_extractor.cli.SessionLocal", mock_session_factory),
    ):
        export_result = runner.invoke(app, ["export", "--output", str(out_file)])

    assert export_result.exit_code == 0, export_result.output
    assert out_file.exists()

    # Fresh engine for import
    fresh_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(fresh_engine)
    fresh_factory = _make_mock_session_cls(fresh_engine)

    with (
        patch("policy_extractor.cli.init_db"),
        patch("policy_extractor.cli.SessionLocal", fresh_factory),
    ):
        import_result = runner.invoke(app, ["import", str(out_file)])

    assert import_result.exit_code == 0, import_result.output

    # Verify the imported data
    with Session(fresh_engine) as s:
        polizas = s.query(Poliza).all()
    assert len(polizas) == 1
    assert polizas[0].numero_poliza == "POL-AXA-001"
    assert polizas[0].aseguradora == "AXA"


def test_serve_subcommand_registered():
    """serve subcommand is registered in the Typer app (without actually starting uvicorn)."""
    # List registered commands
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.output


# ---------------------------------------------------------------------------
# Tests -- rate limit retry (Phase 9)
# ---------------------------------------------------------------------------

import anthropic as _anthropic
from policy_extractor.extraction.client import extract_with_retry

PATCH_CALL_API = "policy_extractor.extraction.client.call_extraction_api"
PATCH_TIME = "policy_extractor.extraction.client.time"
PATCH_RANDOM = "policy_extractor.extraction.client.random"


def _make_mock_message():
    """Return a mock anthropic.types.Message with valid tool_use content."""
    msg = MagicMock()
    content_block = MagicMock()
    content_block.type = "tool_use"
    content_block.input = {
        "numero_poliza": "TEST-001",
        "aseguradora": "Test",
    }
    msg.content = [content_block]
    msg.model = "claude-haiku-4-5-20251001"
    msg.usage = MagicMock()
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    return msg


def _make_rate_limit_error():
    return _anthropic.RateLimitError(
        message="rate limited",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )


def _make_internal_server_error():
    return _anthropic.InternalServerError(
        message="server error",
        response=MagicMock(status_code=500, headers={}),
        body=None,
    )


def _make_connection_error():
    return _anthropic.APIConnectionError(request=MagicMock())


def _make_bad_request_error():
    return _anthropic.BadRequestError(
        message="bad request",
        response=MagicMock(status_code=400, headers={}),
        body=None,
    )


def test_rate_limit_retry_succeeds():
    """RateLimitError on first call; second call succeeds. Returns valid result with retry count 1."""
    mock_client = MagicMock(spec=_anthropic.Anthropic)
    mock_message = _make_mock_message()

    with (
        patch(PATCH_CALL_API, side_effect=[_make_rate_limit_error(), mock_message]),
        patch(PATCH_TIME) as mock_time,
        patch(PATCH_RANDOM) as mock_random,
    ):
        mock_time.sleep = MagicMock()
        mock_random.uniform = MagicMock(return_value=0.5)

        result = extract_with_retry(
            mock_client, "text", "hash123", "claude-haiku-4-5-20251001"
        )

    assert result is not None, "Expected a result tuple, got None"
    assert len(result) == 4, f"Expected 4-tuple, got {len(result)}-tuple"
    policy, raw_response, usage, rl_retries = result
    assert policy is not None
    assert rl_retries == 1, f"Expected 1 rate limit retry, got {rl_retries}"
    mock_time.sleep.assert_called_once()


def test_rate_limit_retry_exhausted():
    """RateLimitError on all 4 attempts exhausts retries; returns None (caught by except Exception)."""
    mock_client = MagicMock(spec=_anthropic.Anthropic)

    with (
        patch(
            PATCH_CALL_API,
            side_effect=[
                _make_rate_limit_error(),
                _make_rate_limit_error(),
                _make_rate_limit_error(),
                _make_rate_limit_error(),
            ],
        ),
        patch(PATCH_TIME) as mock_time,
        patch(PATCH_RANDOM) as mock_random,
    ):
        mock_time.sleep = MagicMock()
        mock_random.uniform = MagicMock(return_value=0.5)

        result = extract_with_retry(
            mock_client, "text", "hash123", "claude-haiku-4-5-20251001"
        )

    assert result is None, "Expected None after exhausting all retries"
    # sleep called 3 times (one per backoff wait, before 4th attempt which raises)
    assert mock_time.sleep.call_count == 3


def test_no_retry_on_4xx():
    """BadRequestError (4xx non-429) must NOT trigger retry — only 1 API call made."""
    mock_client = MagicMock(spec=_anthropic.Anthropic)

    with (
        patch(PATCH_CALL_API, side_effect=[_make_bad_request_error()]) as mock_api,
        patch(PATCH_TIME) as mock_time,
        patch(PATCH_RANDOM) as mock_random,
    ):
        mock_time.sleep = MagicMock()
        mock_random.uniform = MagicMock(return_value=0.5)

        result = extract_with_retry(
            mock_client, "text", "hash123", "claude-haiku-4-5-20251001"
        )

    assert result is None, "Expected None for non-retryable 4xx error"
    assert mock_api.call_count == 1, f"Expected 1 call, got {mock_api.call_count}"
    mock_time.sleep.assert_not_called()


def test_rate_limit_retry_with_server_error():
    """InternalServerError (5xx) on first call; second call succeeds. Retry count = 1."""
    mock_client = MagicMock(spec=_anthropic.Anthropic)
    mock_message = _make_mock_message()

    with (
        patch(
            PATCH_CALL_API,
            side_effect=[_make_internal_server_error(), mock_message],
        ),
        patch(PATCH_TIME) as mock_time,
        patch(PATCH_RANDOM) as mock_random,
    ):
        mock_time.sleep = MagicMock()
        mock_random.uniform = MagicMock(return_value=0.5)

        result = extract_with_retry(
            mock_client, "text", "hash123", "claude-haiku-4-5-20251001"
        )

    assert result is not None, "Expected valid result after 5xx retry"
    policy, raw_response, usage, rl_retries = result
    assert policy is not None
    assert rl_retries == 1, f"Expected 1 retry, got {rl_retries}"
    mock_time.sleep.assert_called_once()


def test_rate_limit_retry_with_connection_error():
    """APIConnectionError on first call; second call succeeds. Retry count = 1."""
    mock_client = MagicMock(spec=_anthropic.Anthropic)
    mock_message = _make_mock_message()

    with (
        patch(
            PATCH_CALL_API,
            side_effect=[_make_connection_error(), mock_message],
        ),
        patch(PATCH_TIME) as mock_time,
        patch(PATCH_RANDOM) as mock_random,
    ):
        mock_time.sleep = MagicMock()
        mock_random.uniform = MagicMock(return_value=0.5)

        result = extract_with_retry(
            mock_client, "text", "hash123", "claude-haiku-4-5-20251001"
        )

    assert result is not None, "Expected valid result after connection error retry"
    policy, raw_response, usage, rl_retries = result
    assert policy is not None
    assert rl_retries == 1, f"Expected 1 retry, got {rl_retries}"
    mock_time.sleep.assert_called_once()
