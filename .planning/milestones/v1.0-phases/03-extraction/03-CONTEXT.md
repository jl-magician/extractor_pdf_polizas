# Phase 3: Extraction - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract all available policy fields from any PDF using Claude API with validated structured output. Takes `IngestionResult` (text per page) from Phase 2, sends to Claude, returns `PolicyExtraction` Pydantic model with confidence scores. No CLI, no storage — pure extraction logic.

</domain>

<decisions>
## Implementation Decisions

### Prompt strategy
- Single-pass extraction — one Claude API call per PDF, Claude extracts all fields AND classifies insurer/type in a single response
- Detailed system prompt (~500 tokens) explicitly listing every field, explaining Spanish insurance terminology (poliza, prima, vigencia, deducible, etc.), and instructing "return null, never invent values"
- Versioned prompt template — store prompt as versioned constant (e.g., `PROMPT_V1 = "v1.0.0"`), each extraction records which prompt_version produced it (field already exists on PolicyExtraction)
- Text delivery: concatenate all page texts with page separators (`--- Page N ---`) into a single user message

### Confidence scoring
- Claude self-reports confidence for each field in the same extraction response
- Three-level scale: `high` (clearly stated in PDF), `medium` (inferred or partially visible), `low` (guessed or ambiguous)
- Storage: parallel `confianza` dict field on PolicyExtraction — e.g., `{"numero_poliza": "high", "prima_total": "medium", ...}`
- Does NOT bloat main fields — confidence is a separate dict that consumers can ignore

### Extraction error handling
- Retry once on Pydantic validation failure — retry with a refined prompt mentioning the specific validation error
- After retry failure: log the error, return null/partial result so batch processing continues
- Store raw Claude API response alongside extracted data — invaluable for debugging, prompt tuning, audit trail
- Hallucination prevention: BOTH prompt instruction ("null, never invent") AND post-hoc verification of key fields (numero_poliza, aseguradora) against source text — flag mismatches as potential hallucinations

### API integration pattern
- Anthropic Python SDK with tool_use — define PolicyExtraction as a tool schema, Claude returns structured JSON matching the tool definition
- Default model: Haiku (cheapest, ~$0.25/M input) — good enough for structured field extraction from insurance PDFs
- Configurable to Sonnet via Settings class — users can switch to Sonnet if Haiku quality is insufficient for their insurer mix
- Configuration via existing `policy_extractor/config.py` Settings class — add EXTRACTION_MODEL, EXTRACTION_MAX_RETRIES, EXTRACTION_PROMPT_VERSION

### Claude's Discretion
- Exact tool_use schema construction from Pydantic model
- System prompt wording and field descriptions
- Post-hoc hallucination verification algorithm details
- Raw response storage format (JSON field vs separate file)
- How to structure the retry prompt with validation error context

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 outputs (extraction contract)
- `policy_extractor/schemas/poliza.py` — PolicyExtraction model (the target output schema). Has `source_file_hash`, `model_id`, `prompt_version`, `extracted_at` provenance fields. Has `campos_adicionales` dict for overflow.
- `policy_extractor/schemas/asegurado.py` — AseguradoExtraction with `tipo: Literal["persona", "bien"]` discriminator
- `policy_extractor/schemas/cobertura.py` — CoberturaExtraction with Decimal monetary fields and overflow dict
- `policy_extractor/schemas/__init__.py` — Exports all three schema classes

### Phase 2 outputs (input contract)
- `policy_extractor/schemas/ingestion.py` — IngestionResult and PageResult models (the input to extraction)
- `policy_extractor/ingestion/__init__.py` — `ingest_pdf()` function that produces IngestionResult

### Project infrastructure
- `policy_extractor/config.py` — Settings class to extend with extraction config
- `policy_extractor/extraction/__init__.py` — Stub module where extraction code will live

### Project scope
- `.planning/REQUIREMENTS.md` — EXT-01 through EXT-05 are the requirements for this phase
- `.planning/ROADMAP.md` — Phase 3 success criteria (4 criteria that must be TRUE)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PolicyExtraction` Pydantic model — already has all fields, date normalization, Decimal types, provenance fields. This IS the extraction target.
- `IngestionResult` — structured input with per-page text, file_hash, page classifications. Phase 3 reads this directly.
- `Settings` class — extend with EXTRACTION_MODEL, EXTRACTION_MAX_RETRIES, EXTRACTION_PROMPT_VERSION
- `compute_file_hash()` from ingestion cache — source_file_hash on PolicyExtraction should match

### Established Patterns
- Pydantic v2 models for all data contracts
- python-dotenv + Settings class for configuration
- TDD with pytest, fixtures in tests/fixtures/
- Spanish domain terms in field names, English code

### Integration Points
- `policy_extractor/extraction/__init__.py` — stub exists, extraction module lives here
- Input: `IngestionResult` from `policy_extractor.ingestion.ingest_pdf()`
- Output: `PolicyExtraction` from `policy_extractor.schemas.poliza`
- Provenance: `source_file_hash` from ingestion, `model_id` and `prompt_version` from extraction, `extracted_at` = now
- `confianza` dict needs to be added to PolicyExtraction model (new field)

</code_context>

<specifics>
## Specific Ideas

- Start with Haiku for cost efficiency (200+ policies/month), but make model configurable so users can switch to Sonnet if extraction quality is insufficient
- The "Sonnet as evaluator recommending upgrade" concept is deferred to v2 quality features (QAL-03)
- Post-hoc hallucination verification: check if `numero_poliza` and `aseguradora` values actually appear somewhere in the source text — if not, flag with low confidence
- Raw Claude response storage enables future prompt iteration: compare v1.0.0 vs v1.1.0 extractions on the same PDF

</specifics>

<deferred>
## Deferred Ideas

- Sonnet as quality evaluator that recommends model upgrade when many extraction errors are detected — v2 quality feature (QAL-03 human-in-the-loop scope)
- Image-based extraction via Claude vision API — revisit if text-only extraction proves insufficient for complex layouts
- Per-insurer prompt tuning or examples — only if single-pass generic prompt proves inadequate across the 50-70 layouts
- Golden dataset regression suite for model drift detection — v2 (QAL-01)

</deferred>

---

*Phase: 03-extraction*
*Context gathered: 2026-03-18*
