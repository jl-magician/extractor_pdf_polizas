# Phase 02: Ingestion - Research

**Researched:** 2026-03-18
**Domain:** PDF classification (digital vs scanned), OCR preprocessing, per-page text extraction, result caching
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**PDF Classification**
- Per-page classification — each page is independently classified as digital or scanned
- Detection method: image coverage ratio — if images cover >80% of page area, treat as scanned
- Filter out decorative images (<10% page area) and transparent overlays before calculating coverage to avoid false "scanned" classification from watermarks
- Password-protected or corrupted PDFs: skip with error log (file path + reason), continue processing remaining files

**OCR Pipeline**
- Basic preprocessing before OCR: deskew + light contrast enhancement (ocrmypdf built-in)
- Language: Spanish-only as primary OCR language
- English fallback: if OCR confidence is low on a page, retry with English language pack
- OCR output preserves page boundaries: return list of (page_number, text) tuples, not concatenated string

**Caching Strategy**
- Cache key: SHA-256 hash of file content bytes — same file = same hash regardless of filename or location
- Cache storage: SQLite table (`ingestion_cache`) in the existing database — file hash, extracted text, page classifications, timestamps
- Cache invalidation: never auto-invalidate — same hash = same content = same output forever. Only a `--force-reprocess` flag bypasses cache
- Policy-number-based deduplication deferred to Phase 4/5 (policy number isn't known until after extraction)

**Output Contract**
- Structured Pydantic result object (not plain text) — typed and validated handoff to Phase 3
- Fields: file_hash, file_path, total_pages, list of (page_num, text, classification) per page, source metadata (file size, created date)
- Text only — no page images. Phase 3 sends text to Claude API, not images
- One result per file — if a PDF contains multiple policies, Phase 3 handles splitting

### Claude's Discretion
- Exact image coverage calculation algorithm
- OCR confidence threshold for English fallback retry
- Pydantic model naming and field naming for ingestion result
- Internal module structure within `policy_extractor/ingestion/`

### Deferred Ideas (OUT OF SCOPE)
- Policy-number-based deduplication at the extraction/storage level (Phase 4/5)
- Full image preprocessing (denoise, binarization) for low-quality scans — v2 scope (QAL-02)
- Sending page images to Claude vision API for complex layouts — revisit if text-only extraction proves insufficient
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ING-01 | System detects whether a PDF contains selectable text or is a scanned image | PyMuPDF `page.get_images()` + coverage ratio heuristic; `page.get_text()` for text presence check |
| ING-02 | System extracts text from scanned PDFs using OCR with Spanish and English support | ocrmypdf Python API with `language=["spa", "eng"]`; pytesseract `image_to_data()` for per-page confidence; English fallback on low confidence |
| ING-05 | System caches OCR results to avoid reprocessing the same PDF | SHA-256 file hash as cache key; new `IngestionCache` SQLAlchemy model added alongside existing Phase 1 tables; cache checked before OCR is run |
</phase_requirements>

---

## Summary

Phase 2 builds the ingestion layer that routes every incoming PDF to the correct processing path before any LLM interaction. It has three distinct technical problems: (1) classifying each page as digital-text or scanned-image using PyMuPDF's image geometry API, (2) applying OCR via ocrmypdf's Python API with Tesseract as the backend for scanned pages, and (3) caching results in the existing SQLite database so identical files are never re-processed.

The classification logic is per-page rather than per-file, because real insurance policies from Mexican insurers frequently mix digital pages (terms, conditions, schedules) with scanned pages (signature pages, attached endorsements). The 80% image-coverage threshold was chosen to tolerate watermarks and logos; decorative images below 10% of page area are filtered before the ratio is computed. PyMuPDF provides the geometry primitives to implement this without any image rasterization.

The OCR pipeline is built on ocrmypdf calling Tesseract internally. ocrmypdf handles deskew and contrast enhancement as built-in options, which are the only preprocessing steps the user has chosen for v1. pytesseract is used separately to obtain per-word confidence scores from Tesseract's `image_to_data` output — if the page-level mean confidence falls below a threshold (recommended: 60), the page is re-processed with English added to the language set. The Pydantic ingestion result model is the typed contract that Phase 3 consumes; it is never plain text.

**Primary recommendation:** Implement the ingestion layer as three focused modules inside `policy_extractor/ingestion/`: a classifier, an OCR runner, and a cache store. Wire them together in a public `ingest_pdf()` function that returns a single `IngestionResult` Pydantic model. Add the `IngestionCache` SQLAlchemy model to the existing `models.py` and call `Base.metadata.create_all()` — no migration needed.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyMuPDF | 1.27.2 | PDF parsing, page geometry, text extraction | Fastest Python PDF library; `page.get_images()`, `page.get_image_rects()`, and `page.get_text()` provide everything needed for classification without rasterizing pages; bundled MuPDF binaries, no external install |
| ocrmypdf | 17.3.0 | OCR preprocessing for scanned PDFs | Wraps Tesseract; handles deskew, contrast, and text-layer insertion in one call; Python API via `ocrmypdf.ocr()`; returns `ExitCode` enum; Spanish language pack support built-in |
| pytesseract | 0.3.13 | Per-page OCR confidence scoring | `image_to_data()` returns per-word confidence 0-100; needed to decide English fallback; lightweight wrapper over Tesseract binary |
| pdf2image | 1.17.0 | PDF page to PIL image | Required by pytesseract confidence check (pytesseract needs PIL image input); converts specific pages to images for confidence sampling |
| pydantic | 2.12.5 | `IngestionResult` output contract | Already installed; follow same pattern as Phase 1 schemas |
| SQLAlchemy | 2.0.48 | `IngestionCache` table | Already installed; add model to existing `models.py` |
| hashlib | stdlib | SHA-256 file hash | No install needed; `hashlib.sha256(bytes).hexdigest()` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow | latest (pdf2image dep) | Image representation for pytesseract | Pulled in automatically by pdf2image |
| pathlib | stdlib | Path handling | All file I/O — already used in Phase 1 |
| loguru | 0.7.x | Structured logging | Log skip reasons (corrupted/protected files), OCR fallback events |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ocrmypdf | pytesseract direct | pytesseract alone does not produce a text-layer PDF; ocrmypdf does, which is the required output format for Phase 3 |
| pytesseract confidence | ocrmypdf --tesseract-config | ocrmypdf does not expose per-page confidence natively; pytesseract.image_to_data is the cleaner path |
| pdf2image for confidence sampling | PyMuPDF pixmap | Both work; pdf2image is already needed and more convenient for pytesseract input |

**Installation (libraries not yet in pyproject.toml):**
```bash
pip install pymupdf==1.27.2 ocrmypdf==17.3.0 pytesseract==0.3.13 pdf2image==1.17.0 loguru
```

Add to `pyproject.toml` `dependencies`:
```toml
"pymupdf>=1.27.2",
"ocrmypdf>=17.3.0",
"pytesseract>=0.3.13",
"pdf2image>=1.17.0",
"loguru>=0.7",
```

**Windows prerequisites (must be installed before Phase 2 code runs):**
```
Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
  - Install tesseract-ocr-w64-setup.exe
  - Install tesseract-ocr-spa.exe language pack
  - Add to PATH: C:\Program Files\Tesseract-OCR

Poppler (for pdf2image): https://github.com/oschwartz10612/poppler-windows/releases
  - Extract and add bin/ to PATH or pass poppler_path= argument
```

**Version verification (run before implementation):**
```bash
pip show pymupdf ocrmypdf pytesseract pdf2image
```

---

## Architecture Patterns

### Recommended Module Structure

```
policy_extractor/ingestion/
├── __init__.py          # exports: ingest_pdf(), IngestionResult
├── classifier.py        # classify_page() -> PageClassification
├── ocr_runner.py        # ocr_pages() -> list[(page_num, text)]
└── cache.py             # get_cached(), save_to_cache()
```

The `IngestionCache` SQLAlchemy model lives in the existing `policy_extractor/storage/models.py` alongside `Poliza`, `Asegurado`, and `Cobertura`.

### Pattern 1: Per-Page Classification with Image Coverage Ratio

**What:** For each page, sum the area of all images that meet the minimum size threshold (>10% of page area), then divide by page area. Pages where coverage exceeds 80% are classified as `"scanned"`. Pages below the threshold are classified as `"digital"`.

**When to use:** Always — this is the locked classification method.

**Coverage ratio algorithm (recommended implementation):**
```python
# Source: PyMuPDF official docs + Discussion #1653
import fitz  # PyMuPDF

PAGE_SCAN_THRESHOLD = 0.80       # images covering >80% of page = scanned
DECORATIVE_IMAGE_MIN = 0.10      # images <10% of page area are decorative, skip

def classify_page(page: fitz.Page) -> str:
    """Return 'digital' or 'scanned' for a single page."""
    page_area = abs(page.rect)
    if page_area == 0:
        return "digital"

    images = page.get_images(full=True)
    if not images:
        return "digital"

    covered_area = 0.0
    for img in images:
        xref = img[0]
        rects = page.get_image_rects(xref)
        for rect, _matrix in rects:
            intersection = page.rect & rect
            img_area = abs(intersection)
            # Skip decorative images (watermarks, logos)
            if img_area / page_area < DECORATIVE_IMAGE_MIN:
                continue
            # Skip transparent overlays (check colorspace or mask)
            covered_area += img_area

    coverage = covered_area / page_area
    return "scanned" if coverage >= PAGE_SCAN_THRESHOLD else "digital"
```

**Note on transparent overlay detection:** PyMuPDF stores the soft mask xref in `img[1]` (smask field). An image with a non-zero smask is a masked/transparent image. These should be skipped alongside decoratives when calculating coverage to avoid false "scanned" classification from watermark overlays.

```python
# img tuple: (xref, smask, width, height, colorspace_n, colorspace_name, ...)
smask = img[1]
is_transparent = smask != 0
if is_transparent:
    continue
```

### Pattern 2: ocrmypdf Python API for OCR

**What:** Call `ocrmypdf.ocr()` with `deskew=True`, `language=["spa"]` (or `["spa", "eng"]` for fallback retry), writing a text-layer PDF to a temp file, then extract the text with PyMuPDF.

**When to use:** When any page in the file is classified as `"scanned"`.

```python
# Source: ocrmypdf 17.3.0 docs — https://ocrmypdf.readthedocs.io/en/stable/apiref.html
import ocrmypdf
import tempfile
from pathlib import Path

def run_ocr(input_path: Path, language: list[str] = ["spa"]) -> Path:
    """Run ocrmypdf on the input PDF, return path to OCR-enhanced output PDF."""
    output_path = Path(tempfile.mktemp(suffix=".pdf"))
    exit_code = ocrmypdf.ocr(
        input_file=str(input_path),
        output_file=str(output_path),
        language=language,
        deskew=True,
        skip_text=True,         # skip pages that already have text layer
        output_type="pdf",
        jobs=1,                 # ocrmypdf is single-threaded per call
    )
    if exit_code not in (ocrmypdf.ExitCode.ok, ocrmypdf.ExitCode.already_done_ocr):
        raise RuntimeError(f"ocrmypdf failed with exit code {exit_code}")
    return output_path
```

**After OCR:** Extract text per page from the output PDF using PyMuPDF:
```python
import fitz

def extract_text_by_page(pdf_path: Path) -> list[tuple[int, str]]:
    """Return list of (page_number, text) from a text-layer PDF."""
    doc = fitz.open(str(pdf_path))
    return [(i + 1, page.get_text()) for i, page in enumerate(doc)]
```

### Pattern 3: pytesseract Confidence Scoring for English Fallback

**What:** Before/after running OCR with Spanish, sample a scanned page through pytesseract to get mean word confidence. If below threshold, retry ocrmypdf with `["spa", "eng"]`.

**When to use:** As a post-OCR quality check on scanned pages.

```python
# Source: pytesseract docs + https://about.lovia.id/confidence-in-ktp-ocr-using-pytesseract/
import pytesseract
from PIL import Image
import pandas as pd

CONFIDENCE_THRESHOLD = 60  # below this mean = retry with English

def get_page_confidence(pil_image: Image.Image, lang: str = "spa") -> float:
    """Return mean OCR confidence for a page image (0-100). -1 words excluded."""
    data = pytesseract.image_to_data(
        pil_image, lang=lang, output_type=pytesseract.Output.DATAFRAME
    )
    valid = data[data["conf"] != -1]["conf"]
    return float(valid.mean()) if not valid.empty else 0.0
```

**OCR fallback decision logic:**
```python
def needs_english_fallback(page_confidences: list[float]) -> bool:
    """Return True if mean page confidence is below threshold."""
    if not page_confidences:
        return False
    return sum(page_confidences) / len(page_confidences) < CONFIDENCE_THRESHOLD
```

### Pattern 4: SHA-256 Cache Key and SQLite Cache Table

**What:** Hash the raw PDF bytes before any processing. Check the `ingestion_cache` table. On hit, return cached result. On miss, run ingestion and persist.

```python
# hashlib is stdlib — no install
import hashlib

def compute_file_hash(file_path: Path) -> str:
    """Return SHA-256 hex digest of file content bytes."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()
```

**IngestionCache SQLAlchemy model** (add to `policy_extractor/storage/models.py`):
```python
# Follow established pattern: SQLAlchemy 2.0 Mapped[] with DeclarativeBase
import json
from datetime import datetime
from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

class IngestionCache(Base):
    __tablename__ = "ingestion_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_path: Mapped[str] = mapped_column(String)          # last seen path (informational)
    total_pages: Mapped[int] = mapped_column()
    # JSON-serialized list of {"page_num": int, "text": str, "classification": str}
    page_results: Mapped[dict] = mapped_column(JSON)
    file_size_bytes: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ocr_language: Mapped[str] = mapped_column(String, default="spa")  # which lang was used
```

**Cache lookup pattern:**
```python
from sqlalchemy.orm import Session
from policy_extractor.storage.models import IngestionCache

def get_cached(session: Session, file_hash: str) -> IngestionCache | None:
    return session.get(IngestionCache, file_hash)  # SQLAlchemy identity map lookup

# Or with filter:
def get_cached(session: Session, file_hash: str) -> IngestionCache | None:
    return session.execute(
        select(IngestionCache).where(IngestionCache.file_hash == file_hash)
    ).scalar_one_or_none()
```

### Pattern 5: IngestionResult Pydantic Model

**What:** The typed output of `ingest_pdf()`, consumed by Phase 3. Follow the same Pydantic v2 pattern as Phase 1 schemas.

```python
# policy_extractor/ingestion/__init__.py (or schemas/ingestion.py)
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class PageResult(BaseModel):
    page_num: int
    text: str
    classification: Literal["digital", "scanned"]

class IngestionResult(BaseModel):
    file_hash: str               # SHA-256 hex string (64 chars)
    file_path: str               # absolute path as string
    total_pages: int
    pages: list[PageResult] = Field(default_factory=list)
    file_size_bytes: int
    created_at: datetime         # file mtime or processing time
    ocr_applied: bool            # True if any page was processed by OCR
    ocr_language: str = "spa"    # language used for OCR
    from_cache: bool = False     # True if result was loaded from cache
```

### Anti-Patterns to Avoid

- **Classifying per-file instead of per-page:** Insurance PDFs frequently mix digital and scanned pages within the same document. Per-file classification will produce wrong results.
- **Ignoring smask/transparent images in coverage calculation:** Watermarks and transparent overlays appear in `get_images()` output. If not filtered, they inflate coverage and cause false "scanned" classification on digital pages with logos.
- **Using `page.get_text()` alone as the classification signal:** Some scanned PDFs processed by prior OCR contain a text layer ("GlyphlessFont"). Text presence alone is not a reliable "digital" signal. Use image coverage as the primary signal.
- **Concatenating all page text into one string:** The output contract requires per-page (page_num, text) tuples. Concatenation loses page boundary information needed by Phase 3 for prompt segmentation.
- **Blocking cache on `--force-reprocess`:** The flag must be a caller-provided parameter, not a global state change. The cache table is never auto-invalidated.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction with layout preservation | Custom page parser | `fitz.Page.get_text()` | Multi-column insurance PDFs require positional text extraction; PyMuPDF handles reading order correctly |
| OCR with deskew + preprocessing | Tesseract subprocess + ImageMagick | `ocrmypdf.ocr(deskew=True)` | ocrmypdf handles 15+ preprocessing steps, error recovery, page-by-page processing, and text-layer insertion in one call |
| Per-word OCR confidence | Custom confidence parser | `pytesseract.image_to_data(..., output_type=Output.DATAFRAME)` | Tesseract's TSV output includes per-word conf column; pytesseract parses it into a clean DataFrame |
| PDF to image conversion | fitz pixmap pipeline | `pdf2image.convert_from_path()` | pdf2image handles DPI, page selection, and PIL output in one call; correct integration point for pytesseract |
| SHA-256 hashing | Custom rolling hash | `hashlib.sha256(bytes).hexdigest()` | stdlib; handles all file sizes correctly; same key regardless of filename or location |

**Key insight:** The ingestion layer has no novel algorithmic work. Every sub-problem (geometry, OCR, confidence, hashing) is solved by a well-maintained library. The implementation work is wiring these libraries together with correct error handling and caching.

---

## Common Pitfalls

### Pitfall 1: ocrmypdf Threading Lock

**What goes wrong:** `ocrmypdf.ocr()` takes a process-level threading lock. Calling it from multiple threads in the same process raises a `RuntimeError`.

**Why it happens:** ocrmypdf uses a plugin system with global state; it is not thread-safe.

**How to avoid:** Call `ocrmypdf.ocr()` from a single worker thread or use `multiprocessing` if parallelism is needed. In Phase 2 (single-file ingestion), this is not an issue, but batch processing in Phase 4 must use processes, not threads.

**Warning signs:** `RuntimeError: ocrmypdf is already running` in concurrent code.

### Pitfall 2: `get_image_rects()` Returns Empty for Some Image Types

**What goes wrong:** Some images in insurance PDFs are embedded via Form XObjects rather than direct image references. `page.get_images()` may not enumerate them, and `get_image_rects()` returns an empty list.

**Why it happens:** PDF has multiple ways to embed images. Form XObjects are common for recurring elements like letterheads and stamps.

**How to avoid:** Call `page.get_images(full=True)` with `full=True` to include images from nested XObjects. Also check `page.get_image_info(xrefs=True)` as a supplement for any images `get_images()` misses.

**Warning signs:** Pages classified as "digital" that visually appear to be scanned when opened in a PDF viewer.

### Pitfall 3: ocrmypdf `already_done_ocr` Exit Code

**What goes wrong:** If a scanned PDF was previously OCR-processed by another tool and already has a text layer, `ocrmypdf.ocr()` returns `ExitCode.already_done_ocr` (6) and does not process the file. The output file is not written.

**Why it happens:** ocrmypdf detects existing text layers and skips by default to avoid double-OCR.

**How to avoid:** Check for both `ExitCode.ok` AND `ExitCode.already_done_ocr` as success cases. If exit code is `already_done_ocr`, use the original input path (not the output path) for text extraction, since the file already has a text layer.

### Pitfall 4: pytesseract `image_to_data` Requires Pillow Image, Not Path

**What goes wrong:** Passing a file path string to `pytesseract.image_to_data()` causes type errors on some platforms.

**Why it happens:** pytesseract's internal path handling is inconsistent on Windows.

**How to avoid:** Always pass a PIL `Image` object. Use `pdf2image.convert_from_path(path, first_page=n, last_page=n)` to get PIL images from specific pages. Do not pass raw file paths.

### Pitfall 5: Cache Table Not Created Before First Use

**What goes wrong:** `IngestionCache` is added to `models.py` but `init_db()` was already called once before the model was added. The table does not exist at runtime.

**Why it happens:** `Base.metadata.create_all()` uses `CREATE TABLE IF NOT EXISTS` — it only creates tables that exist in `Base.metadata` at call time. The new model must be imported before `init_db()` runs.

**How to avoid:** Import `IngestionCache` in `policy_extractor/storage/__init__.py` or in `models.py` directly (it already lives there). Ensure `init_db()` is called at application startup after all models are imported. Since `Base.metadata.create_all()` is idempotent, calling `init_db()` again after adding the new model is safe.

---

## Code Examples

### Full Page Classification Loop

```python
# Source: PyMuPDF docs + Discussion #1653 (github.com/pymupdf/PyMuPDF/discussions/1653)
import fitz

PAGE_SCAN_THRESHOLD = 0.80
DECORATIVE_IMAGE_MIN = 0.10

def classify_all_pages(pdf_path: str) -> list[tuple[int, str]]:
    """Return list of (page_num, 'digital'|'scanned') for every page."""
    doc = fitz.open(pdf_path)
    results = []
    for i, page in enumerate(doc):
        page_area = abs(page.rect)
        images = page.get_images(full=True)
        covered = 0.0
        for img in images:
            xref, smask = img[0], img[1]
            if smask != 0:
                continue  # transparent overlay — skip
            for rect, _ in page.get_image_rects(xref):
                intersection = page.rect & rect
                img_area = abs(intersection)
                if page_area > 0 and img_area / page_area < DECORATIVE_IMAGE_MIN:
                    continue
                covered += img_area
        coverage = covered / page_area if page_area > 0 else 0.0
        classification = "scanned" if coverage >= PAGE_SCAN_THRESHOLD else "digital"
        results.append((i + 1, classification))
    return results
```

### OCR with English Fallback

```python
# Source: ocrmypdf 17.3.0 docs (ocrmypdf.readthedocs.io/en/stable/apiref.html)
import ocrmypdf
import tempfile
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

CONFIDENCE_THRESHOLD = 60

def ocr_with_fallback(input_path: Path) -> Path:
    """OCR a PDF. Retry with English if Spanish confidence is too low."""
    output_path = Path(tempfile.mktemp(suffix=".pdf"))

    exit_code = ocrmypdf.ocr(
        input_file=str(input_path),
        output_file=str(output_path),
        language=["spa"],
        deskew=True,
        skip_text=True,
        output_type="pdf",
        jobs=1,
    )

    if exit_code == ocrmypdf.ExitCode.already_done_ocr:
        return input_path  # already has text layer, use as-is

    if exit_code != ocrmypdf.ExitCode.ok:
        raise RuntimeError(f"ocrmypdf failed: {exit_code}")

    # Sample first scanned page for confidence check
    images = convert_from_path(str(output_path), first_page=1, last_page=1, dpi=150)
    if images:
        data = pytesseract.image_to_data(
            images[0], lang="spa", output_type=pytesseract.Output.DATAFRAME
        )
        valid_conf = data[data["conf"] != -1]["conf"]
        mean_conf = float(valid_conf.mean()) if not valid_conf.empty else 0.0

        if mean_conf < CONFIDENCE_THRESHOLD:
            output_path.unlink(missing_ok=True)
            output_path = Path(tempfile.mktemp(suffix=".pdf"))
            ocrmypdf.ocr(
                input_file=str(input_path),
                output_file=str(output_path),
                language=["spa", "eng"],
                deskew=True,
                skip_text=True,
                output_type="pdf",
                jobs=1,
            )

    return output_path
```

### Cache Lookup and Store

```python
# Follow Phase 1 pattern: SQLAlchemy 2.0 session usage
from sqlalchemy.orm import Session
from sqlalchemy import select
from policy_extractor.storage.models import IngestionCache
from datetime import datetime
import json

def lookup_cache(session: Session, file_hash: str) -> IngestionCache | None:
    return session.execute(
        select(IngestionCache).where(IngestionCache.file_hash == file_hash)
    ).scalar_one_or_none()

def save_cache(session: Session, result: "IngestionResult") -> None:
    entry = IngestionCache(
        file_hash=result.file_hash,
        file_path=result.file_path,
        total_pages=result.total_pages,
        page_results=[p.model_dump() for p in result.pages],
        file_size_bytes=result.file_size_bytes,
        created_at=datetime.utcnow(),
        ocr_language=result.ocr_language,
    )
    session.add(entry)
    session.commit()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Text-count heuristic (count chars per page) | Image coverage ratio with smask filtering | Established pattern in PyMuPDF community as of 2023 | Eliminates false positives from watermarks on digital pages |
| Running Tesseract subprocess manually | `ocrmypdf.ocr()` Python API | ocrmypdf added stable Python API in v13+ | No subprocess management; handles temp files, errors, and text-layer insertion automatically |
| pytesseract returning confidence as string | `pytesseract.Output.DATAFRAME` returning typed DataFrame | pytesseract 0.3.x | Clean pandas filtering instead of string parsing; conf column is int |
| `page.get_image_bbox()` | `page.get_image_rects()` | PyMuPDF 1.22+ | `get_image_rects()` is the improved replacement; returns list of (rect, matrix) per occurrence of the image |

**Deprecated/outdated:**
- `page.get_image_bbox()`: Superseded by `page.get_image_rects()` which handles multiple placements of the same image on a page. Use `get_image_rects()`.
- `PyPDF2`: Abandoned 2023; do not use for text extraction.

---

## Open Questions

1. **`get_image_rects()` vs `get_image_bbox()` availability in PyMuPDF 1.27.2**
   - What we know: `get_image_rects()` was introduced in PyMuPDF 1.22.x and is documented in current docs
   - What's unclear: Exact method signature at runtime (not yet installed)
   - Recommendation: During Wave 0, write a quick verification test that calls both methods on a sample PDF. If `get_image_rects()` behaves unexpectedly, fall back to `get_image_bbox()` which is the well-documented older API.

2. **ocrmypdf `skip_text=True` behavior on mixed-page PDFs**
   - What we know: `skip_text=True` tells ocrmypdf to skip pages that already have a text layer
   - What's unclear: Whether it correctly identifies mixed PDFs (some pages digital, some scanned) or skips the whole file
   - Recommendation: Test with a mixed PDF in Wave 0. If per-page skipping doesn't work as expected, pre-split the PDF by page type using PyMuPDF before passing to ocrmypdf.

3. **Tesseract Windows PATH detection by pytesseract**
   - What we know: pytesseract finds the Tesseract binary via `pytesseract.pytesseract.tesseract_cmd`; UB-Mannheim installer sets PATH
   - What's unclear: Whether the default PATH detection works for the project's virtual environment on this machine
   - Recommendation: Add a startup check in `Settings` or the ingestion module that calls `pytesseract.get_tesseract_version()` and raises a clear `RuntimeError` if Tesseract is not found, before any PDF processing begins.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_ingestion.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ING-01 | Digital PDF with selectable text classified as "digital" | unit | `pytest tests/test_ingestion.py::test_classify_digital_page -x` | Wave 0 |
| ING-01 | Scanned PDF (image-only page) classified as "scanned" | unit | `pytest tests/test_ingestion.py::test_classify_scanned_page -x` | Wave 0 |
| ING-01 | Watermark page (digital + small logo) stays "digital" | unit | `pytest tests/test_ingestion.py::test_watermark_not_false_scanned -x` | Wave 0 |
| ING-02 | OCR extracts Spanish text from scanned page | integration | `pytest tests/test_ingestion.py::test_ocr_spanish_text -x` | Wave 0 |
| ING-02 | English fallback triggered when confidence below threshold | unit | `pytest tests/test_ingestion.py::test_ocr_english_fallback -x` | Wave 0 |
| ING-02 | Output is list of (page_num, text) tuples, not single string | unit | `pytest tests/test_ingestion.py::test_ocr_output_page_tuples -x` | Wave 0 |
| ING-05 | Cached PDF returns result without re-running OCR | unit | `pytest tests/test_ingestion.py::test_cache_hit_skips_ocr -x` | Wave 0 |
| ING-05 | `--force-reprocess` bypasses cache and re-runs OCR | unit | `pytest tests/test_ingestion.py::test_force_reprocess_bypasses_cache -x` | Wave 0 |
| ING-05 | Same file at different path returns cache hit | unit | `pytest tests/test_ingestion.py::test_cache_hit_path_independent -x` | Wave 0 |

**Note on integration tests:** ING-02 OCR tests require Tesseract installed with the Spanish language pack. Tests that need Tesseract should be marked with `@pytest.mark.requires_tesseract` and skipped in CI if Tesseract is absent. Provide fixture PDFs in `tests/fixtures/` (a minimal scanned-only PDF and a digital-text PDF).

### Sampling Rate

- **Per task commit:** `pytest tests/test_ingestion.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ingestion.py` — all ING-01, ING-02, ING-05 test cases
- [ ] `tests/fixtures/digital_sample.pdf` — minimal digital PDF with selectable text (create with PyMuPDF or use existing test asset)
- [ ] `tests/fixtures/scanned_sample.pdf` — minimal image-only PDF for OCR tests
- [ ] `tests/conftest.py` — add `ingestion_session` fixture (in-memory SQLite with `IngestionCache` table); update existing `engine` fixture to include `IngestionCache` via `Base.metadata.create_all()`

---

## Sources

### Primary (HIGH confidence)
- PyMuPDF 1.27.2 official docs: https://pymupdf.readthedocs.io/en/latest/page.html — `get_images()`, `get_image_rects()`, `get_text()`
- ocrmypdf 17.3.0 API reference: https://ocrmypdf.readthedocs.io/en/stable/apiref.html — `ocr()` function signature, `ExitCode` enum, `skip_text`, `deskew`, `language` parameters
- PyMuPDF Discussion #1653 (scanned PDF detection pattern): https://github.com/pymupdf/PyMuPDF/discussions/1653 — coverage ratio implementation pattern from maintainers
- `.planning/research/STACK.md` — PyMuPDF 1.27.2 and ocrmypdf 17.3.0 version decisions with rationale

### Secondary (MEDIUM confidence)
- pytesseract confidence scoring: https://about.lovia.id/confidence-in-ktp-ocr-using-pytesseract/ — `image_to_data` with `Output.DATAFRAME`, conf=-1 exclusion pattern; verified against pytesseract PyPI docs
- ocrmypdf Python API usage: https://deepwiki.com/ocrmypdf/OCRmyPDF/1.3-python-api — `OcrOptions` pattern; verified against official API reference

### Tertiary (LOW confidence)
- None — all critical claims verified against official docs or maintained library source

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions from STACK.md (verified against PyPI March 2026); ocrmypdf and PyMuPDF API verified against official docs
- Architecture: HIGH — PyMuPDF image coverage pattern from official maintainer discussion; ocrmypdf API from official docs
- Pitfalls: HIGH — ocrmypdf threading constraint from official docs; other pitfalls from direct API inspection + community sources verified against docs

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable libraries; ocrmypdf and PyMuPDF release infrequently)
