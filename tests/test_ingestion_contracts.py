"""Tests for Task 1: Pydantic ingestion models, SQLAlchemy cache model, config extensions.

These tests are written FIRST (TDD RED phase) before the implementation exists.
"""
from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session


class TestPageResult:
    def test_valid_digital_page_result(self):
        from policy_extractor.schemas.ingestion import PageResult

        pr = PageResult(page_num=1, text="Some text here", classification="digital")
        assert pr.page_num == 1
        assert pr.classification == "digital"

    def test_valid_scanned_page_result(self):
        from policy_extractor.schemas.ingestion import PageResult

        pr = PageResult(page_num=2, text="", classification="scanned")
        assert pr.classification == "scanned"

    def test_invalid_classification_raises(self):
        from policy_extractor.schemas.ingestion import PageResult

        with pytest.raises(ValidationError):
            PageResult(page_num=1, text="text", classification="unknown")

    def test_only_digital_or_scanned_accepted(self):
        from policy_extractor.schemas.ingestion import PageResult

        for valid in ("digital", "scanned"):
            pr = PageResult(page_num=1, text="x", classification=valid)
            assert pr.classification == valid

        for invalid in ("image", "text", "mixed", ""):
            with pytest.raises(ValidationError):
                PageResult(page_num=1, text="x", classification=invalid)


class TestIngestionResult:
    def test_instantiation_with_valid_fields(self):
        from policy_extractor.schemas.ingestion import IngestionResult, PageResult

        ir = IngestionResult(
            file_hash="a" * 64,
            file_path="/some/path/policy.pdf",
            total_pages=3,
            pages=[PageResult(page_num=1, text="hello", classification="digital")],
            file_size_bytes=12345,
            created_at=datetime(2026, 3, 18, 12, 0, 0),
            ocr_applied=False,
            ocr_language="spa",
            from_cache=False,
        )
        assert ir.total_pages == 3
        assert len(ir.pages) == 1
        assert ir.from_cache is False

    def test_serialized_to_dict(self):
        from policy_extractor.schemas.ingestion import IngestionResult

        ir = IngestionResult(
            file_hash="b" * 64,
            file_path="/tmp/test.pdf",
            total_pages=1,
            pages=[],
            file_size_bytes=500,
            created_at=datetime(2026, 1, 1),
            ocr_applied=True,
        )
        d = ir.model_dump()
        assert isinstance(d, dict)
        assert d["file_hash"] == "b" * 64
        assert d["ocr_applied"] is True
        assert d["ocr_language"] == "spa"
        assert d["from_cache"] is False

    def test_defaults(self):
        from policy_extractor.schemas.ingestion import IngestionResult

        ir = IngestionResult(
            file_hash="c" * 64,
            file_path="/tmp/x.pdf",
            total_pages=0,
            file_size_bytes=0,
            created_at=datetime.now(),
            ocr_applied=False,
        )
        assert ir.pages == []
        assert ir.ocr_language == "spa"
        assert ir.from_cache is False

    def test_all_required_fields_present(self):
        from policy_extractor.schemas.ingestion import IngestionResult

        import inspect as ins

        fields = IngestionResult.model_fields
        required = {
            "file_hash",
            "file_path",
            "total_pages",
            "file_size_bytes",
            "created_at",
            "ocr_applied",
        }
        for field in required:
            assert field in fields, f"Missing required field: {field}"


class TestIngestionCacheModel:
    @pytest.fixture
    def mem_engine(self):
        from policy_extractor.storage.models import Base, IngestionCache  # noqa: F401

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine

    def test_ingestion_cache_table_created(self, mem_engine):
        inspector = inspect(mem_engine)
        tables = inspector.get_table_names()
        assert "ingestion_cache" in tables

    def test_ingestion_cache_insert_and_query_by_hash(self, mem_engine):
        from policy_extractor.storage.models import IngestionCache

        with Session(mem_engine) as session:
            entry = IngestionCache(
                file_hash="d" * 64,
                file_path="/tmp/pol.pdf",
                total_pages=2,
                page_results=[{"page_num": 1, "text": "hi", "classification": "digital"}],
                file_size_bytes=9999,
                created_at=datetime(2026, 3, 18),
                ocr_language="spa",
            )
            session.add(entry)
            session.commit()

        with Session(mem_engine) as session:
            from sqlalchemy import select

            result = session.execute(
                select(IngestionCache).where(IngestionCache.file_hash == "d" * 64)
            ).scalar_one_or_none()
            assert result is not None
            assert result.total_pages == 2
            assert result.ocr_language == "spa"

    def test_existing_tables_still_present(self, mem_engine):
        inspector = inspect(mem_engine)
        tables = inspector.get_table_names()
        for expected in ("polizas", "asegurados", "coberturas", "ingestion_cache"):
            assert expected in tables, f"Table missing: {expected}"

    def test_ingestion_cache_file_hash_unique(self, mem_engine):
        from sqlalchemy.exc import IntegrityError

        from policy_extractor.storage.models import IngestionCache

        with Session(mem_engine) as session:
            e1 = IngestionCache(
                file_hash="e" * 64,
                file_path="/a.pdf",
                total_pages=1,
                page_results=[],
                file_size_bytes=100,
                created_at=datetime.now(),
            )
            session.add(e1)
            session.commit()

        with Session(mem_engine) as session:
            e2 = IngestionCache(
                file_hash="e" * 64,
                file_path="/b.pdf",
                total_pages=1,
                page_results=[],
                file_size_bytes=200,
                created_at=datetime.now(),
            )
            session.add(e2)
            with pytest.raises(IntegrityError):
                session.commit()


class TestConftestEngineFixtureIncludesIngestionCache:
    """Verify the conftest engine fixture creates ingestion_cache via Base.metadata."""

    def test_engine_fixture_creates_ingestion_cache_table(self, engine):
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "ingestion_cache" in tables


class TestConfigExtensions:
    def test_ocr_confidence_threshold_present(self):
        from policy_extractor.config import settings

        assert hasattr(settings, "OCR_CONFIDENCE_THRESHOLD")
        assert isinstance(settings.OCR_CONFIDENCE_THRESHOLD, int)

    def test_page_scan_threshold_present(self):
        from policy_extractor.config import settings

        assert hasattr(settings, "PAGE_SCAN_THRESHOLD")
        assert isinstance(settings.PAGE_SCAN_THRESHOLD, float)

    def test_decorative_image_min_present(self):
        from policy_extractor.config import settings

        assert hasattr(settings, "DECORATIVE_IMAGE_MIN")
        assert isinstance(settings.DECORATIVE_IMAGE_MIN, float)

    def test_ocr_language_present(self):
        from policy_extractor.config import settings

        assert hasattr(settings, "OCR_LANGUAGE")
        assert settings.OCR_LANGUAGE == "spa"

    def test_tesseract_cmd_present(self):
        from policy_extractor.config import settings

        assert hasattr(settings, "TESSERACT_CMD")

    def test_default_thresholds(self):
        from policy_extractor.config import settings

        assert settings.PAGE_SCAN_THRESHOLD == 0.80
        assert settings.DECORATIVE_IMAGE_MIN == 0.10
        assert settings.OCR_CONFIDENCE_THRESHOLD == 60
