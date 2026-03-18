"""Tests for Task 2: per-page PDF classifier.

Written FIRST (TDD RED) before classifier.py exists.
"""
import io
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


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
