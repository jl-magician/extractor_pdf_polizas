"""Tests for ingestion layer: classifier (Plan 01) and ingest_pdf orchestrator (Plan 02)."""
import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import fitz  # PyMuPDF
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
DIGITAL_PDF = FIXTURES / "digital_sample.pdf"
SCANNED_PDF = FIXTURES / "scanned_sample.pdf"

requires_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="Tesseract OCR not installed",
)


@pytest.fixture
def digital_pdf_path():
    return str(FIXTURES / "digital_sample.pdf")


@pytest.fixture
def scanned_pdf_path():
    return str(FIXTURES / "scanned_sample.pdf")


# ────────────────────────────────────────────────────────────────────────────
# Helper: create minimal in-test PDFs
# ────────────────────────────────────────────────────────────────────────────


def make_digital_page_pdf(tmp_path: Path) -> str:
    """1-page PDF with selectable text, no images."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 200), "Digital insurance policy text", fontsize=12)
    out = str(tmp_path / "digital.pdf")
    doc.save(out)
    doc.close()
    return out


def make_scanned_page_pdf(tmp_path: Path) -> str:
    """1-page PDF with a full-page image (>90% coverage)."""
    from PIL import Image

    img_w, img_h = 595, 842
    img = Image.new("RGB", (img_w, img_h), color=(200, 200, 200))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    margin = 5
    page.insert_image(
        fitz.Rect(margin, margin, 595 - margin, 842 - margin),
        stream=img_bytes.getvalue(),
    )
    out = str(tmp_path / "scanned.pdf")
    doc.save(out)
    doc.close()
    return out


def make_watermark_pdf(tmp_path: Path) -> str:
    """1-page PDF with text AND a small logo image (<10% of page area)."""
    from PIL import Image

    # Small logo: ~40x40 pixels = ~1600px^2 vs page 595*842 = ~501k px^2 (~0.3%)
    logo = Image.new("RGB", (40, 40), color=(255, 0, 0))
    logo_bytes = io.BytesIO()
    logo.save(logo_bytes, format="PNG")

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Insert digital text
    page.insert_text((72, 200), "Poliza digital con logo", fontsize=12)
    # Insert tiny logo in corner (well under 10% of page)
    page.insert_image(fitz.Rect(10, 10, 50, 50), stream=logo_bytes.getvalue())
    out = str(tmp_path / "watermark.pdf")
    doc.save(out)
    doc.close()
    return out


def make_transparent_overlay_pdf(tmp_path: Path) -> str:
    """1-page PDF with a masked/transparent image (smask != 0) over text."""
    # We create a PDF with a transparent image by embedding an image with an alpha channel
    # PyMuPDF stores the soft-mask xref in img[1]; we can't directly test smask here
    # without low-level PDF manipulation. Instead we test that a page with only transparent
    # images (which we'll simulate by checking that the resulting PDF classifies as digital)
    # by inserting a small image to a largely text page.
    from PIL import Image

    # We use a RGBA image (has alpha channel). PyMuPDF will embed it with a smask.
    rgba_img = Image.new("RGBA", (200, 200), color=(255, 0, 0, 128))  # semi-transparent
    img_bytes = io.BytesIO()
    rgba_img.save(img_bytes, format="PNG")

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 200), "Digital text page with transparent overlay", fontsize=12)
    # Insert small transparent image
    page.insert_image(fitz.Rect(50, 50, 150, 150), stream=img_bytes.getvalue())
    out = str(tmp_path / "transparent.pdf")
    doc.save(out)
    doc.close()
    return out


# ────────────────────────────────────────────────────────────────────────────
# Classifier tests
# ────────────────────────────────────────────────────────────────────────────


class TestClassifyPage:
    def test_classify_digital_page(self, digital_pdf_path):
        """digital_sample.pdf page 1 should return 'digital'."""
        from policy_extractor.ingestion.classifier import classify_page

        doc = fitz.open(digital_pdf_path)
        result = classify_page(doc[0])
        doc.close()
        assert result == "digital"

    def test_classify_scanned_page(self, scanned_pdf_path):
        """scanned_sample.pdf page 1 should return 'scanned'."""
        from policy_extractor.ingestion.classifier import classify_page

        doc = fitz.open(scanned_pdf_path)
        result = classify_page(doc[0])
        doc.close()
        assert result == "scanned"

    def test_watermark_not_false_scanned(self, tmp_path):
        """A page with small logo (<10% area) on digital text returns 'digital'."""
        from policy_extractor.ingestion.classifier import classify_page

        pdf_path = make_watermark_pdf(tmp_path)
        doc = fitz.open(pdf_path)
        result = classify_page(doc[0])
        doc.close()
        assert result == "digital", (
            "A page with a small logo must not be falsely classified as scanned"
        )

    def test_transparent_overlay_skipped(self, tmp_path):
        """A transparent RGBA image (smask != 0) does not count toward coverage."""
        from policy_extractor.ingestion.classifier import classify_page

        pdf_path = make_transparent_overlay_pdf(tmp_path)
        doc = fitz.open(pdf_path)
        result = classify_page(doc[0])
        doc.close()
        # The image is small AND transparent; page should remain digital
        assert result == "digital"

    def test_empty_page_classified_digital(self, tmp_path):
        """A page with no images and no text returns 'digital'."""
        from policy_extractor.ingestion.classifier import classify_page

        doc = fitz.open()
        doc.new_page(width=595, height=842)
        out = str(tmp_path / "empty.pdf")
        doc.save(out)
        doc.close()

        doc2 = fitz.open(out)
        result = classify_page(doc2[0])
        doc2.close()
        assert result == "digital"


class TestClassifyAllPages:
    def test_classify_all_pages_returns_list(self, digital_pdf_path):
        """classify_all_pages returns list of (page_num, classification) tuples."""
        from policy_extractor.ingestion.classifier import classify_all_pages

        results = classify_all_pages(digital_pdf_path)
        assert isinstance(results, list)
        assert len(results) == 1
        page_num, classification = results[0]
        assert page_num == 1
        assert classification in ("digital", "scanned")

    def test_classify_all_pages_1_based_numbering(self, digital_pdf_path):
        """Page numbers are 1-based."""
        from policy_extractor.ingestion.classifier import classify_all_pages

        results = classify_all_pages(digital_pdf_path)
        page_nums = [r[0] for r in results]
        assert page_nums[0] == 1

    def test_classify_all_pages_digital_file(self, digital_pdf_path):
        from policy_extractor.ingestion.classifier import classify_all_pages

        results = classify_all_pages(digital_pdf_path)
        assert results[0][1] == "digital"

    def test_classify_all_pages_scanned_file(self, scanned_pdf_path):
        from policy_extractor.ingestion.classifier import classify_all_pages

        results = classify_all_pages(scanned_pdf_path)
        assert results[0][1] == "scanned"

    def test_corrupted_pdf_raises_runtime_error(self, tmp_path):
        """Opening a non-PDF file should raise RuntimeError (handled, not crash)."""
        from policy_extractor.ingestion.classifier import classify_all_pages

        bad_file = tmp_path / "not_a_pdf.txt"
        bad_file.write_text("this is not a pdf")

        with pytest.raises(RuntimeError):
            classify_all_pages(str(bad_file))


class TestClassifierModule:
    def test_classify_page_importable(self):
        from policy_extractor.ingestion.classifier import classify_page

        assert callable(classify_page)

    def test_classify_all_pages_importable(self):
        from policy_extractor.ingestion.classifier import classify_all_pages

        assert callable(classify_all_pages)

    def test_ingestion_init_exports(self):
        from policy_extractor.ingestion import classify_all_pages, classify_page

        assert callable(classify_page)
        assert callable(classify_all_pages)


# ────────────────────────────────────────────────────────────────────────────
# ingest_pdf() orchestrator tests (Plan 02-02)
# ────────────────────────────────────────────────────────────────────────────


class TestIngestPdf:
    def test_ingest_returns_pydantic_model(self):
        """ingest_pdf returns an IngestionResult instance."""
        from policy_extractor.ingestion import ingest_pdf, IngestionResult

        result = ingest_pdf(DIGITAL_PDF)
        assert isinstance(result, IngestionResult)

    def test_ingest_digital_pdf(self):
        """Digital PDF: ocr_applied=False, all pages classified 'digital'."""
        from policy_extractor.ingestion import ingest_pdf

        result = ingest_pdf(DIGITAL_PDF)
        assert result.ocr_applied is False
        for page in result.pages:
            assert page.classification == "digital"

    def test_ingest_preserves_page_boundaries(self):
        """result.pages has correct page_num values (1-based) and text strings."""
        from policy_extractor.ingestion import ingest_pdf

        result = ingest_pdf(DIGITAL_PDF)
        assert len(result.pages) >= 1
        assert result.pages[0].page_num == 1
        for page in result.pages:
            assert isinstance(page.text, str)

    def test_ingest_ocr_output_page_tuples(self):
        """result.pages contains PageResult objects with page_num, text, classification."""
        from policy_extractor.ingestion import ingest_pdf
        from policy_extractor.schemas.ingestion import PageResult

        result = ingest_pdf(DIGITAL_PDF)
        for page in result.pages:
            assert isinstance(page, PageResult)
            assert hasattr(page, "page_num")
            assert hasattr(page, "text")
            assert hasattr(page, "classification")

    def test_corrupted_pdf_skipped(self, tmp_path):
        """Corrupted file raises RuntimeError with descriptive message."""
        from policy_extractor.ingestion import ingest_pdf

        bad_pdf = tmp_path / "corrupt.pdf"
        bad_pdf.write_text("this is not a pdf")

        with pytest.raises(RuntimeError, match="(?i)cannot open|not a valid PDF|corrupt"):
            ingest_pdf(bad_pdf)

    @requires_tesseract
    def test_ingest_scanned_pdf(self):
        """Scanned PDF: ocr_applied=True (requires Tesseract)."""
        from policy_extractor.ingestion import ingest_pdf

        result = ingest_pdf(SCANNED_PDF)
        assert result.ocr_applied is True


class TestIngestPdfCache:
    def test_cache_hit_skips_ocr(self, session):
        """Second ingest_pdf call with same hash returns from_cache=True."""
        from policy_extractor.ingestion import ingest_pdf

        # First call — populates cache
        result1 = ingest_pdf(DIGITAL_PDF, session=session)
        assert result1.from_cache is False

        # Second call — should hit cache
        result2 = ingest_pdf(DIGITAL_PDF, session=session)
        assert result2.from_cache is True

    def test_cache_hit_skips_ocr_not_called(self, session):
        """Second ingest_pdf call does not invoke OCR functions."""
        from policy_extractor.ingestion import ingest_pdf

        # Populate cache
        ingest_pdf(DIGITAL_PDF, session=session)

        # Mock ocr_with_fallback to verify it's not called on cache hit
        with patch(
            "policy_extractor.ingestion.ocr_with_fallback"
        ) as mock_ocr:
            result = ingest_pdf(DIGITAL_PDF, session=session)
            assert result.from_cache is True
            mock_ocr.assert_not_called()

    def test_force_reprocess_bypasses_cache(self, session):
        """With force_reprocess=True, OCR runs even if cached."""
        from policy_extractor.ingestion import ingest_pdf

        # Populate cache
        ingest_pdf(DIGITAL_PDF, session=session)

        # force_reprocess=True must return from_cache=False
        result = ingest_pdf(DIGITAL_PDF, session=session, force_reprocess=True)
        assert result.from_cache is False

    def test_cache_hit_path_independent(self, session, tmp_path):
        """Same file content at two paths returns cache hit on second call."""
        from policy_extractor.ingestion import ingest_pdf

        # Ingest original
        ingest_pdf(DIGITAL_PDF, session=session)

        # Copy to different path
        copy_path = tmp_path / "copy_digital.pdf"
        shutil.copy2(DIGITAL_PDF, copy_path)

        # Ingest copy — should be a cache hit (same content)
        result = ingest_pdf(copy_path, session=session)
        assert result.from_cache is True

    def test_ocr_english_fallback(self, tmp_path):
        """mock get_page_confidence < 60 causes run_ocr called twice with spa+eng."""
        from policy_extractor.ingestion.ocr_runner import ocr_with_fallback

        fake_ocr_output = tmp_path / "fake_ocr.pdf"
        shutil.copy2(DIGITAL_PDF, fake_ocr_output)

        with (
            patch(
                "policy_extractor.ingestion.ocr_runner.run_ocr"
            ) as mock_run_ocr,
            patch(
                "policy_extractor.ingestion.ocr_runner.get_page_confidence"
            ) as mock_conf,
        ):
            mock_conf.return_value = 30.0  # below threshold (60)
            mock_run_ocr.side_effect = [
                (fake_ocr_output, "spa"),
                (fake_ocr_output, "spa+eng"),
            ]
            ocr_with_fallback(DIGITAL_PDF)

            assert mock_run_ocr.call_count == 2
            second_lang = mock_run_ocr.call_args_list[1][1].get(
                "language"
            ) or mock_run_ocr.call_args_list[1][0][1]
            assert second_lang == ["spa", "eng"]


# ────────────────────────────────────────────────────────────────────────────
# Auto-OCR reclassification tests (Plan 13-01)
# ────────────────────────────────────────────────────────────────────────────


class TestAutoOcrReclassification:
    """Tests for digital page auto-reclassification when char count is below threshold."""

    def _make_mock_doc(self, page_text: str):
        """Return a mock fitz document whose page 0 returns page_text via get_text()."""
        mock_page = io.StringIO()  # placeholder — we'll use MagicMock below
        from unittest.mock import MagicMock

        mock_fitz_page = MagicMock()
        mock_fitz_page.get_text.return_value = page_text

        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_fitz_page)
        mock_doc.is_pdf = True
        mock_doc.close = MagicMock()
        return mock_doc

    @patch("policy_extractor.ingestion.classify_all_pages")
    @patch("policy_extractor.ingestion.ocr_with_fallback")
    @patch("policy_extractor.ingestion.extract_text_by_page")
    @patch("policy_extractor.ingestion.compute_file_hash")
    @patch("fitz.open")
    def test_auto_reclassify_low_char_digital_page(
        self,
        mock_fitz_open,
        mock_hash,
        mock_extract_text,
        mock_ocr,
        mock_classify,
        tmp_path,
    ):
        """Digital page with < OCR_MIN_CHARS_THRESHOLD chars is auto-reclassified."""
        from policy_extractor.ingestion import ingest_pdf

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf content for hashing purposes only")

        mock_hash.return_value = "a" * 64
        mock_classify.return_value = [(1, "digital")]
        mock_fitz_open.return_value = self._make_mock_doc("abc")  # 3 chars < 10 threshold
        ocr_pdf_path = tmp_path / "ocr_output.pdf"
        ocr_pdf_path.write_bytes(b"ocr output")
        mock_ocr.return_value = (ocr_pdf_path, "spa")
        mock_extract_text.return_value = [(1, "OCR extracted text")]

        result = ingest_pdf(pdf_path)

        assert result.pages[0].classification == "scanned (auto-reclassified)"
        assert result.pages[0].text == "OCR extracted text"

    @patch("policy_extractor.ingestion.classify_all_pages")
    @patch("policy_extractor.ingestion.ocr_with_fallback")
    @patch("policy_extractor.ingestion.compute_file_hash")
    @patch("fitz.open")
    def test_digital_page_above_threshold_stays_digital(
        self,
        mock_fitz_open,
        mock_hash,
        mock_ocr,
        mock_classify,
        tmp_path,
    ):
        """Digital page with >= OCR_MIN_CHARS_THRESHOLD chars keeps digital classification."""
        from policy_extractor.ingestion import ingest_pdf

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf content for hashing purposes only")

        mock_hash.return_value = "b" * 64
        mock_classify.return_value = [(1, "digital")]
        long_text = "x" * 500  # well above threshold
        mock_fitz_open.return_value = self._make_mock_doc(long_text)

        result = ingest_pdf(pdf_path)

        assert result.pages[0].classification == "digital"
        mock_ocr.assert_not_called()

    @patch("policy_extractor.ingestion.classify_all_pages")
    @patch("policy_extractor.ingestion.ocr_with_fallback")
    @patch("policy_extractor.ingestion.compute_file_hash")
    @patch("fitz.open")
    def test_auto_ocr_failure_does_not_crash(
        self,
        mock_fitz_open,
        mock_hash,
        mock_ocr,
        mock_classify,
        tmp_path,
    ):
        """When ocr_with_fallback raises, ingest_pdf keeps original text and does not raise."""
        from policy_extractor.ingestion import ingest_pdf

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf content for hashing purposes only")

        mock_hash.return_value = "c" * 64
        mock_classify.return_value = [(1, "digital")]
        short_text = "ab"  # 2 chars < threshold 10
        mock_fitz_open.return_value = self._make_mock_doc(short_text)
        mock_ocr.side_effect = RuntimeError("OCR engine not available")

        # Should NOT raise
        result = ingest_pdf(pdf_path)

        assert result.pages[0].classification == "scanned (auto-reclassified)"
        # Original short text is preserved because OCR failed
        assert result.pages[0].text == short_text

    def test_page_result_accepts_auto_reclassified(self):
        """PageResult schema accepts 'scanned (auto-reclassified)' classification."""
        from policy_extractor.schemas.ingestion import PageResult

        page = PageResult(page_num=1, text="test", classification="scanned (auto-reclassified)")
        assert page.classification == "scanned (auto-reclassified)"

    def test_ocr_min_chars_threshold_default(self):
        """OCR_MIN_CHARS_THRESHOLD=10 is the default in Settings."""
        from policy_extractor.config import settings

        assert settings.OCR_MIN_CHARS_THRESHOLD == 10

    @patch("policy_extractor.ingestion.classify_all_pages")
    @patch("policy_extractor.ingestion.ocr_with_fallback")
    @patch("policy_extractor.ingestion.extract_text_by_page")
    @patch("policy_extractor.ingestion.compute_file_hash")
    @patch("fitz.open")
    def test_whole_pdf_retry_on_empty_reclassified_texts(
        self,
        mock_fitz_open,
        mock_hash,
        mock_extract_text,
        mock_ocr,
        mock_classify,
        tmp_path,
    ):
        """D-16: When reclassified pages yield all-empty OCR text, whole-PDF OCR retry fires."""
        from policy_extractor.ingestion import ingest_pdf

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf content for hashing purposes only")

        ocr_pdf_path = tmp_path / "ocr_output.pdf"
        ocr_pdf_path.write_bytes(b"ocr output")

        mock_hash.return_value = "d" * 64
        mock_classify.return_value = [(1, "digital")]
        mock_fitz_open.return_value = self._make_mock_doc("ab")  # 2 chars < threshold

        # First OCR call: per-page OCR returns empty text for reclassified page
        # Second OCR call (whole-PDF retry): returns real text
        mock_ocr.side_effect = [
            (ocr_pdf_path, "spa"),
            (ocr_pdf_path, "spa"),
        ]
        mock_extract_text.side_effect = [
            [(1, "")],          # first call: empty — triggers retry
            [(1, "Full text extracted by retry")],  # second call: real text
        ]

        result = ingest_pdf(pdf_path)

        assert mock_ocr.call_count == 2, "Should have called OCR twice (initial + retry)"
        assert result.pages[0].text == "Full text extracted by retry"

    @patch("policy_extractor.ingestion.classify_all_pages")
    @patch("policy_extractor.ingestion.ocr_with_fallback")
    @patch("policy_extractor.ingestion.extract_text_by_page")
    @patch("policy_extractor.ingestion.compute_file_hash")
    @patch("fitz.open")
    def test_whole_pdf_retry_skipped_when_ocr_text_present(
        self,
        mock_fitz_open,
        mock_hash,
        mock_extract_text,
        mock_ocr,
        mock_classify,
        tmp_path,
    ):
        """D-16: Whole-PDF retry does NOT trigger when reclassified pages have non-empty OCR text."""
        from policy_extractor.ingestion import ingest_pdf

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf content for hashing purposes only")

        ocr_pdf_path = tmp_path / "ocr_output.pdf"
        ocr_pdf_path.write_bytes(b"ocr output")

        mock_hash.return_value = "e" * 64
        mock_classify.return_value = [(1, "digital")]
        mock_fitz_open.return_value = self._make_mock_doc("ab")  # 2 chars < threshold

        # First OCR call returns real text — no retry should happen
        mock_ocr.return_value = (ocr_pdf_path, "spa")
        mock_extract_text.return_value = [(1, "Good OCR text from first pass")]

        result = ingest_pdf(pdf_path)

        assert mock_ocr.call_count == 1, "Should have called OCR only once (no retry needed)"
        assert result.pages[0].text == "Good OCR text from first pass"

    @patch("policy_extractor.ingestion.classify_all_pages")
    @patch("policy_extractor.ingestion.ocr_with_fallback")
    @patch("policy_extractor.ingestion.extract_text_by_page")
    @patch("policy_extractor.ingestion.compute_file_hash")
    @patch("fitz.open")
    def test_whole_pdf_retry_failure_does_not_crash(
        self,
        mock_fitz_open,
        mock_hash,
        mock_extract_text,
        mock_ocr,
        mock_classify,
        tmp_path,
    ):
        """D-16: If whole-PDF retry raises, ingest_pdf catches and continues."""
        from policy_extractor.ingestion import ingest_pdf

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf content for hashing purposes only")

        ocr_pdf_path = tmp_path / "ocr_output.pdf"
        ocr_pdf_path.write_bytes(b"ocr output")

        mock_hash.return_value = "f" * 64
        mock_classify.return_value = [(1, "digital")]
        mock_fitz_open.return_value = self._make_mock_doc("ab")  # 2 chars < threshold

        # First OCR call succeeds but returns empty text (triggers retry)
        # Second OCR call (retry) raises RuntimeError
        mock_ocr.side_effect = [
            (ocr_pdf_path, "spa"),
            RuntimeError("Retry OCR engine failed"),
        ]
        mock_extract_text.return_value = [(1, "")]  # empty — triggers retry

        # Should NOT raise — retry failure is swallowed
        result = ingest_pdf(pdf_path)

        assert mock_ocr.call_count == 2
        # Page should exist (even if text is empty due to retry failure)
        assert len(result.pages) == 1
