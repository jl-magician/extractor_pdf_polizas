"""Unit tests for evaluation module — QAL-02, QAL-03.

Tests the evaluation engine that calls Sonnet to score Haiku extractions
for completeness, accuracy, and hallucination risk.

All tests mock anthropic.Anthropic to avoid live API calls.
"""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from policy_extractor.schemas.ingestion import IngestionResult, PageResult


# ---------------------------------------------------------------------------
# Mock helpers for Anthropic API response simulation
# ---------------------------------------------------------------------------

class MockToolUseBlock:
    type = "tool_use"

    def __init__(self, input_data):
        self.input = input_data


class MockUsage:
    input_tokens = 500
    output_tokens = 200


class MockEvalMessage:
    """Mock Anthropic Message for evaluation tool_use responses."""

    def __init__(self, input_data, model="claude-sonnet-4-5-20250514"):
        self.content = [MockToolUseBlock(input_data)]
        self.model = model
        self.stop_reason = "tool_use"
        self.usage = MockUsage()


# ---------------------------------------------------------------------------
# Sample eval tool response data
# ---------------------------------------------------------------------------

SAMPLE_EVAL_INPUT = {
    "completeness": 0.9,
    "accuracy": 0.85,
    "hallucination_risk": 0.1,
    "flags": [{"field": "prima_total", "issue": "Valor no verificable"}],
    "summary": "Extraccion de alta calidad con minimo riesgo de alucinacion.",
}

# Expected score: (0.9 + 0.85 + (1 - 0.1)) / 3 = (0.9 + 0.85 + 0.9) / 3 = 2.65 / 3 = 0.8833...
EXPECTED_SCORE = (0.9 + 0.85 + (1.0 - 0.1)) / 3.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ingestion_result():
    """Minimal IngestionResult for testing."""
    pages = [
        PageResult(
            page_num=1,
            text="POLIZA NUM: POL-2024-001\nAseguradora: GNP\nPrima: $5,000.00 MXN",
            classification="digital",
        )
    ]
    return IngestionResult(
        pages=pages,
        file_hash="abc123",
        file_path="test.pdf",
        total_pages=1,
        file_size_bytes=1024,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ocr_applied=False,
    )


@pytest.fixture
def sample_policy_extraction():
    """Minimal PolicyExtraction for testing."""
    from policy_extractor.schemas.poliza import PolicyExtraction
    return PolicyExtraction(
        numero_poliza="POL-2024-001",
        aseguradora="GNP",
        source_file_hash="abc123",
        model_id="claude-haiku-4-5-20251001",
        prompt_version="v1.0.0",
        extracted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def poliza_in_db(session, sample_policy_extraction):
    """Insert a Poliza row into the in-memory DB and return it."""
    from policy_extractor.storage.writer import upsert_policy
    poliza = upsert_policy(session, sample_policy_extraction)
    return poliza


# ---------------------------------------------------------------------------
# Tests: build_evaluation_tool()
# ---------------------------------------------------------------------------

class TestBuildEvaluationTool:
    def test_returns_dict_with_name(self):
        from policy_extractor.evaluation import build_evaluation_tool
        tool = build_evaluation_tool()
        assert tool["name"] == "evaluate_policy"

    def test_has_input_schema(self):
        from policy_extractor.evaluation import build_evaluation_tool
        tool = build_evaluation_tool()
        assert "input_schema" in tool
        assert "properties" in tool["input_schema"]

    def test_schema_has_required_properties(self):
        from policy_extractor.evaluation import build_evaluation_tool
        tool = build_evaluation_tool()
        props = tool["input_schema"]["properties"]
        required_keys = {"completeness", "accuracy", "hallucination_risk", "flags", "summary"}
        assert required_keys == set(props.keys())

    def test_schema_has_required_list_with_all_5_properties(self):
        from policy_extractor.evaluation import build_evaluation_tool
        tool = build_evaluation_tool()
        required = tool["input_schema"]["required"]
        assert set(required) == {"completeness", "accuracy", "hallucination_risk", "flags", "summary"}

    def test_numeric_scores_have_number_type(self):
        from policy_extractor.evaluation import build_evaluation_tool
        tool = build_evaluation_tool()
        props = tool["input_schema"]["properties"]
        for field in ("completeness", "accuracy", "hallucination_risk"):
            assert props[field]["type"] == "number", f"{field} should have type number"

    def test_flags_is_array(self):
        from policy_extractor.evaluation import build_evaluation_tool
        tool = build_evaluation_tool()
        props = tool["input_schema"]["properties"]
        assert props["flags"]["type"] == "array"

    def test_summary_is_string(self):
        from policy_extractor.evaluation import build_evaluation_tool
        tool = build_evaluation_tool()
        props = tool["input_schema"]["properties"]
        assert props["summary"]["type"] == "string"


# ---------------------------------------------------------------------------
# Tests: call_evaluation_api()
# ---------------------------------------------------------------------------

class TestCallEvaluationApi:
    def test_calls_messages_create(self):
        from policy_extractor.evaluation import call_evaluation_api, EVAL_MODEL_ID
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockEvalMessage(SAMPLE_EVAL_INPUT)

        call_evaluation_api(mock_client, "some text", '{"field": "val"}')

        assert mock_client.messages.create.called

    def test_uses_eval_model_id(self):
        from policy_extractor.evaluation import call_evaluation_api, EVAL_MODEL_ID
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockEvalMessage(SAMPLE_EVAL_INPUT)

        call_evaluation_api(mock_client, "some text", '{"field": "val"}')

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == EVAL_MODEL_ID

    def test_uses_forced_tool_choice(self):
        from policy_extractor.evaluation import call_evaluation_api, EVAL_TOOL_NAME
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockEvalMessage(SAMPLE_EVAL_INPUT)

        call_evaluation_api(mock_client, "some text", '{"field": "val"}')

        call_kwargs = mock_client.messages.create.call_args
        tool_choice = call_kwargs.kwargs["tool_choice"]
        assert tool_choice["type"] == "tool"
        assert tool_choice["name"] == EVAL_TOOL_NAME

    def test_user_message_contains_pdf_text_and_extracted_data(self):
        from policy_extractor.evaluation import call_evaluation_api
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockEvalMessage(SAMPLE_EVAL_INPUT)

        assembled = "PDF TEXT HERE"
        extraction = '{"numero_poliza": "POL-001"}'
        call_evaluation_api(mock_client, assembled, extraction)

        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[0]["content"]
        assert "PDF TEXT HERE" in user_content
        assert '{"numero_poliza": "POL-001"}' in user_content

    def test_includes_evaluation_tool_in_tools(self):
        from policy_extractor.evaluation import call_evaluation_api, EVAL_TOOL_NAME
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockEvalMessage(SAMPLE_EVAL_INPUT)

        call_evaluation_api(mock_client, "text", '{}')

        call_kwargs = mock_client.messages.create.call_args
        tools = call_kwargs.kwargs["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == EVAL_TOOL_NAME


# ---------------------------------------------------------------------------
# Tests: _parse_evaluation()
# ---------------------------------------------------------------------------

class TestParseEvaluation:
    def test_score_formula(self):
        """Score = (completeness + accuracy + (1 - hallucination_risk)) / 3."""
        from policy_extractor.evaluation import _parse_evaluation
        msg = MockEvalMessage(SAMPLE_EVAL_INPUT)
        result = _parse_evaluation(msg)
        assert abs(result.score - EXPECTED_SCORE) < 1e-9

    def test_evaluation_json_is_valid_json_string(self):
        from policy_extractor.evaluation import _parse_evaluation
        msg = MockEvalMessage(SAMPLE_EVAL_INPUT)
        result = _parse_evaluation(msg)
        # Must not raise
        parsed = json.loads(result.evaluation_json)
        assert "completeness" in parsed
        assert "accuracy" in parsed
        assert "hallucination_risk" in parsed
        assert "flags" in parsed
        assert "summary" in parsed

    def test_evaluation_json_uses_json_null_not_python_none(self):
        """Verify json.dumps is used — 'null' not 'None', 'true' not 'True'."""
        from policy_extractor.evaluation import _parse_evaluation
        input_with_none = {**SAMPLE_EVAL_INPUT, "extra": None}
        msg = MockEvalMessage(input_with_none)
        # The evaluation_json should serialize None as null
        result = _parse_evaluation(msg)
        # json.loads must work (no Python repr)
        json.loads(result.evaluation_json)
        # Should not contain Python repr artifacts
        assert "None" not in result.evaluation_json
        assert "True" not in result.evaluation_json

    def test_model_id_from_message(self):
        from policy_extractor.evaluation import _parse_evaluation
        msg = MockEvalMessage(SAMPLE_EVAL_INPUT, model="claude-sonnet-4-5-20250514")
        result = _parse_evaluation(msg)
        assert result.model_id == "claude-sonnet-4-5-20250514"

    def test_evaluated_at_is_utc_datetime(self):
        from policy_extractor.evaluation import _parse_evaluation
        msg = MockEvalMessage(SAMPLE_EVAL_INPUT)
        result = _parse_evaluation(msg)
        assert isinstance(result.evaluated_at, datetime)
        # Should be timezone-aware
        assert result.evaluated_at.tzinfo is not None

    def test_score_clamped_to_zero_one_range(self):
        """Scores out of range should be clamped."""
        from policy_extractor.evaluation import _parse_evaluation
        out_of_range = {
            "completeness": 1.5,  # > 1.0
            "accuracy": -0.2,     # < 0.0
            "hallucination_risk": 0.5,
            "flags": [],
            "summary": "test",
        }
        msg = MockEvalMessage(out_of_range)
        result = _parse_evaluation(msg)
        # completeness clamped to 1.0, accuracy clamped to 0.0
        expected_score = (1.0 + 0.0 + (1.0 - 0.5)) / 3.0
        assert abs(result.score - expected_score) < 1e-9


# ---------------------------------------------------------------------------
# Tests: evaluate_policy()
# ---------------------------------------------------------------------------

class TestEvaluatePolicy:
    def test_returns_evaluation_result_on_success(self, sample_ingestion_result, sample_policy_extraction):
        from policy_extractor.evaluation import evaluate_policy, EvaluationResult
        mock_message = MockEvalMessage(SAMPLE_EVAL_INPUT)

        with patch("anthropic.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.return_value = mock_message

            result = evaluate_policy(sample_ingestion_result, sample_policy_extraction)

        assert result is not None
        assert isinstance(result, EvaluationResult)
        assert abs(result.score - EXPECTED_SCORE) < 1e-9

    def test_returns_none_on_api_exception(self, sample_ingestion_result, sample_policy_extraction):
        with patch("anthropic.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("API down")

            from policy_extractor.evaluation import evaluate_policy
            result = evaluate_policy(sample_ingestion_result, sample_policy_extraction)

        assert result is None

    def test_evaluation_json_is_valid_json_string(self, sample_ingestion_result, sample_policy_extraction):
        from policy_extractor.evaluation import evaluate_policy
        mock_message = MockEvalMessage(SAMPLE_EVAL_INPUT)

        with patch("anthropic.Anthropic") as MockAnthropicClass:
            mock_client = MagicMock()
            MockAnthropicClass.return_value = mock_client
            mock_client.messages.create.return_value = mock_message

            result = evaluate_policy(sample_ingestion_result, sample_policy_extraction)

        assert result is not None
        # Must be deserializable
        parsed = json.loads(result.evaluation_json)
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Tests: update_evaluation_columns()
# ---------------------------------------------------------------------------

class TestUpdateEvaluationColumns:
    def test_sets_evaluation_columns_on_poliza(self, session, poliza_in_db):
        from policy_extractor.storage.writer import update_evaluation_columns
        from policy_extractor.storage.models import Poliza

        evaluated_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        eval_json = json.dumps({"completeness": 0.9, "accuracy": 0.85, "hallucination_risk": 0.1})

        update_evaluation_columns(
            session=session,
            numero_poliza="POL-2024-001",
            aseguradora="GNP",
            score=0.88,
            evaluation_json=eval_json,
            evaluated_at=evaluated_at,
            model_id="claude-sonnet-4-5-20250514",
        )

        updated = session.query(Poliza).filter_by(
            numero_poliza="POL-2024-001", aseguradora="GNP"
        ).first()
        assert updated.evaluation_score == pytest.approx(0.88)
        assert updated.evaluation_json == eval_json
        assert updated.evaluated_model_id == "claude-sonnet-4-5-20250514"
        assert updated.evaluated_at is not None

    def test_raises_value_error_for_nonexistent_poliza(self, session):
        from policy_extractor.storage.writer import update_evaluation_columns

        with pytest.raises(ValueError, match="Poliza not found"):
            update_evaluation_columns(
                session=session,
                numero_poliza="DOES-NOT-EXIST",
                aseguradora="Nobody",
                score=0.5,
                evaluation_json="{}",
                evaluated_at=datetime.now(timezone.utc),
                model_id="claude-sonnet-4-5-20250514",
            )

    def test_evaluation_json_stored_as_string(self, session, poliza_in_db):
        """evaluation_json column must be a string (not dict) after persistence."""
        from policy_extractor.storage.writer import update_evaluation_columns
        from policy_extractor.storage.models import Poliza

        eval_dict = {"completeness": 1.0, "accuracy": 1.0, "hallucination_risk": 0.0,
                     "flags": [], "summary": "Perfecto"}
        eval_json_str = json.dumps(eval_dict, ensure_ascii=False)

        update_evaluation_columns(
            session=session,
            numero_poliza="POL-2024-001",
            aseguradora="GNP",
            score=1.0,
            evaluation_json=eval_json_str,
            evaluated_at=datetime.now(timezone.utc),
            model_id="claude-sonnet-4-5-20250514",
        )

        updated = session.query(Poliza).filter_by(
            numero_poliza="POL-2024-001", aseguradora="GNP"
        ).first()
        # Must be a string — not a dict
        assert isinstance(updated.evaluation_json, str)
        # And must be valid JSON
        parsed = json.loads(updated.evaluation_json)
        assert parsed["completeness"] == 1.0


# ---------------------------------------------------------------------------
# Tests: CLI integration — --evaluate flag on extract command
# ---------------------------------------------------------------------------

class TestCliEvaluateFlag:
    """Integration tests confirming --evaluate triggers evaluate_policy."""

    def test_evaluate_called_with_flag(self, tmp_path):
        """With --evaluate flag, evaluate_policy and update_evaluation_columns are called."""
        from typer.testing import CliRunner
        from policy_extractor.cli import app

        runner = CliRunner()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_usage = MagicMock()
        mock_usage.input_tokens = 500
        mock_usage.output_tokens = 200

        mock_eval_result = MagicMock()
        mock_eval_result.score = 0.88
        mock_eval_result.evaluation_json = '{"completeness": 0.9}'
        mock_eval_result.evaluated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_eval_result.model_id = "claude-sonnet-4-5-20250514"
        mock_eval_result.usage = mock_usage

        mock_policy = MagicMock()
        mock_policy.numero_poliza = "POL-001"
        mock_policy.aseguradora = "GNP"
        mock_policy.model_dump_json = MagicMock(return_value='{"numero_poliza": "POL-001"}')

        mock_usage_extraction = MagicMock()
        mock_usage_extraction.input_tokens = 1000
        mock_usage_extraction.output_tokens = 300

        with patch("policy_extractor.cli.init_db"), \
             patch("policy_extractor.cli.SessionLocal") as mock_session_cls, \
             patch("policy_extractor.cli.compute_file_hash", return_value="abc123"), \
             patch("policy_extractor.cli.is_already_extracted", return_value=False), \
             patch("policy_extractor.cli.ingest_pdf") as mock_ingest, \
             patch("policy_extractor.cli.extract_policy", return_value=(mock_policy, mock_usage_extraction, 0)), \
             patch("policy_extractor.storage.writer.upsert_policy") as mock_upsert, \
             patch("policy_extractor.evaluation.evaluate_policy", return_value=mock_eval_result) as mock_evaluate, \
             patch("policy_extractor.storage.writer.update_evaluation_columns") as mock_update_eval:

            mock_session_cls.return_value = MagicMock()
            mock_ingest.return_value = MagicMock()

            result = runner.invoke(app, ["extract", str(pdf_file), "--evaluate"])

        assert mock_evaluate.called, "evaluate_policy should have been called"
        assert mock_update_eval.called, "update_evaluation_columns should have been called"

    def test_evaluate_not_called_without_flag(self, tmp_path):
        """Without --evaluate flag, evaluate_policy is NOT called."""
        from typer.testing import CliRunner
        from policy_extractor.cli import app

        runner = CliRunner()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_policy = MagicMock()
        mock_policy.numero_poliza = "POL-001"
        mock_policy.aseguradora = "GNP"
        mock_policy.model_dump_json = MagicMock(return_value='{"numero_poliza": "POL-001"}')

        mock_usage_extraction = MagicMock()
        mock_usage_extraction.input_tokens = 1000
        mock_usage_extraction.output_tokens = 300

        with patch("policy_extractor.cli.init_db"), \
             patch("policy_extractor.cli.SessionLocal") as mock_session_cls, \
             patch("policy_extractor.cli.compute_file_hash", return_value="abc123"), \
             patch("policy_extractor.cli.is_already_extracted", return_value=False), \
             patch("policy_extractor.cli.ingest_pdf") as mock_ingest, \
             patch("policy_extractor.cli.extract_policy", return_value=(mock_policy, mock_usage_extraction, 0)), \
             patch("policy_extractor.storage.writer.upsert_policy"), \
             patch("policy_extractor.evaluation.evaluate_policy") as mock_evaluate:

            mock_session_cls.return_value = MagicMock()
            mock_ingest.return_value = MagicMock()

            runner.invoke(app, ["extract", str(pdf_file)])

        assert not mock_evaluate.called, "evaluate_policy should NOT be called without --evaluate flag"


# ---------------------------------------------------------------------------
# Tests: Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_eval_model_id_is_sonnet(self):
        from policy_extractor.evaluation import EVAL_MODEL_ID
        assert EVAL_MODEL_ID == "claude-sonnet-4-5-20250514"

    def test_low_score_threshold_is_0_7(self):
        from policy_extractor.evaluation import LOW_SCORE_THRESHOLD
        assert LOW_SCORE_THRESHOLD == 0.7

    def test_eval_tool_name(self):
        from policy_extractor.evaluation import EVAL_TOOL_NAME
        assert EVAL_TOOL_NAME == "evaluate_policy"
