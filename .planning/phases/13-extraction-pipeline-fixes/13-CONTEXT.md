# Phase 13: Extraction Pipeline Fixes - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix systematic extraction errors before any UI is built on top of them. Four improvements: prompt enhancement with per-insurer overlays, post-extraction financial cross-validation, auto-OCR fallback for zero-text digital pages, and configurable per-insurer field exclusion. Does NOT include UI, reports, corrections table, or golden dataset expansion.

</domain>

<decisions>
## Implementation Decisions

### Prompt improvement strategy
- **D-01:** Add explicit field-mapping rules to the prompt (not few-shot examples) to prevent known value swaps — financiamiento/otros_servicios, folio/clave, subsecuentes/primer_pago
- **D-02:** Per-insurer prompt overlay system — base prompt with insurer-specific rules appended. Auto-detect insurer from PDF text in a lightweight first pass, then route to the appropriate overlay
- **D-03:** Start with base prompt + 1 Zurich overlay as proof of concept. Framework supports adding more overlays later
- **D-04:** Target all prompt-fixable errors from v2-extraction-errors.md: value swaps (#3-4, #6-7), wrong source (#1, #5), hallucination (#2), and irrelevant fields (#8)
- **D-05:** Add page-level hints — tag pages containing financial breakdown tables with `[FINANCIAL BREAKDOWN TABLE BELOW]` before the page text
- **D-06:** Bump prompt version to v2.0.0 (major) — clear break from v1.x prompts, aligns with milestone version

### Post-extraction validation
- **D-07:** New `validation_warnings` JSON column on polizas table via Alembic migration — stores list of `{field, message, severity}` objects
- **D-08:** Validation is annotate-only — always save the extraction, never block. Better to have data with warnings than no data
- **D-09:** Financial cross-check: primer_pago + subsecuentes must be within 1% of prima_total. Strict tolerance — flags even small rounding differences
- **D-10:** Build an extensible validator registry so new checks can be added easily. Start with financial invariants + date logic (inicio_vigencia < fin_vigencia, fecha_emision <= inicio_vigencia)

### Field exclusion list
- **D-11:** Per-insurer configuration file (YAML/JSON) mapping insurer name to excluded field names
- **D-12:** Exclusion applies to ALL campos_adicionales — poliza, asegurado, and cobertura level
- **D-13:** Start with empty default list — user configures what to exclude. No risk of dropping useful fields
- **D-14:** Excluded fields are silently dropped before save — no logging, no warnings

### Auto-OCR fallback
- **D-15:** Per-page reclassification: any "digital" page with fewer than configurable threshold characters is reclassified as "scanned" and OCR is applied
- **D-16:** Whole-PDF retry: if extraction returns all-null core fields after per-page reclassification, re-run the entire PDF through OCR pipeline regardless of classification
- **D-17:** Fix the ocrmypdf call bug (error #10) — likely needs path quoting for filenames with spaces. Add try/except around OCR calls so a single PDF failure doesn't crash the batch
- **D-18:** Update page classification from "digital" to "scanned (auto-reclassified)" in the ingestion result — preserves audit trail
- **D-19:** Character threshold configurable via `OCR_MIN_CHARS_THRESHOLD` in config.py Settings

### Claude's Discretion
- Exact implementation of insurer auto-detection (regex on aseguradora names vs text pattern matching)
- Validator registry pattern (class-based, decorator-based, or simple function list)
- YAML vs JSON for per-insurer config file format
- Exact wording of financial validation warning messages
- How to detect financial table pages for tagging

</decisions>

<specifics>
## Specific Ideas

- Per-insurer prompts prevent the base prompt from becoming overcomplicated — each insurer's quirks stay isolated in their overlay
- The Zurich auto policy (112234653_Poliza.pdf) is the reference test case — errors #1-8 are documented with expected values
- "Poliza 8650156226.pdf" is the reference for auto-OCR fallback — 3-page digital PDF with 0 extractable text
- "Poliza - 001_LGS-RCGRA_07013104_01_0.pdf" is the reference for the ocrmypdf call bug — filename with spaces

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Extraction errors (the problem definition)
- `.planning/v2-extraction-errors.md` — All 10 documented errors with expected values, error patterns, and recommended fixes

### Current extraction pipeline
- `policy_extractor/extraction/prompt.py` — Current SYSTEM_PROMPT_V1 (lines 7-55), assemble_text() (lines 58-74), PROMPT_VERSION_V1 (line 5)
- `policy_extractor/extraction/verification.py` — verify_no_hallucination() post-hoc check (lines 8-39)
- `policy_extractor/extraction/client.py` — parse_and_validate() (lines 46-81), extract_with_retry()
- `policy_extractor/extraction/__init__.py` — extract_policy() orchestration (lines 19-69)

### Ingestion and OCR
- `policy_extractor/ingestion/classifier.py` — classify_page() with PAGE_SCAN_THRESHOLD=0.80 (lines 11-49)
- `policy_extractor/ingestion/ocr_runner.py` — ocr_with_fallback() (lines 83-112), run_ocr() (lines 14-46)
- `policy_extractor/ingestion/__init__.py` — ingest_pdf() (lines 28-144)

### Data models and storage
- `policy_extractor/schemas/poliza.py` — PolicyExtraction with campos_adicionales dict (line 51), financial fields (lines 34-38)
- `policy_extractor/storage/models.py` — Poliza ORM model (lines 15-61), campos_adicionales JSON column
- `policy_extractor/storage/writer.py` — upsert_policy() (lines 54-123)
- `policy_extractor/config.py` — Settings class (lines 8-27)

### Research
- `.planning/research/SUMMARY.md` — v2.0 research synthesis
- `.planning/research/PITFALLS.md` — Known pitfalls including auto-OCR threshold gate

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `verify_no_hallucination()` in verification.py — extend this pattern for financial validation (check source text for values)
- `Settings` class in config.py — add OCR_MIN_CHARS_THRESHOLD here
- `SYSTEM_PROMPT_V1` in prompt.py — base for v2.0.0 prompt, overlay system extends this
- `classify_page()` in classifier.py — add char count check after classification
- Alembic migration infrastructure — use for adding validation_warnings column

### Established Patterns
- Lazy imports inside function bodies (used throughout CLI and API entry points)
- Pydantic BaseSettings for configuration
- Alembic render_as_batch=True for SQLite migrations
- Inspector guards on add_column to prevent duplicate column errors on fresh DBs

### Integration Points
- `ingest_pdf()` — add auto-OCR reclassification logic after classify_all_pages()
- `extract_policy()` — add validation step after verify_no_hallucination()
- `upsert_policy()` — apply field exclusion before saving campos_adicionales
- `parse_and_validate()` — no changes needed (schema validation stays as-is)
- `assemble_text()` — add financial page tagging here

</code_context>

<deferred>
## Deferred Ideas

- Per-insurer prompt overlays for AXA, MAPFRE, and remaining 7 insurers — expand after Zurich overlay proves the pattern (Phase 17 or backlog)
- Confidence-based field flagging from Claude self-reported confidence — needs empirical validation against correction log (Phase 15+)
- Prompt improvement for coberturas extraction accuracy — not in documented errors, revisit if issues emerge

</deferred>

---

*Phase: 13-extraction-pipeline-fixes*
*Context gathered: 2026-03-20*
