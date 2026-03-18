"""Per-page PDF classification: digital vs scanned using image coverage ratio."""
import fitz  # PyMuPDF
from loguru import logger

from policy_extractor.config import settings

PAGE_SCAN_THRESHOLD = settings.PAGE_SCAN_THRESHOLD     # 0.80
DECORATIVE_IMAGE_MIN = settings.DECORATIVE_IMAGE_MIN   # 0.10


def classify_page(page: fitz.Page) -> str:
    """Classify a single page as 'digital' or 'scanned'.

    Algorithm:
    1. Get all images on the page via page.get_images(full=True)
    2. For each image, skip if smask != 0 (transparent overlay)
    3. For each image rect, skip if area < DECORATIVE_IMAGE_MIN of page area
    4. Sum remaining image area
    5. If total coverage >= PAGE_SCAN_THRESHOLD (0.80), return 'scanned'
    6. Otherwise return 'digital'
    """
    page_area = abs(page.rect)
    if page_area == 0:
        return "digital"

    images = page.get_images(full=True)
    if not images:
        return "digital"

    covered_area = 0.0
    for img in images:
        xref = img[0]
        smask = img[1]

        # Skip transparent overlays (soft-masked images)
        if smask != 0:
            continue

        rects = page.get_image_rects(xref)
        for rect in rects:
            intersection = page.rect & rect
            img_area = abs(intersection)
            # Skip decorative images (watermarks, logos) — less than DECORATIVE_IMAGE_MIN
            if img_area / page_area < DECORATIVE_IMAGE_MIN:
                continue
            covered_area += img_area

    coverage = covered_area / page_area
    return "scanned" if coverage >= PAGE_SCAN_THRESHOLD else "digital"


def classify_all_pages(pdf_path: str) -> list[tuple[int, str]]:
    """Classify every page in a PDF file.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of (1-based page_num, 'digital'|'scanned') tuples

    Raises:
        RuntimeError: If PDF cannot be opened (corrupted/password-protected)
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        logger.error("Failed to open PDF '{}': {}", pdf_path, exc)
        raise RuntimeError(f"Cannot open PDF '{pdf_path}': {exc}") from exc

    if not doc.is_pdf:
        doc.close()
        logger.error("File '{}' is not a valid PDF", pdf_path)
        raise RuntimeError(f"File '{pdf_path}' is not a valid PDF")

    if doc.is_encrypted:
        logger.error("PDF '{}' is password-protected; skipping", pdf_path)
        doc.close()
        raise RuntimeError(f"PDF '{pdf_path}' is password-protected")

    results: list[tuple[int, str]] = []
    for i, page in enumerate(doc):
        classification = classify_page(page)
        results.append((i + 1, classification))

    doc.close()
    return results
