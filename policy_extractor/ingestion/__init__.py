"""Ingestion layer — PDF classification, OCR, caching, and structured output.

Public API:
    ingest_pdf(pdf_path, session=None, force_reprocess=False) -> IngestionResult
"""
from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF
from loguru import logger
from sqlalchemy.orm import Session

from policy_extractor.schemas.ingestion import IngestionResult, PageResult
from .classifier import classify_page, classify_all_pages
from .ocr_runner import run_ocr, ocr_with_fallback, extract_text_by_page
from .cache import compute_file_hash, lookup_cache, save_cache

__all__ = [
    "ingest_pdf",
    "IngestionResult",
    "PageResult",
    "classify_page",
    "classify_all_pages",
    "compute_file_hash",
]


def ingest_pdf(
    pdf_path: str | Path,
    session: Session | None = None,
    force_reprocess: bool = False,
) -> IngestionResult:
    """Ingest a single PDF file: classify pages, OCR if needed, cache result.

    Orchestration flow:
    1. Compute SHA-256 hash of file bytes
    2. If session provided and not force_reprocess: check cache
    3. Open PDF with PyMuPDF, classify each page
    4. For digital pages: extract text directly with page.get_text()
    5. If any scanned pages exist: run ocr_with_fallback() on the full PDF,
       then extract text from OCR output for scanned pages
    6. Build IngestionResult with per-page PageResult objects
    7. If session provided: save to cache
    8. Return IngestionResult

    Args:
        pdf_path: Path to PDF file (str or Path)
        session: Optional SQLAlchemy session for cache operations. If None, caching is skipped.
        force_reprocess: If True, bypass cache and re-run full pipeline.

    Returns:
        IngestionResult with per-page text and classification

    Raises:
        RuntimeError: If PDF cannot be opened (corrupted or password-protected).
            Error is logged with file path and reason before raising.
    """
    pdf_path = Path(pdf_path)

    # Step 1: Hash
    file_hash = compute_file_hash(pdf_path)
    logger.info(f"Processing {pdf_path.name} (hash: {file_hash[:12]}...)")

    # Step 2: Cache check
    if session and not force_reprocess:
        cached = lookup_cache(session, file_hash)
        if cached is not None:
            logger.info(f"Cache hit for {pdf_path.name}")
            # Update file_path to current location (informational)
            cached.file_path = str(pdf_path.resolve())
            return cached

    # Step 3: Open and classify
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        msg = f"Cannot open PDF {pdf_path}: {e}"
        logger.error(msg)
        raise RuntimeError(msg) from e

    if not doc.is_pdf:
        doc.close()
        msg = f"Cannot open PDF {pdf_path}: not a valid PDF"
        logger.error(msg)
        raise RuntimeError(msg)

    classifications = classify_all_pages(str(pdf_path))
    has_scanned = any(c == "scanned" for _, c in classifications)

    # Step 4+5: Extract text
    pages: list[PageResult] = []
    ocr_language = "spa"

    if has_scanned:
        # Run OCR on full file (ocrmypdf handles skip_text for digital pages)
        ocr_output_path, ocr_language = ocr_with_fallback(pdf_path)
        ocr_texts = extract_text_by_page(ocr_output_path)
        ocr_text_map = {pn: txt for pn, txt in ocr_texts}

        # Also get direct text for digital pages
        for page_num, classification in classifications:
            if classification == "digital":
                text = doc[page_num - 1].get_text()
            else:
                text = ocr_text_map.get(page_num, "")
            pages.append(PageResult(
                page_num=page_num, text=text, classification=classification
            ))

        # Clean up temp file if different from input
        if ocr_output_path != pdf_path:
            ocr_output_path.unlink(missing_ok=True)
    else:
        # All digital — extract text directly
        for page_num, classification in classifications:
            text = doc[page_num - 1].get_text()
            pages.append(PageResult(
                page_num=page_num, text=text, classification=classification
            ))

    doc.close()

    # Step 6: Build result
    result = IngestionResult(
        file_hash=file_hash,
        file_path=str(pdf_path.resolve()),
        total_pages=len(pages),
        pages=pages,
        file_size_bytes=pdf_path.stat().st_size,
        created_at=datetime.utcnow(),
        ocr_applied=has_scanned,
        ocr_language=ocr_language,
        from_cache=False,
    )

    # Step 7: Cache
    if session:
        save_cache(session, result)

    logger.info(
        f"Ingested {pdf_path.name}: {result.total_pages} pages, "
        f"ocr={'yes' if has_scanned else 'no'}, lang={ocr_language}"
    )
    return result
