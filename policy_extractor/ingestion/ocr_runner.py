"""OCR processing for scanned PDF pages using ocrmypdf + pytesseract."""
import tempfile
from pathlib import Path

import fitz  # PyMuPDF — for text extraction from OCR output
import ocrmypdf
from loguru import logger

from policy_extractor.config import settings

CONFIDENCE_THRESHOLD = settings.OCR_CONFIDENCE_THRESHOLD  # 60


def run_ocr(input_path: Path, language: list[str] | None = None) -> tuple[Path, str]:
    """Run ocrmypdf on input PDF, return (output_path, language_used).

    If exit_code is already_done_ocr, returns (input_path, language_str).
    Raises RuntimeError on OCR failure.
    """
    if language is None:
        language = [settings.OCR_LANGUAGE]  # ["spa"]
    lang_str = "+".join(language)
    output_path = Path(tempfile.mktemp(suffix=".pdf"))

    exit_code = ocrmypdf.ocr(
        input_file=str(input_path),
        output_file=str(output_path),
        language=language,
        deskew=True,
        skip_text=True,
        output_type="pdf",
        jobs=1,
    )

    if exit_code == ocrmypdf.ExitCode.already_done_ocr:
        logger.info(f"PDF already has text layer: {input_path}")
        output_path.unlink(missing_ok=True)
        return input_path, lang_str

    if exit_code != ocrmypdf.ExitCode.ok:
        output_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"ocrmypdf failed with exit code {exit_code} for {input_path}"
        )

    return output_path, lang_str


def extract_text_by_page(pdf_path: Path) -> list[tuple[int, str]]:
    """Extract text from each page of a text-layer PDF.

    Returns list of (1-based page_num, text) tuples.
    """
    doc = fitz.open(str(pdf_path))
    results = [(i + 1, page.get_text()) for i, page in enumerate(doc)]
    doc.close()
    return results


def get_page_confidence(pdf_path: Path, page_num: int, lang: str = "spa") -> float:
    """Get mean OCR confidence for a specific page (0-100).

    Uses pdf2image to convert page to PIL image, then pytesseract.image_to_data.
    Words with conf == -1 are excluded from the mean.
    Returns 0.0 if no valid words found.
    """
    from pdf2image import convert_from_path
    import pytesseract

    images = convert_from_path(
        str(pdf_path), first_page=page_num, last_page=page_num, dpi=150
    )
    if not images:
        return 0.0

    data = pytesseract.image_to_data(
        images[0], lang=lang, output_type=pytesseract.Output.DATAFRAME
    )
    valid = data[data["conf"] != -1]["conf"]
    return float(valid.mean()) if not valid.empty else 0.0


def ocr_with_fallback(input_path: Path) -> tuple[Path, str]:
    """OCR a PDF with Spanish. Retry with English if confidence too low.

    Samples first scanned page for confidence. If mean confidence < CONFIDENCE_THRESHOLD (60),
    re-runs OCR with ["spa", "eng"].

    Returns (output_pdf_path, language_used_string).
    """
    output_path, lang_used = run_ocr(input_path, language=["spa"])

    # If already had text layer, no need to check confidence
    if output_path == input_path:
        return output_path, lang_used

    # Sample first page for confidence check
    try:
        conf = get_page_confidence(output_path, page_num=1, lang="spa")
        logger.debug(f"OCR confidence for {input_path.name} page 1: {conf:.1f}")

        if conf < CONFIDENCE_THRESHOLD:
            logger.info(
                f"Low Spanish confidence ({conf:.1f} < {CONFIDENCE_THRESHOLD}), "
                f"retrying with spa+eng: {input_path}"
            )
            output_path.unlink(missing_ok=True)
            output_path, lang_used = run_ocr(input_path, language=["spa", "eng"])
    except Exception as e:
        logger.warning(f"Confidence check failed, using Spanish-only result: {e}")

    return output_path, lang_used
