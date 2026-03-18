# Project Research Summary

**Project:** extractor_pdf_polizas
**Domain:** Insurance policy PDF data extraction — LLM-powered, local-first, Python CLI + API
**Researched:** 2026-03-17
**Confidence:** HIGH

## Executive Summary

This project is an Intelligent Document Processing (IDP) system purpose-built for a Mexican insurance agency that processes ~200 policies per month from ~10 insurers across 50-70 distinct PDF formats. The expert approach is not template-based parsing — that approach requires O(n) maintenance across insurer formats and breaks silently on any layout change. The correct approach is a hybrid pipeline: classify each PDF as digital-text vs. scanned, apply OCR pre-processing only for scanned documents using ocrmypdf + Tesseract (with Spanish language pack), then send the PDF as a native document block to Claude via the Anthropic SDK. Structured JSON output is enforced through Pydantic v2 schemas and the `instructor` library. Extracted data is persisted to a SQLite database using a hybrid schema (core columns for queryable fields, JSON blob for insurer-specific extras). The entire system runs locally on Windows with a Typer CLI as the primary interface and a FastAPI server scaffolded for future web access.

The recommended stack is well-established: Python 3.11+, anthropic SDK 0.85.0, instructor 1.14.5, PyMuPDF 1.27.2, pydantic 2.12.5, SQLAlchemy 2.0.48, ocrmypdf 17.3.0, FastAPI 0.135.1, and Typer 0.24.1. All versions are verified against PyPI as of March 2026. The uv package manager is recommended over pip for reliable Windows installation of binary dependencies. At 200 policies/month, Claude API costs are estimated at $10-30/month — economically trivial compared to the manual labor replaced.

The top risks are architectural, not technical: (1) using a flat database schema that cannot represent multiple insured parties per policy — this must be a one-to-many table relationship from day one; (2) storing dates and currency amounts without normalization — schema must enforce ISO 8601 dates and decimal currency with a currency code field before any extraction is built; (3) skipping extraction provenance (model ID, prompt version, file hash) — without this, targeted re-extraction after bug fixes or schema changes is impossible. All three of these must be designed into Phase 1 before any LLM calls are made. They are non-retrofittable.

---

## Key Findings

### Recommended Stack

The core pipeline is: PyMuPDF detects whether a PDF has selectable text. Digital-text PDFs go directly to Claude as base64 document blocks. Scanned PDFs are first processed by ocrmypdf (which calls Tesseract internally, supports Spanish + English), and the OCR-enhanced PDF is sent to Claude — Claude uses the text layer as an anchor alongside the visual, improving accuracy over raw OCR alone. Claude's native PDF support (as of February 2025) processes each page as both an image and extracted text simultaneously, making it superior to the old pattern of running OCR then sending text-only to the LLM.

`instructor` wraps the anthropic SDK to enforce Pydantic-defined structured output, handling validation retries automatically. This eliminates the need to manually parse JSON from Claude's response text. SQLAlchemy 2.0 provides a single ORM layer that works with SQLite now and PostgreSQL later if a web UI is ever added — same code, different connection string. LangChain is explicitly ruled out: it adds abstraction overhead with no benefit for a single-provider, single-task pipeline and has documented version compatibility issues.

**Core technologies:**
- Python 3.11+: runtime — required by ocrmypdf 17.x; best Windows ecosystem stability
- anthropic SDK 0.85.0: Claude API client — native PDF document block support; handles digital and scanned in one call
- instructor 1.14.5: structured LLM output — wraps anthropic SDK to enforce pydantic schemas; automatic retry on validation failure
- pydantic 2.12.5: data validation and output schema — defines PolicyData, Insured, Coverage models; used end-to-end
- PyMuPDF 1.27.2: PDF parsing — detects digital vs. scanned; extracts text for routing decision; no external MuPDF install required since 1.24.0
- ocrmypdf 17.3.0: OCR pre-processing for scanned PDFs — Tesseract-based; Spanish language pack built-in; preserves PDF structure
- SQLAlchemy 2.0.48: ORM — SQLite for v1 local operation; PostgreSQL-ready for v2 migration
- FastAPI 0.135.1: API layer — native pydantic v2 integration; auto-generates OpenAPI docs; scaffolded in v1, activated in v2
- Typer 0.24.1: CLI — same type-hint pattern as FastAPI; single-file and batch commands

**Critical Windows notes:** Tesseract must be installed separately (UB-Mannheim build) with the Spanish language pack. Poppler must be installed separately if pdf2image is used. Use `uv` instead of pip for faster installs and reliable binary dependency resolution on Windows.

### Expected Features

The core MVP is driven by table stakes that every insurance agency expects. Missing any P1 feature means the system does not do its job.

**Must have — P1 (table stakes):**
- Digital PDF text extraction — direct path for non-scanned PDFs; fast, no AI cost
- Scanned PDF OCR pipeline — required for the Mexican insurance document mix
- Claude API extraction with structured JSON output — the core value proposition; template-based extraction does not scale across 50-70 structures
- Core schema extraction: policy number, insurer, contractor, insured parties (array), validity dates, premium, payment info, agent, coverages (array with type/amount/deductible)
- PDF SHA-256 fingerprinting for idempotency — prevents duplicate records on re-run
- Local SQLite database storage — persistence for 200+/month
- CLI: single-file and batch-folder processing modes
- Spanish and English language support — document set is explicitly mixed
- Per-file error handling with batch continuation — one bad PDF must not abort 199 others
- Progress feedback during batch runs

**Should have — P2 (differentiators after validation):**
- Confidence scoring per field — tells operators which values need human review
- Extraction provenance logging (source_file_hash, model_id, prompt_version, timestamp)
- JSON export flag (--export) — downstream integrations without waiting for web API
- Dry-run / preview mode — validates new insurer formats without committing to DB
- Insurer auto-detection as a classification step
- Extraction quality summary report at end of batch

**Defer to v2+:**
- Web UI for data review and editing
- Excel / CSV export
- Full REST API (FastAPI is scaffolded but not activated in v1)
- Policy comparison and analytics
- Renewal / expiry alerting
- Re-extraction pipeline for schema migrations

### Architecture Approach

The architecture is a layered pipeline: Entry Layer (CLI or future API) → Ingestion Layer (PDF loading + digital/scanned classification) → Extraction Layer (Claude API with Pydantic schema contract) → Validation Layer (Pydantic parsing + domain-specific field validators) → Storage Layer (SQLite with hybrid schema: core columns + JSON blob). The FastAPI query layer sits alongside storage for future web access. Each layer has a single responsibility and communicates via Pydantic models, so Claude API concerns are fully isolated in `extraction/` and storage concerns are fully isolated in `storage/`. The `data/raw/` folder saves every full Claude API response as JSON — this enables re-processing without re-paying API costs when schemas evolve.

**Major components:**
1. CLI (cli.py / Typer) — orchestrates single-file and batch processing; handles error aggregation and progress display
2. Ingestion layer (ingestion/loader.py + detector.py) — reads PDF bytes; routes digital PDFs directly and scanned PDFs through ocrmypdf
3. Extraction layer (extraction/client.py + schemas.py + prompts.py) — sends PDF to Claude via document blocks; parses structured JSON response into typed Pydantic models
4. Validation layer (validation/validators.py) — post-extraction domain rules: date coherence, currency format, RFC patterns; logs warnings, does not block persistence
5. Storage layer (storage/database.py + models.py + writer.py) — persists core columns to SQLite; JSON blob for insurer-specific extras; saves raw API response to data/raw/
6. API layer (api/main.py + serializers.py) — thin FastAPI layer; reads from DB; no business logic; scaffolded in v1

**Recommended build order (from architecture research):**
1. schemas.py — all components depend on the data contract; define first
2. extraction/client.py — prove Claude integration works on a sample PDF
3. storage/database.py + models.py — define DB schema based on extraction output
4. storage/writer.py — proves end-to-end flow
5. cli.py single-file mode — wires full pipeline
6. validation/validators.py — incremental; not a blocker for MVP
7. cli.py batch mode — extends single-file with loop + error handling
8. api/main.py — built last; reads from already-populated DB

### Critical Pitfalls

1. **Flat schema for multiple insured parties** — Design `insured_persons` and `insured_assets` as separate tables with foreign keys to policies from day one. A flat `insured_name` string column cannot be migrated cleanly after data is in production. This is explicitly required ("Manejo de múltiples asegurados") and must be in Phase 1.

2. **No output schema validation — silent bad records in DB** — Use instructor + Pydantic to validate every Claude response before writing to the database. Never use `json.loads()` on Claude's text response without schema enforcement. Instruct Claude to return `null` for missing fields, not invented values like "N/A" or "desconocido."

3. **Date and currency format inconsistency** — Define canonical formats in the Pydantic schema before writing the first extraction: ISO 8601 dates (`YYYY-MM-DD`), decimal currency with a separate currency code field. Mexican insurers use both DD/MM/YYYY and MM/DD/YYYY; some use European decimal notation. The LLM extracts whatever it sees — normalization is the system's responsibility, not the model's.

4. **No extraction provenance — cannot re-extract targeted records** — Every DB record must store `source_file_hash`, `model_id`, `prompt_version`, and `extracted_at`. Without this, when a bug is found or schema is extended, there is no way to identify which records are affected. This is 4 extra columns at schema creation time with zero migration cost.

5. **Sending scanned PDFs raw to Claude without OCR pre-processing** — Claude vision can read scanned PDFs but silently misreads numbers, dates, and amounts from low-resolution or skewed scans. Use ocrmypdf to add a text layer to scanned PDFs before sending to Claude. Claude then gets both the OCR text and the visual, dramatically improving accuracy for financial fields.

---

## Implications for Roadmap

Based on combined research, the following phase structure is recommended. The critical insight is that **Phase 1 must be data model design, not code** — three of the eight critical pitfalls can only be prevented by getting the schema right before extraction is built.

### Phase 1: Foundation — Data Model, Schema, and Pipeline Skeleton

**Rationale:** Three non-retrofittable decisions must be made before writing a single extraction call: the Pydantic extraction schema (defines the contract for all downstream code), the database schema (must include one-to-many for insured parties and provenance columns), and canonical formats for dates and currency. Getting these wrong has HIGH recovery cost. The build order from architecture research explicitly puts schemas.py first.

**Delivers:** Verified project structure, Pydantic models for all extracted fields, SQLite schema with related tables, canonical format definitions, environment setup with uv and python-dotenv, and a single working extraction call on one sample PDF.

**Addresses (from FEATURES.md P1):** Core schema extraction, structured JSON output, local database storage, PDF hash idempotency.

**Avoids (from PITFALLS.md):** Flat schema for multi-insured (Pitfall 8), date/currency inconsistency (Pitfall 5), no provenance metadata (Pitfall 6), no output schema validation (Pitfall 2).

**Research flag:** Standard patterns — Pydantic v2 model definition and SQLAlchemy table design are well-documented. No additional research needed.

---

### Phase 2: Ingestion and OCR Pipeline

**Rationale:** Before the extraction layer can be generalized, the PDF routing logic must work reliably. The digital-vs-scanned decision determines which processing path is taken and whether ocrmypdf is invoked. This is an isolated component (ingestion/) with no Claude API dependency — it can be built and tested with local PDFs from each of the 10 insurers without API costs.

**Delivers:** PyMuPDF-based text coverage detector, ocrmypdf integration with Spanish language pack, PDF byte loader, routing logic that tags each PDF as digital or scanned, and tests against sample PDFs from each insurer.

**Addresses (from FEATURES.md P1):** Digital PDF text extraction, scanned PDF OCR pipeline, Spanish and English language support.

**Avoids (from PITFALLS.md):** Scanned PDFs sent raw to LLM (Pitfall 1). This phase builds the defense before the LLM layer is even written.

**Research flag:** Standard patterns for PyMuPDF text detection and ocrmypdf invocation. Windows-specific: verify Tesseract + Spanish language pack installation before this phase.

---

### Phase 3: LLM Extraction Layer

**Rationale:** With the data contract (Phase 1) and ingestion routing (Phase 2) in place, the extraction layer can be built against a stable interface. The instructor + Pydantic pattern enforces schema validation on every Claude response. This phase also establishes the token budget and model pinning practices that prevent cost blowouts.

**Delivers:** `extraction/client.py` sending PDFs as base64 document blocks, instructor integration enforcing Pydantic schema on Claude output, system prompt with canonical format instructions, model pinned to a specific dated version (not `latest`), token logging per call, and extraction tests on a golden dataset of sample PDFs from each insurer.

**Addresses (from FEATURES.md P1):** LLM-powered field extraction, core field extraction (all required fields), Spanish/English language support (Claude handles natively).

**Avoids (from PITFALLS.md):** No output schema validation (Pitfall 2), generic prompt failing minority layouts (Pitfall 3), uncontrolled API costs from token bloat (Pitfall 4), model drift without regression tests (Pitfall 7).

**Research flag:** Needs phase research. The two-pass strategy (classification pass then extraction pass) for handling 50-70 insurer layouts is a key design decision. How to structure insurer-specific prompt modifiers without creating hard-coded templates needs concrete design before implementation.

---

### Phase 4: CLI and Batch Processing

**Rationale:** With extraction working end-to-end for a single file, the CLI and batch loop can be built on top. Error handling, progress feedback, and idempotency checks (PDF hash lookup before extraction) belong here. This phase delivers the primary user interface stated in the project requirements.

**Delivers:** Typer CLI with `extract` (single file) and `batch` (folder) subcommands, per-file error handling with batch continuation, progress display with `rich`, extraction status output (OK / low-confidence / failed), PDF hash deduplication check, and a final summary report after batch runs.

**Addresses (from FEATURES.md P1):** CLI single-file and batch-folder processing, idempotent re-processing, processing status / progress feedback, basic error reporting.

**Avoids (from PITFALLS.md):** No progress feedback causing user cancellation (UX Pitfall), extraction errors crashing the whole batch (UX Pitfall), synchronous extraction being too slow for large batches (Performance Trap).

**Research flag:** Standard patterns — Typer CLI and asyncio concurrency with semaphore for rate-limit-safe parallel API calls are well-documented.

---

### Phase 5: Storage, Validation, and Quality Visibility

**Rationale:** The storage layer and domain validation rules are added after the extraction shape is confirmed by real data. This phase also adds the P2 differentiators — confidence scoring, provenance logging, dry-run mode, and the extraction quality report — that transform the tool from a data mover into a trustworthy extraction system.

**Delivers:** SQLAlchemy models with hybrid schema (core columns + JSON blob), `storage/writer.py` that persists validated Pydantic objects, field-level validators for dates/RFC/currency, raw Claude response saved to `data/raw/`, confidence scoring per field, provenance logging (model_id, prompt_version, source_file_hash), JSON export flag (`--export`), dry-run / preview mode, and extraction quality summary report.

**Addresses (from FEATURES.md P1+P2):** Local database storage, raw LLM output storage, confidence scoring, extraction provenance, JSON export, dry-run mode, insurer auto-detection, extraction quality report.

**Avoids (from PITFALLS.md):** No raw response storage (Pitfall 4/Anti-Pattern 4), storing full PDF binary in DB (Performance Trap), no pagination on API output (Performance Trap — add limit/offset from the start).

**Research flag:** Standard patterns for SQLAlchemy hybrid schema with JSON columns. No additional research needed.

---

### Phase 6: FastAPI Layer and Security Hardening

**Rationale:** The FastAPI server is scaffolded last because it reads from an already-validated, already-populated database. There is no business logic in the API layer — it is a thin serialization layer. Security hardening (API key auth, input validation, PII-safe logging) is addressed here before any network exposure.

**Delivers:** FastAPI app with query endpoints (filter by insurer, date range, policy number), Pydantic response serializers, API key authentication (even for local use — policy data is PII-heavy), path validation on CLI inputs, PII-safe logging (metadata only, never field values), and `.env` + `.gitignore` setup for API key management.

**Addresses (from FEATURES.md P1):** Local database query access; foundation for v2 web UI.

**Avoids (from PITFALLS.md):** Exposing full DB via API with no auth (Security Mistake), logging full PDF text content (Security Mistake), storing API key in source code (Security Mistake).

**Research flag:** Standard patterns — FastAPI with API key auth is well-documented. No additional research needed.

---

### Phase Ordering Rationale

- Phases 1-2 are pure setup: no LLM calls, no API costs. They establish the non-negotiable foundations that cannot be changed later without HIGH recovery cost.
- Phase 3 is the highest-risk phase technically (LLM behavior, prompt engineering, token costs) and benefits from having stable schemas and routing in place before it begins.
- Phase 4 delivers the stated user interface requirement. It can only be built after single-file extraction works (Phase 3).
- Phase 5 adds observability and trust signals. P2 features belong here because they require real extraction data to calibrate (confidence thresholds, quality reports).
- Phase 6 is last because FastAPI adds no value until the database has real data and the CLI workflow is validated by actual agency use.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (LLM Extraction Layer):** The two-pass classification + targeted extraction approach for 50-70 insurer layouts needs concrete design. What insurer-specific signals should the classification prompt look for? How should prompt modifiers be structured and stored? This is the highest-risk design decision in the project.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Pydantic v2 model definition and SQLAlchemy 2.0 table design are extremely well-documented.
- **Phase 2:** PyMuPDF text coverage detection and ocrmypdf CLI invocation follow standard patterns.
- **Phase 4:** Typer CLI and asyncio batch processing with semaphore-based rate limiting are well-documented.
- **Phase 5:** SQLAlchemy hybrid JSON column pattern is documented; confidence scoring as a Pydantic field is straightforward.
- **Phase 6:** FastAPI with API key dependency injection is standard.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI March 2026; Claude API constraints verified from official docs; version compatibility matrix confirmed |
| Features | HIGH | Corroborated across InsurGrid, KlearStack, Docsumo, GroupBWT, AltexSoft, AWS IDP documentation; competitor feature analysis provides external validation |
| Architecture | HIGH (Claude API) / MEDIUM (pipeline patterns) | Claude PDF support from official docs is HIGH confidence; pipeline layer separation patterns are MEDIUM — community consensus from multiple sources, no single authoritative reference |
| Pitfalls | HIGH | Multiple verified sources; several pitfalls come from official Claude API docs; post-mortems corroborate LLM-specific failure modes |

**Overall confidence:** HIGH

### Gaps to Address

- **Two-pass classification strategy for 50-70 insurer layouts:** Research describes the pattern (classify then extract) but does not provide a concrete implementation for the Mexican insurer set. The classification prompt, the per-insurer hint registry structure, and the decision threshold for when hints apply need design during Phase 3 planning.

- **Confidence scoring calibration:** The field-level confidence flag from Claude is binary (high/low) without explicit numerical scores from the API. Research does not identify a reliable way to get numerical confidence from Claude. The implementation approach — likely asking Claude to self-report confidence per field in the structured output — needs validation against real extraction data. Defer threshold-setting until Phase 5 has real data.

- **Async batch concurrency limits:** The research recommends asyncio + semaphore for concurrent extraction but does not specify the optimal semaphore count for Claude API rate limits on the specific Anthropic account tier. This needs empirical testing during Phase 4 implementation.

- **ocrmypdf performance on low-DPI scans from Mexican insurers:** DPI and scan quality vary significantly across the 10 insurers. Acceptance criteria for OCR quality (what DPI threshold triggers a manual review flag) needs calibration against actual insurer samples during Phase 2.

---

## Sources

### Primary (HIGH confidence)
- [Anthropic PDF Support — Official Docs](https://platform.claude.com/docs/en/build-with-claude/pdf-support) — PDF limits, document block format, Files API, token costs per page
- [Anthropic Batch Processing — Official Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing) — Message Batches API, 50% cost reduction, 24h results
- [Anthropic Rate Limits — Official Docs](https://platform.claude.com/docs/en/api/rate-limits) — retry-after header, 429 vs 529 distinction
- [anthropic PyPI](https://pypi.org/project/anthropic/) — SDK version 0.85.0, verified March 2026
- [instructor PyPI](https://pypi.org/project/instructor/) — version 1.14.5, verified March 2026
- [Instructor + Anthropic Integration](https://python.useinstructor.com/integrations/anthropic/) — structured output pattern with `from_anthropic()` pattern
- [PyMuPDF PyPI](https://pypi.org/project/PyMuPDF/) — version 1.27.2, verified March 2026
- [ocrmypdf PyPI](https://pypi.org/project/ocrmypdf/) — version 17.3.0, Python 3.11+ requirement
- [SQLAlchemy PyPI](https://pypi.org/project/SQLAlchemy/) — version 2.0.48 stable
- [FastAPI PyPI](https://pypi.org/project/fastapi/) — version 0.135.1
- [Typer PyPI](https://pypi.org/project/typer/) — version 0.24.1

### Secondary (MEDIUM confidence)
- [InsurGrid Policy Data Extraction](https://www.insurgrid.com/policy-data-extraction) — competitor feature baseline, carrier detection
- [KlearStack Insurance Data Extraction](https://klearstack.com/insurance-data-extraction) — IDP pipeline overview, multi-format support
- [Docsumo Insurance Data Extraction](https://www.docsumo.com/blogs/data-extraction/insurance-industry) — field extraction standards
- [AltexSoft IDP for Insurance](https://www.altexsoft.com/blog/idp-intelligent-document-processing-insurance/) — IDP feature taxonomy
- [GroupBWT Insurance AI Workflows 2026](https://groupbwt.com/blog/data-extraction-insurance/) — governance requirements, workflow patterns
- [Unstract LLM PDF Extraction 2026](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/) — pipeline pattern comparison
- [LLM Model Drift — By AI Team](https://byaiteam.com/blog/2025/12/30/llm-model-drift-detect-prevent-and-mitigate-failures/) — model drift statistics, golden dataset recommendation
- [Applied AI PDF Parsing Benchmark](https://www.applied-ai.com/briefings/pdf-parsing-benchmark/) — 800+ documents across 7 frontier LLMs
- [SQLite JSON1 Hybrid Schema — Charles Leifer](https://charlesleifer.com/blog/using-the-sqlite-json1-and-fts5-extensions-with-python/) — hybrid column pattern

### Tertiary (MEDIUM-LOW confidence)
- [pdf2image PyPI](https://pypi.org/project/pdf2image/) — version 1.17.0, last release Jan 2024; still maintained but less actively
- [I Tested 7 Python PDF Extractors (2025)](https://dev.to/onlyoneaman/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-akm) — PyMuPDF performance comparison; methodology not disclosed
- [Best Python PDF to Text Libraries: 2026 Evaluation](https://unstract.com/blog/evaluating-python-pdf-to-text-libraries/) — current library landscape; vendor-authored
- [Don't Use LLMs as OCR — Medium (Marta Fernandez)](https://medium.com/@martia_es/dont-use-llms-as-ocr-lessons-learned-from-extracting-complex-documents-db2d1fafcdfb) — scanned PDF pitfall; single practitioner post-mortem

---
*Research completed: 2026-03-17*
*Ready for roadmap: yes*
