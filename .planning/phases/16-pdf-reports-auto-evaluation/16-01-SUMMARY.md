---
phase: 16-pdf-reports-auto-evaluation
plan: 01
subsystem: ui
tags: [fpdf2, pyyaml, pdf-generation, reports, per-insurer-config, fastapi]

# Dependency graph
requires:
  - phase: 15-hitl-review-workflow
    provides: corrections table, poliza review page with header bar
  - phase: 14-web-ui-foundation
    provides: poliza_detail.html, poliza_views.py, UI router pattern

provides:
  - policy_extractor/reports/ module with generate_poliza_report() API
  - PolizaReportPDF(FPDF) class for per-insurer branded PDF rendering
  - load_insurer_config() with YAML config per insurer and lru_cache
  - YAML configs for default, zurich, axa, gnp insurers
  - GET /ui/polizas/{id}/report async download route with run_in_executor
  - Descargar Reporte button on detail page and review page

affects: [16-02, 16-03, 17-golden-dataset-expansion]

# Tech tracking
tech-stack:
  added: [fpdf2>=2.8.7, pyyaml>=6.0]
  patterns:
    - Per-insurer YAML config loaded via lru_cache(maxsize=16) — zero file I/O after first call
    - fpdf2 PolizaReportPDF subclass with header/footer/section methods — one instance per request
    - async def route wraps synchronous fpdf2 via asyncio.get_event_loop().run_in_executor()
    - PDF content verified in tests using PyMuPDF (fitz) text extraction — avoids compression issues

key-files:
  created:
    - policy_extractor/reports/__init__.py
    - policy_extractor/reports/renderer.py
    - policy_extractor/reports/config_loader.py
    - policy_extractor/reports/configs/default.yaml
    - policy_extractor/reports/configs/zurich.yaml
    - policy_extractor/reports/configs/axa.yaml
    - policy_extractor/reports/configs/gnp.yaml
    - tests/test_reports.py
  modified:
    - pyproject.toml
    - policy_extractor/api/ui/poliza_views.py
    - policy_extractor/templates/poliza_detail.html
    - policy_extractor/templates/poliza_review.html
    - tests/test_ui_pages.py

key-decisions:
  - "Used helvetica built-in font (not DejaVuSans TTF) — fpdf2 2.8.x ships without font files in data/; helvetica handles Latin/Spanish characters including accents and n-tilde correctly"
  - "PDF content tests use PyMuPDF (fitz) text extraction — fpdf2 compresses PDF streams by default; Latin-1 decode or raw byte search is unreliable; fitz.open(stream=bytes) gives verified text"
  - "lru_cache on _load_config_by_name(normalized_name) — normalize before caching so 'Zurich', 'zurich', 'ZURICH' all hit same cache entry"
  - "set_auto_page_break(auto=True, margin=15) — prevents table content from overflowing page bottom"

patterns-established:
  - "FPDF subclass with header()/footer() override — called automatically on each new page"
  - "Per-section _render_*() private methods — clear separation, easy to extend or reorder"
  - "New PolizaReportPDF instance per request — FPDF is stateful, not thread-safe, run_in_executor provides isolation"

requirements-completed: [RPT-01, RPT-02]

# Metrics
duration: 15min
completed: 2026-03-23
---

# Phase 16 Plan 01: PDF Reports Module Summary

**fpdf2-based per-insurer PDF report generator with YAML config system and download route on detail and review pages**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-23T00:00:00Z
- **Completed:** 2026-03-23
- **Tasks:** 2 (+ TDD RED commit)
- **Files modified:** 12

## Accomplishments

- Full PDF report module at `policy_extractor/reports/` — `generate_poliza_report()` public API returns a valid bytearray in <0.1s (well under 5s target)
- Per-insurer YAML configs for zurich, axa, gnp, and default fallback — brand_color drives header bar RGB, field_order controls info section layout
- Async download route `GET /ui/polizas/{id}/report` uses `run_in_executor` to keep FastAPI event loop non-blocking
- "Descargar Reporte" button (red background) on both poliza detail page and review page per D-03
- 10 new tests pass (8 unit + 2 integration), 20 total in affected test files

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `9f8c193` (test)
2. **Task 1 GREEN: Reports module** - `11f034d` (feat)
3. **Task 2: Download route + buttons** - `880d2e1` (feat)

## Files Created/Modified

- `policy_extractor/reports/__init__.py` - generate_poliza_report() public API
- `policy_extractor/reports/renderer.py` - PolizaReportPDF(FPDF) with 6 section renderers
- `policy_extractor/reports/config_loader.py` - load_insurer_config() with lru_cache
- `policy_extractor/reports/configs/default.yaml` - Fallback config (brand_color: [50,50,50])
- `policy_extractor/reports/configs/zurich.yaml` - Zurich config (brand_color: [0,82,160])
- `policy_extractor/reports/configs/axa.yaml` - AXA config (brand_color: [0,0,175])
- `policy_extractor/reports/configs/gnp.yaml` - GNP config (brand_color: [0,128,0])
- `pyproject.toml` - Added fpdf2>=2.8.7 and pyyaml>=6.0 dependencies
- `policy_extractor/api/ui/poliza_views.py` - Added poliza_report() async route
- `policy_extractor/templates/poliza_detail.html` - Added Descargar Reporte button
- `policy_extractor/templates/poliza_review.html` - Added Descargar Reporte button in header
- `tests/test_reports.py` - 8 unit tests for report module
- `tests/test_ui_pages.py` - 2 integration tests for report download route

## Decisions Made

- Used `helvetica` built-in font instead of DejaVuSans TTF — fpdf2 2.8.x does not ship font files; helvetica handles Spanish accents (accented vowels, n-tilde) via latin-1 encoding
- PDF content tests use PyMuPDF (`fitz`) for text extraction — fpdf2 compresses stream content by default making raw byte search unreliable; fitz gives verified extracted text
- lru_cache applied to normalized name helper — `_load_config_by_name(normalized_name)` ensures "Zurich", "zurich", "ZURICH" all hit same cache entry

## Deviations from Plan

**1. [Rule 1 - Bug] Used helvetica instead of DejaVuSans TTF**
- **Found during:** Task 1 (renderer implementation)
- **Issue:** Plan specified `add_font("dejavu", fname="DejaVuSans.ttf")` but fpdf2 2.8.x ships no TTF font files in its package directory — `add_font()` would raise `FileNotFoundError` at runtime
- **Fix:** Used `self._font_family = "helvetica"` (built-in fpdf2 font) which correctly renders Spanish characters via WinAnsi/latin-1 encoding. All 8 tests pass and PDF content verified via PyMuPDF extraction
- **Files modified:** `policy_extractor/reports/renderer.py`
- **Committed in:** `11f034d`

**2. [Rule 1 - Bug] Used PyMuPDF (fitz) for test content verification**
- **Found during:** Task 1 (test implementation)
- **Issue:** Plan said "fpdf2 embeds text as literal strings in PDF stream" but fpdf2 compresses streams by default — raw byte search (`b"TEST-123" in result`) returns False
- **Fix:** Tests use `fitz.open(stream=bytes(pdf_bytes), filetype="pdf")` to extract text for verification — PyMuPDF is already in project dependencies (pymupdf>=1.27.2)
- **Files modified:** `tests/test_reports.py`
- **Committed in:** `9f8c193`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — library behavior bugs vs plan assumptions)
**Impact on plan:** Both fixes were necessary for the implementation to work at all. No scope creep. All acceptance criteria met.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## User Setup Required

None — no external service configuration required. fpdf2 and pyyaml are pure Python dependencies installed via pip.

## Next Phase Readiness

- PDF report module is ready for Phase 16 Plan 02 (auto-evaluation trigger)
- Per-insurer YAML configs at `policy_extractor/reports/configs/` are extensible — add `{insurer}.yaml` to support new insurers without code changes
- Report download route tested and verified; ready for user testing

---
*Phase: 16-pdf-reports-auto-evaluation*
*Completed: 2026-03-23*
