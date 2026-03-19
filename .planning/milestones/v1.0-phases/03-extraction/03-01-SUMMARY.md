---
phase: 03-extraction
plan: 01
subsystem: api
tags: [anthropic, pydantic, tool-use, extraction, confidence, tdd]

# Dependency graph
requires:
  - phase: 02-ingestion
    provides: IngestionResult with pages list that prompt.assemble_text() consumes

provides:
  - confianza dict field on PolicyExtraction (EXT-04 schema contract)
  - EXTRACTION_MODEL, EXTRACTION_MAX_RETRIES, EXTRACTION_PROMPT_VERSION in Settings
  - anthropic>=0.86.0 in project dependencies
  - SYSTEM_PROMPT_V1 with Spanish glossary, confidence levels, anti-hallucination rules
  - assemble_text() to build user message from IngestionResult pages
  - build_extraction_schema() producing simplified JSON schema without Decimal regex noise or provenance fields
  - build_extraction_tool() returning complete Claude tool definition
  - 9 failing unit tests (TDD RED) covering EXT-01 through EXT-05 plus retry, hallucination, provenance, raw response

affects: [03-extraction plan-02 (implements extract_policy to make tests pass), 05-storage (reads confianza field)]

# Tech tracking
tech-stack:
  added: [anthropic==0.86.0]
  patterns:
    - "forced tool_use with tool_choice to guarantee structured output from Claude"
    - "Decimal schema simplification: replace anyOf[number|pattern-string|null] with anyOf[number|null]"
    - "provenance field exclusion from tool input_schema (source_file_hash, model_id, prompt_version, extracted_at set by code, not Claude)"
    - "versioned prompt constant: PROMPT_VERSION_V1 = 'v1.0.0' matches Settings.EXTRACTION_PROMPT_VERSION"
    - "TDD RED: tests written before implementation, import fails until Plan 02"

key-files:
  created:
    - policy_extractor/extraction/prompt.py
    - policy_extractor/extraction/schema_builder.py
    - tests/test_extraction.py
  modified:
    - policy_extractor/schemas/poliza.py
    - policy_extractor/config.py
    - pyproject.toml

key-decisions:
  - "confianza field is plain dict (no strict validation) — Claude may occasionally return values outside high/medium/low; strict validation deferred to Phase 5 if storage requires it"
  - "extract_policy return value is flexible — tuple (PolicyExtraction, raw_dict) OR raw stored in campos_adicionales; Plan 02 implementation decides"
  - "assemble_text joins pages with double newline separators, page markers '--- Page N ---' prefix each page"
  - "provenance fields (source_file_hash, model_id, prompt_version, extracted_at) excluded from Claude tool schema — set programmatically by extraction code"

patterns-established:
  - "TOOL_NAME constant referenced in both build_extraction_schema and build_extraction_tool to prevent name mismatch"
  - "schema simplification: _PROVENANCE_FIELDS set drives removal from both properties and required list"
  - "TDD scaffold: tests mock at anthropic.Anthropic level with MockMessage/MockToolUseBlock/MockUsage helpers"

requirements-completed: [EXT-01, EXT-02, EXT-04, EXT-05]

# Metrics
duration: 4min
completed: 2026-03-18
---

# Phase 3 Plan 01: Extraction Contracts Summary

**Extraction contracts established: confianza schema field, Claude tool schema builder with Decimal simplification, versioned system prompt with Spanish insurance glossary, and 9 failing TDD tests for extract_policy()**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-18T20:28:13Z
- **Completed:** 2026-03-18T20:32:13Z
- **Tasks:** 3
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments
- Added `confianza: dict` field to PolicyExtraction and three extraction settings to config
- Created prompt.py with SYSTEM_PROMPT_V1 (~500 tokens, Spanish glossary, confidence definitions) and assemble_text()
- Created schema_builder.py that strips provenance fields and fixes Decimal anyOf regex noise from tool schema
- Wrote 9 failing unit tests (TDD RED) covering all EXT requirements plus retry, hallucination downgrade, provenance injection, and raw response storage

## Task Commits

Each task was committed atomically:

1. **Task 1: Schema update, config additions, and dependency** - `16fe3c4` (feat)
2. **Task 2: Prompt module and schema builder** - `e388828` (feat)
3. **Task 3: Test scaffold for extraction (mocked API)** - `0041c57` (test)

**Plan metadata:** (docs commit — added after state updates)

_Note: Task 3 is TDD RED phase — tests fail intentionally until Plan 02 implements extract_policy()_

## Files Created/Modified
- `policy_extractor/schemas/poliza.py` - Added `confianza: dict = Field(default_factory=dict)` after campos_adicionales
- `policy_extractor/config.py` - Added EXTRACTION_MODEL, EXTRACTION_MAX_RETRIES, EXTRACTION_PROMPT_VERSION under "# Extraction settings" comment
- `pyproject.toml` - Added `anthropic>=0.86.0` to dependencies list
- `policy_extractor/extraction/prompt.py` - SYSTEM_PROMPT_V1 constant, PROMPT_VERSION_V1 = "v1.0.0", assemble_text() function
- `policy_extractor/extraction/schema_builder.py` - TOOL_NAME, build_extraction_schema(), build_extraction_tool()
- `tests/test_extraction.py` - 9 unit tests with MockMessage/MockToolUseBlock/MockUsage helpers, sample_ingestion_result and valid_extraction_data fixtures

## Decisions Made
- `confianza` is a plain `dict` (no strict Literal validation) — Claude may occasionally return unexpected values; dict is more robust for batch processing
- `test_raw_response_stored` accepts either tuple return or campos_adicionales storage — Plan 02 decides the exact API contract
- Provenance fields explicitly excluded from Claude's tool schema to prevent hallucination of model_id, source hash, etc.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. (ANTHROPIC_API_KEY env var is already managed by Settings class from Phase 1.)

## Next Phase Readiness
- All contracts in place for Plan 02 implementation of `extract_policy()`
- Plan 02 must implement `extract_policy(ingestion_result)` in `policy_extractor/extraction/__init__.py` or `client.py`
- 9 tests waiting to go GREEN when extract_policy() is implemented
- anthropic 0.86.0 installed and verified

---
*Phase: 03-extraction*
*Completed: 2026-03-18*

## Self-Check: PASSED

- FOUND: policy_extractor/schemas/poliza.py
- FOUND: policy_extractor/config.py
- FOUND: policy_extractor/extraction/prompt.py
- FOUND: policy_extractor/extraction/schema_builder.py
- FOUND: tests/test_extraction.py
- FOUND: .planning/phases/03-extraction/03-01-SUMMARY.md
- FOUND commit: 16fe3c4 (Task 1)
- FOUND commit: e388828 (Task 2)
- FOUND commit: 0041c57 (Task 3)
- Pre-existing tests: 42 passed
