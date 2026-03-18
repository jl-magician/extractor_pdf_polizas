# Phase 2: Ingestion - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Reliably route any PDF — digital or scanned — to the correct processing path before touching the LLM. Detect page type, apply OCR to scanned pages, cache results to avoid reprocessing, and return structured text to Phase 3 (extraction). No Claude API calls, no extraction logic — pure PDF preprocessing.

</domain>

<decisions>
## Implementation Decisions

### PDF classification
- Per-page classification — each page is independently classified as digital or scanned
- Detection method: image coverage ratio — if images cover >80% of page area, treat as scanned
- Filter out decorative images (<10% page area) and transparent overlays before calculating coverage to avoid false "scanned" classification from watermarks
- Password-protected or corrupted PDFs: skip with error log (file path + reason), continue processing remaining files

### OCR pipeline
- Basic preprocessing before OCR: deskew + light contrast enhancement (ocrmypdf built-in)
- Language: Spanish-only as primary OCR language
- English fallback: if OCR confidence is low on a page, retry with English language pack
- OCR output preserves page boundaries: return list of (page_number, text) tuples, not concatenated string

### Caching strategy
- Cache key: SHA-256 hash of file content bytes — same file = same hash regardless of filename or location
- Cache storage: SQLite table (`ingestion_cache`) in the existing database — file hash, extracted text, page classifications, timestamps
- Cache invalidation: never auto-invalidate — same hash = same content = same output forever. Only a `--force-reprocess` flag bypasses cache
- Policy-number-based deduplication deferred to Phase 4/5 (policy number isn't known until after extraction)

### Output contract
- Structured Pydantic result object (not plain text) — typed and validated handoff to Phase 3
- Fields: file_hash, file_path, total_pages, list of (page_num, text, classification) per page, source metadata (file size, created date)
- Text only — no page images. Phase 3 sends text to Claude API, not images
- One result per file — if a PDF contains multiple policies, Phase 3 handles splitting

### Claude's Discretion
- Exact image coverage calculation algorithm
- OCR confidence threshold for English fallback retry
- Pydantic model naming and field naming for ingestion result
- Internal module structure within `policy_extractor/ingestion/`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 outputs (upstream contract)
- `policy_extractor/schemas/poliza.py` — PolicyExtraction model that Phase 3 will populate from ingestion output
- `policy_extractor/storage/models.py` — SQLAlchemy models; ingestion_cache table will be added alongside existing tables
- `policy_extractor/storage/database.py` — Engine factory and init_db() that must be extended for cache table
- `policy_extractor/config.py` — Settings class for configuration

### Project scope
- `.planning/REQUIREMENTS.md` — ING-01 (detect PDF type), ING-02 (OCR with Spanish+English), ING-05 (cache results)
- `.planning/ROADMAP.md` — Phase 2 success criteria (4 criteria that must be TRUE)

### Research findings
- `.planning/research/STACK.md` — PyMuPDF and ocrmypdf library versions and rationale
- `.planning/research/ARCHITECTURE.md` — Component boundaries and data flow for ingestion layer
- `.planning/research/PITFALLS.md` — OCR and ingestion pitfalls to avoid

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `policy_extractor/config.py` (Settings class) — extend with OCR-related config (Tesseract path, cache settings)
- `policy_extractor/storage/database.py` (init_db, get_engine) — reuse for ingestion_cache table creation
- `policy_extractor/storage/models.py` (Base, declarative models) — add IngestionCache model here

### Established Patterns
- Pydantic v2 models for data contracts (schemas/) — follow same pattern for ingestion result type
- SQLAlchemy 2.0 Mapped[] annotations with DeclarativeBase — follow for cache model
- python-dotenv for configuration

### Integration Points
- `policy_extractor/ingestion/__init__.py` — stub exists, this is where the ingestion module will live
- Ingestion result feeds into Phase 3 extraction — the Pydantic result model is the contract
- Cache table joins the existing SQLite database alongside polizas/asegurados/coberturas

</code_context>

<specifics>
## Specific Ideas

- Tesseract + Spanish language pack (UB-Mannheim build) must be installed on Windows 11 before this phase works — this is a prerequisite, not something the code installs
- The ingestion layer should be completely independent of the LLM — no Claude API calls, no extraction logic
- Per-page classification with image coverage ratio was chosen specifically because insurance PDFs from Mexican insurers sometimes have watermarks and logos that would confuse simpler text-count heuristics

</specifics>

<deferred>
## Deferred Ideas

- Policy-number-based deduplication at the extraction/storage level (Phase 4/5) — user noted policy numbers are unique and could serve as dedup keys
- Full image preprocessing (denoise, binarization) for low-quality scans — v2 scope (QAL-02)
- Sending page images to Claude vision API for complex layouts — revisit if text-only extraction proves insufficient

</deferred>

---

*Phase: 02-ingestion*
*Context gathered: 2026-03-18*
