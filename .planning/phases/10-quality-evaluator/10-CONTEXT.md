# Phase 10: Quality Evaluator - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Opt-in Sonnet-powered quality scoring pass on Haiku extractions. Assesses completeness, accuracy, and hallucination risk. Integrates into CLI extract/batch commands via `--evaluate` flag and upload API via `evaluate=true` query parameter. No changes to the extraction pipeline itself.

</domain>

<decisions>
## Implementation Decisions

### Evaluation scoring design
- 3 dimensions: completeness (did Haiku capture all visible fields?), accuracy (are values plausible/correct?), hallucination risk (did Haiku invent data not in the PDF?)
- Each dimension scored 0.0-1.0 float
- `evaluation_score` column stores the average of 3 dimensions
- `evaluation_json` stores structured breakdown: 3 dimension scores + list of flagged fields with issues (e.g., `{"completeness": 0.9, "accuracy": 0.85, "hallucination_risk": 0.1, "flags": [{"field": "prima_total", "issue": "suspicious value 0.00"}, ...]}`)
- `evaluated_at` stores when evaluation ran; `evaluated_model_id` stores which Sonnet model

### CLI & API integration
- `--evaluate` flag on both `extract` and `batch` commands
- Evaluation is opt-in only — never in default path (QAL-04)
- Upload API accepts `evaluate=true` query parameter (QAL-05)
- Cost display: two separate lines — extraction cost and evaluation cost shown independently
- Batch summary: "Avg Score" and "Low Score Files" rows added when --evaluate is used. Individual per-file scores stored in DB only.
- Batch with --evaluate: every successfully extracted PDF gets evaluated (doubles API cost, user opted in)

### Evaluation prompt design
- Sonnet receives: original PDF text + Haiku's structured extraction (JSON)
- Sonnet uses `tool_use` for structured output (same forced-tool pattern as extraction)
- Evaluation tool schema defines typed fields: completeness (float), accuracy (float), hallucination_risk (float), flags (array of {field, issue}), summary (string)
- Evaluation model: `claude-sonnet-4-5-20250514` hardcoded (not configurable in v1.1). Model ID stored in `evaluated_model_id` column.

### Re-evaluation workflow
- Re-evaluation is allowed — overwrites previous evaluation_score, evaluation_json, evaluated_at, evaluated_model_id
- No evaluation history (simple overwrite, not append)
- `--evaluate` always runs Sonnet when passed — no idempotency check on evaluation. `--force` only affects extraction, not evaluation.

### Claude's Discretion
- Exact evaluation prompt wording and system prompt
- Evaluation tool schema field names (as long as they map to the 3 dimensions + flags)
- Whether to create `policy_extractor/evaluation.py` or keep inline
- How to thread evaluation into the upload API's `_run_extraction` background worker
- Low score threshold for "Low Score Files" in batch summary

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing evaluation columns
- `policy_extractor/storage/models.py` lines 50-53 — evaluation_score (REAL), evaluation_json (TEXT), evaluated_at (DATETIME), evaluated_model_id (TEXT) — all nullable, already in schema

### Extraction pipeline (evaluation hooks into this)
- `policy_extractor/extraction/__init__.py` — `extract_policy()` returns 3-tuple; evaluation runs after extraction succeeds
- `policy_extractor/extraction/client.py` — `call_extraction_api()` and `extract_with_retry()` — evaluation uses same Anthropic client pattern but different model
- `policy_extractor/extraction/schema_builder.py` — `build_extraction_tool()` pattern to replicate for evaluation tool
- `policy_extractor/extraction/prompt.py` — `SYSTEM_PROMPT_V1`, `assemble_text()` — evaluation needs the assembled text

### CLI commands to extend
- `policy_extractor/cli.py` lines 73-132 — `extract` command (add --evaluate flag)
- `policy_extractor/cli.py` lines 140-277 — `batch` command (add --evaluate flag + summary rows)
- `policy_extractor/cli_helpers.py` — `estimate_cost()` for cost calculation (evaluation needs separate cost line)

### Upload API to extend
- `policy_extractor/api/upload.py` — `_run_extraction()` background worker (add evaluate parameter + Sonnet call after extraction)

### DB persistence
- `policy_extractor/storage/writer.py` — `upsert_policy()` — need to update evaluation columns after evaluation completes

### Requirements
- `.planning/REQUIREMENTS.md` §Quality Evaluation — QAL-01 through QAL-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `call_extraction_api()` in `client.py`: Anthropic API call pattern — evaluation uses same client, different model, different tool
- `build_extraction_tool()` in `schema_builder.py`: Tool schema builder pattern — create `build_evaluation_tool()` following same pattern
- `assemble_text()` in `prompt.py`: Assembles PDF text — needed as input to evaluation prompt
- `estimate_cost()` in `cli_helpers.py`: Cost calculation — reuse for evaluation model pricing
- `_run_extraction()` in `upload.py`: Background worker — add evaluate branch after extraction
- `orm_to_schema()` in `writer.py`: Converts ORM → Pydantic — evaluation result needs to go back to ORM

### Established Patterns
- Forced `tool_use` with `tool_choice={"type": "tool", "name": TOOL_NAME}` for structured output
- Lazy imports inside CLI command functions
- `_setup_db()` called before any DB operations
- Rich console for CLI output, separate cost lines

### Integration Points
- `extract` command — add `--evaluate` typer.Option, call evaluation after extraction, display separate cost
- `batch` command — add `--evaluate` typer.Option, evaluate in `_process_single_pdf`, add summary rows
- `upload.py` `_run_extraction` — accept `evaluate` param, call evaluation after persist
- `writer.py` — add function to update evaluation columns on existing poliza

</code_context>

<specifics>
## Specific Ideas

- The agency wants to identify low-quality extractions before relying on the data — evaluation flags help prioritize manual review
- Separating extraction cost from evaluation cost helps the agency decide if evaluation is worth running on all polizas or only sampled ones

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-quality-evaluator*
*Context gathered: 2026-03-19*
