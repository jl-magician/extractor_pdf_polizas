"""Tests for auto-evaluation hook — Phase 16 Plan 02 (QA-02, QA-03).

Tests for _auto_evaluate_batch() in policy_extractor/api/upload.py:
- Threshold gate: does NOT trigger when < 10 successful extractions
- Sample rate: evaluates ~EVAL_SAMPLE_PERCENT% of successful records
- Settings override: respects patched EVAL_SAMPLE_PERCENT
- Swap warning append: appends without overwriting existing validation_warnings
- PDF retention check: skips polizas whose retained PDF is missing
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from policy_extractor.storage.models import Base, Poliza


# ---------------------------------------------------------------------------
# In-memory DB helpers
# ---------------------------------------------------------------------------


def make_session():
    """Create an in-memory SQLite session with all tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def insert_poliza(session, poliza_id: int, numero_poliza: str = "POL-001", aseguradora: str = "GNP") -> Poliza:
    """Insert a minimal Poliza row with a given integer id."""
    p = Poliza(
        id=poliza_id,
        numero_poliza=numero_poliza,
        aseguradora=aseguradora,
        source_file_hash=f"hash-{poliza_id}",
        model_id="claude-haiku-4-5-20251001",
        prompt_version="v2.0.0",
        extracted_at=datetime.now(timezone.utc),
        validation_warnings=None,
    )
    session.add(p)
    session.commit()
    return p


def make_summaries(count: int, start_id: int = 1, status: str = "complete") -> list[dict]:
    """Build a list of batch summary dicts."""
    return [
        {
            "filename": f"file_{i}.pdf",
            "status": status,
            "poliza_id": start_id + i - 1,
            "numero_poliza": f"POL-{start_id + i - 1:03d}",
            "aseguradora": "GNP",
            "error": None,
        }
        for i in range(1, count + 1)
    ]


# ---------------------------------------------------------------------------
# Tests: _auto_evaluate_batch threshold gate (< 10 → no-op)
# ---------------------------------------------------------------------------


class TestAutoEvaluateBatchThreshold:
    def test_does_not_call_evaluate_when_fewer_than_10_successful(self):
        """With 9 successful records, evaluate_policy must NOT be called."""
        from policy_extractor.api.upload import _auto_evaluate_batch

        session = make_session()
        summaries = make_summaries(9)

        # Patch evaluate_policy where it is lazy-imported inside _auto_evaluate_batch
        with patch("policy_extractor.evaluation.evaluate_policy") as mock_eval:
            _auto_evaluate_batch(session, summaries, model=None)
            assert not mock_eval.called, "evaluate_policy should NOT be called for < 10 records"

        session.close()

    def test_does_not_call_evaluate_with_zero_successful(self):
        """With 0 successful records, evaluate_policy must NOT be called."""
        from policy_extractor.api.upload import _auto_evaluate_batch

        session = make_session()
        summaries = make_summaries(5, status="failed")

        with patch("policy_extractor.evaluation.evaluate_policy") as mock_eval:
            _auto_evaluate_batch(session, summaries, model=None)
            assert not mock_eval.called

        session.close()


# ---------------------------------------------------------------------------
# Tests: _auto_evaluate_batch sample rate
# ---------------------------------------------------------------------------


class TestAutoEvaluateBatchSampleRate:
    def test_evaluates_approximately_20_percent_of_records_when_gte_10(self, tmp_path):
        """With 20 successful records and EVAL_SAMPLE_PERCENT=20, ~4 calls expected."""
        from policy_extractor.api.upload import _auto_evaluate_batch

        session = make_session()
        summaries = make_summaries(20)

        # Insert polizas and create retained PDFs in tmp_path
        for s in summaries:
            insert_poliza(session, s["poliza_id"], s["numero_poliza"], s["aseguradora"])

        # Create dummy PDF files for each poliza
        pdfs_dir = tmp_path / "pdfs"
        pdfs_dir.mkdir()
        for s in summaries:
            (pdfs_dir / f"{s['poliza_id']}.pdf").write_bytes(b"%PDF-1.4 fake")

        mock_eval_result = MagicMock()
        mock_eval_result.score = 0.85
        mock_eval_result.evaluation_json = json.dumps({
            "completeness": 0.9, "accuracy": 0.8, "hallucination_risk": 0.1,
            "flags": [], "summary": "OK", "campos_swap_suggestions": []
        })
        mock_eval_result.evaluated_at = datetime.now(timezone.utc)
        mock_eval_result.model_id = "claude-sonnet-4-5-20250514"

        call_count = 0

        def fake_evaluate(ingestion_result, policy_schema, model=None):
            nonlocal call_count
            call_count += 1
            return mock_eval_result

        with patch("policy_extractor.api.upload.PDFS_RETENTION_DIR", pdfs_dir), \
             patch("policy_extractor.evaluation.evaluate_policy", side_effect=fake_evaluate), \
             patch("policy_extractor.ingestion.ingest_pdf") as mock_ingest, \
             patch("policy_extractor.storage.writer.update_evaluation_columns"), \
             patch("policy_extractor.storage.writer.orm_to_schema") as mock_orm_to_schema:
            mock_ingest.return_value = MagicMock()
            mock_orm_to_schema.return_value = MagicMock()
            mock_orm_to_schema.return_value.model_dump_json = MagicMock(return_value='{}')

            _auto_evaluate_batch(session, summaries, model=None)

        # With 20 records and 20% sample, expect ~4 calls (allow ±2 due to rounding/randomness)
        assert 2 <= call_count <= 6, f"Expected ~4 evaluate calls, got {call_count}"

        session.close()

    def test_respects_eval_sample_percent_setting(self, tmp_path):
        """With EVAL_SAMPLE_PERCENT=50 and 10 records, ~5 evaluations expected."""
        from policy_extractor.api.upload import _auto_evaluate_batch
        from policy_extractor.config import settings

        session = make_session()
        summaries = make_summaries(10)

        for s in summaries:
            insert_poliza(session, s["poliza_id"], s["numero_poliza"], s["aseguradora"])

        pdfs_dir = tmp_path / "pdfs"
        pdfs_dir.mkdir()
        for s in summaries:
            (pdfs_dir / f"{s['poliza_id']}.pdf").write_bytes(b"%PDF-1.4 fake")

        mock_eval_result = MagicMock()
        mock_eval_result.score = 0.85
        mock_eval_result.evaluation_json = json.dumps({
            "completeness": 0.9, "accuracy": 0.8, "hallucination_risk": 0.1,
            "flags": [], "summary": "OK", "campos_swap_suggestions": []
        })
        mock_eval_result.evaluated_at = datetime.now(timezone.utc)
        mock_eval_result.model_id = "claude-sonnet-4-5-20250514"

        call_count = 0

        def fake_evaluate(ingestion_result, policy_schema, model=None):
            nonlocal call_count
            call_count += 1
            return mock_eval_result

        original_percent = settings.EVAL_SAMPLE_PERCENT
        settings.EVAL_SAMPLE_PERCENT = 50

        try:
            with patch("policy_extractor.api.upload.PDFS_RETENTION_DIR", pdfs_dir), \
                 patch("policy_extractor.evaluation.evaluate_policy", side_effect=fake_evaluate), \
                 patch("policy_extractor.ingestion.ingest_pdf") as mock_ingest, \
                 patch("policy_extractor.storage.writer.update_evaluation_columns"), \
                 patch("policy_extractor.storage.writer.orm_to_schema") as mock_orm_to_schema:
                mock_ingest.return_value = MagicMock()
                mock_orm_to_schema.return_value = MagicMock()
                mock_orm_to_schema.return_value.model_dump_json = MagicMock(return_value='{}')

                _auto_evaluate_batch(session, summaries, model=None)
        finally:
            settings.EVAL_SAMPLE_PERCENT = original_percent

        # 50% of 10 = 5; allow small range
        assert 3 <= call_count <= 7, f"Expected ~5 evaluate calls, got {call_count}"

        session.close()


# ---------------------------------------------------------------------------
# Tests: swap warnings appended without overwriting existing warnings
# ---------------------------------------------------------------------------


class TestSwapWarningAppend:
    def test_swap_warnings_appended_not_overwritten(self, tmp_path):
        """Existing validation_warnings must be preserved; swap warnings appended."""
        from policy_extractor.api.upload import _auto_evaluate_batch

        session = make_session()
        summaries = make_summaries(10)

        # Insert polizas with pre-existing validation_warnings on first one
        for s in summaries:
            p = insert_poliza(session, s["poliza_id"], s["numero_poliza"], s["aseguradora"])

        # Set pre-existing warning on poliza 1
        poliza_1 = session.get(Poliza, 1)
        poliza_1.validation_warnings = ["EXISTING: some financial warning"]
        session.commit()

        pdfs_dir = tmp_path / "pdfs"
        pdfs_dir.mkdir()
        for s in summaries:
            (pdfs_dir / f"{s['poliza_id']}.pdf").write_bytes(b"%PDF-1.4 fake")

        swap_eval_json = json.dumps({
            "completeness": 0.9, "accuracy": 0.8, "hallucination_risk": 0.1,
            "flags": [], "summary": "OK",
            "campos_swap_suggestions": [
                {
                    "source_key": "prima_neta",
                    "target_key": "derechos",
                    "suspicious_value": "250.00",
                    "reason": "Monto en clave incorrecta",
                }
            ]
        })
        mock_eval_result = MagicMock()
        mock_eval_result.score = 0.85
        mock_eval_result.evaluation_json = swap_eval_json
        mock_eval_result.evaluated_at = datetime.now(timezone.utc)
        mock_eval_result.model_id = "claude-sonnet-4-5-20250514"

        # Force sample to always include poliza 1 by setting sample_pct=100
        from policy_extractor.config import settings
        original_percent = settings.EVAL_SAMPLE_PERCENT
        settings.EVAL_SAMPLE_PERCENT = 100

        try:
            with patch("policy_extractor.api.upload.PDFS_RETENTION_DIR", pdfs_dir), \
                 patch("policy_extractor.evaluation.evaluate_policy", return_value=mock_eval_result), \
                 patch("policy_extractor.ingestion.ingest_pdf") as mock_ingest, \
                 patch("policy_extractor.storage.writer.update_evaluation_columns"), \
                 patch("policy_extractor.storage.writer.orm_to_schema") as mock_orm_to_schema:
                mock_ingest.return_value = MagicMock()
                mock_orm_to_schema.return_value = MagicMock()
                mock_orm_to_schema.return_value.model_dump_json = MagicMock(return_value='{}')

                _auto_evaluate_batch(session, summaries, model=None)
        finally:
            settings.EVAL_SAMPLE_PERCENT = original_percent

        # Verify poliza 1 has both the pre-existing warning AND the swap warning
        session.refresh(poliza_1)
        warnings = poliza_1.validation_warnings or []
        assert any("EXISTING" in w for w in warnings), "Pre-existing warning must be preserved"
        assert any("SWAP" in w for w in warnings), "Swap warning must be appended"

        session.close()


# ---------------------------------------------------------------------------
# Tests: skip polizas without retained PDF
# ---------------------------------------------------------------------------


class TestSkipMissingPdf:
    def test_skips_poliza_when_retained_pdf_missing(self, tmp_path):
        """Polizas without a retained PDF at PDFS_RETENTION_DIR/{id}.pdf are skipped."""
        from policy_extractor.api.upload import _auto_evaluate_batch

        session = make_session()
        summaries = make_summaries(10)

        for s in summaries:
            insert_poliza(session, s["poliza_id"], s["numero_poliza"], s["aseguradora"])

        # Do NOT create any PDF files — pdfs_dir is empty
        pdfs_dir = tmp_path / "pdfs"
        pdfs_dir.mkdir()

        with patch("policy_extractor.api.upload.PDFS_RETENTION_DIR", pdfs_dir), \
             patch("policy_extractor.evaluation.evaluate_policy") as mock_eval, \
             patch("policy_extractor.ingestion.ingest_pdf") as mock_ingest, \
             patch("policy_extractor.storage.writer.update_evaluation_columns"), \
             patch("policy_extractor.storage.writer.orm_to_schema"):
            mock_ingest.return_value = MagicMock()

            _auto_evaluate_batch(session, summaries, model=None)

        # evaluate_policy should never be called because no PDFs exist
        assert not mock_eval.called, "evaluate_policy should be skipped when PDF is missing"

        session.close()
