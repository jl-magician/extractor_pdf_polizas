---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: complete
stopped_at: Completed 05-storage-api 05-02-PLAN.md
last_updated: "2026-03-18T23:26:45.466Z"
last_activity: "2026-03-18 — Completed Phase 5 Plan 2: export/import/serve CLI, FastAPI CRUD endpoints"
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 10
  completed_plans: 10
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-17)

**Core value:** Extract all available data from any insurance policy PDF automatically — regardless of insurer or format — and store it structured for query and integration.
**Current focus:** Phase 5 — Storage & API (COMPLETE)

## Current Position

Phase: 5 of 5 (Storage & API) — COMPLETE
Plan: 2 of 2 in current phase — COMPLETE
Status: Complete
Last activity: 2026-03-18 — Completed Phase 5 Plan 2: export/import/serve CLI, FastAPI CRUD endpoints

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: ~4 min
- Total execution time: ~0.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 4 min | 2 tasks | 16 files |
| 02-ingestion P01 | 4 min | 2 tasks | 13 files |
| 02-ingestion P02 | 4 min | 2 tasks | 5 files |

**Recent Trend:**
- Last 5 plans: 01-P01, 01-P02, 02-P01, 02-P02
- Trend: fast execution, TDD with auto-fix deviations

*Updated after each plan completion*
| Phase 03-extraction P01 | 4 | 3 tasks | 6 files |
| Phase 03-extraction P02 | 5min | 2 tasks | 3 files |
| Phase 04-cli P01 | 2min | 2 tasks | 5 files |
| Phase 04-cli-batch P02 | 3min | 2 tasks | 3 files |
| Phase 05-storage-api P01 | 8min | 2 tasks | 5 files |
| Phase 05-storage-api P02 | 5min | 2 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-phase]: Claude API chosen for extraction — user has existing API key; handles 50-70 formats without templates
- [Pre-phase]: Local-first, no web until extraction validated
- [Pre-phase]: Data model (Pydantic + SQLite hybrid schema) must be locked in Phase 1 before any LLM calls — non-retrofittable
- [Phase 01-foundation]: Used pip instead of uv (uv not on machine); added setuptools.packages.find to pyproject.toml to scope auto-discovery to policy_extractor* only
- [Phase 01-foundation]: normalize_date returns None for unknown formats rather than ValidationError — extraction layer handles nulls gracefully in batch processing
- [Phase 01-foundation]: Skipped Alembic for Phase 1 — Base.metadata.create_all() sufficient for greenfield DB; Alembic deferred to Phase 5
- [Phase 01-foundation]: Models mirror Pydantic schema field names exactly — same names, same optionality — easing ORM-from-Pydantic mapping in Phase 5
- [Phase 01-foundation]: source_file_hash uses String(64) with index but no UNIQUE constraint — same PDF can be re-extracted with different prompt_version creating new row
- [Phase 02-ingestion P01]: get_image_rects() in PyMuPDF 1.27.2 returns list[Rect] not list[(Rect, Matrix)] — research docs were for older API; fixed inline
- [Phase 02-ingestion P01]: Added is_pdf check in classify_all_pages() because fitz.open() silently opens .txt files as 1-page documents without raising an error
- [Phase 02-ingestion P02]: test_ocr_english_fallback mock output must differ from input_path to avoid early-return on already_done_ocr branch — test fixed to use tmp_path copy
- [Phase 02-ingestion P02]: ingest_pdf checks doc.is_pdf after fitz.open() in addition to try/except to detect non-PDF files consistently
- [Phase 02-ingestion P02]: Cache hit updates file_path to current location informational-only; does not re-persist to DB
- [Phase 03-extraction]: confianza field is plain dict (no strict validation) — Claude may occasionally return values outside high/medium/low; strict validation deferred to Phase 5 if storage requires it
- [Phase 03-extraction]: Provenance fields excluded from Claude tool schema (source_file_hash, model_id, prompt_version, extracted_at set by code, not Claude)
- [Phase 03-extraction]: extract_policy returns PolicyExtraction directly (not tuple) — tests contract; raw response stored in campos_adicionales['_raw_response']
- [Phase 03-extraction]: extract_with_retry uses attempt loop (max_retries + 1 total) not recursion — cleaner retry budget tracking
- [Phase 04-cli P01]: extract_policy return type changed to tuple[PolicyExtraction | None, Usage | None] — CLI needs usage for cost reporting in one call
- [Phase 04-cli P01]: PRICING hardcoded in cli_helpers as haiku/sonnet dict — no network call needed, values stable on short timescale
- [Phase 04-cli P01]: is_already_extracted queries only Poliza.id with limit(1) — minimal DB overhead for idempotency check
- [Phase 04-cli-batch]: Rich console writes to stderr; JSON output goes to stdout for clean pipe behavior
- [Phase 04-cli-batch]: Batch exit code 1 on any failure — shell scripts and CI can detect incomplete runs
- [Phase 05-storage-api]: confianza stored in campos_adicionales['confianza'] in ORM; orm_to_schema extracts back to top-level field — avoids new DB column while preserving round-trip fidelity
- [Phase 05-storage-api]: StaticPool required for in-memory SQLite test engine: each connection creates a new empty DB without it
- [Phase 05-storage-api]: PUT /polizas/{id} updates by ID not by (numero_poliza, aseguradora): REST semantics require update-by-ID, inline update bypasses upsert_policy dedup logic
- [Phase 05-storage-api]: model_dump(mode='json') in all API responses prevents JSONResponse TypeError on Decimal fields

### Pending Todos

None.

### Blockers/Concerns

- [Phase 3]: Two-pass classification strategy for 50-70 insurer layouts needs concrete design during Phase 3 planning (research flagged this as highest-risk design decision)
- [Phase 2 OCR]: Tesseract + Spanish language pack must be installed on Windows before Tesseract-dependent tests run (UB-Mannheim build required) — all non-Tesseract tests pass
- [Phase 4]: Optimal asyncio semaphore count for Claude API rate limits needs empirical testing — unknown until Phase 4

## Session Continuity

Last session: 2026-03-18T23:26:45.463Z
Stopped at: Completed 05-storage-api 05-02-PLAN.md
Resume file: None
