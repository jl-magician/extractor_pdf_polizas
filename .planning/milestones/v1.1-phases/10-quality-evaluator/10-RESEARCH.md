# Phase 10: Quality Evaluator - Research

**Researched:** 2026-03-19
**Domain:** Anthropic tool_use structured evaluation, CLI/API opt-in integration, SQLite persistence
**Confidence:** HIGH

## Summary

Phase 10 grafts a Sonnet-powered quality scoring pass onto the existing Haiku extraction pipeline. The evaluator is strictly opt-in: it only runs when the user passes `--evaluate` on the CLI or `evaluate=true` on the upload API. All evaluation state lives in four columns on the `polizas` table that already exist in the schema (added by Phase 6 migration 002). No new tables, no new migrations are required.

The implementation follows patterns already established in the codebase: `build_evaluation_tool()` mirrors `build_extraction_tool()`; `call_evaluation_api()` mirrors `call_extraction_api()`; `update_evaluation()` in `writer.py` makes a targeted column update after `upsert_policy()` has already persisted the extraction. CLI integration is additive only — a single `--evaluate` typer.Option on both `extract` and `batch` commands. The upload API adds an `evaluate: bool = Query(False, ...)` parameter to the existing route and threads it into `_run_extraction`.

The only genuinely new surface is the evaluation module itself (`policy_extractor/evaluation.py`) and the targeted DB update function. Everything else is extension of existing code paths. The largest risk is prompt engineering for the evaluator: Sonnet must assess completeness, accuracy, and hallucination risk from text + JSON alone — the prompt wording critically determines score quality.

**Primary recommendation:** Create `policy_extractor/evaluation.py` as a self-contained module (not inline in cli.py) to keep the evaluation logic testable independently of the CLI.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Evaluation scoring design**
- 3 dimensions: completeness (did Haiku capture all visible fields?), accuracy (are values plausible/correct?), hallucination risk (did Haiku invent data not in the PDF?)
- Each dimension scored 0.0-1.0 float
- `evaluation_score` column stores the average of 3 dimensions
- `evaluation_json` stores structured breakdown: 3 dimension scores + list of flagged fields with issues (e.g., `{"completeness": 0.9, "accuracy": 0.85, "hallucination_risk": 0.1, "flags": [{"field": "prima_total", "issue": "suspicious value 0.00"}, ...]}`)
- `evaluated_at` stores when evaluation ran; `evaluated_model_id` stores which Sonnet model

**CLI & API integration**
- `--evaluate` flag on both `extract` and `batch` commands
- Evaluation is opt-in only — never in default path (QAL-04)
- Upload API accepts `evaluate=true` query parameter (QAL-05)
- Cost display: two separate lines — extraction cost and evaluation cost shown independently
- Batch summary: "Avg Score" and "Low Score Files" rows added when --evaluate is used. Individual per-file scores stored in DB only.
- Batch with --evaluate: every successfully extracted PDF gets evaluated (doubles API cost, user opted in)

**Evaluation prompt design**
- Sonnet receives: original PDF text + Haiku's structured extraction (JSON)
- Sonnet uses `tool_use` for structured output (same forced-tool pattern as extraction)
- Evaluation tool schema defines typed fields: completeness (float), accuracy (float), hallucination_risk (float), flags (array of {field, issue}), summary (string)
- Evaluation model: `claude-sonnet-4-5-20250514` hardcoded (not configurable in v1.1). Model ID stored in `evaluated_model_id` column.

**Re-evaluation workflow**
- Re-evaluation is allowed — overwrites previous evaluation_score, evaluation_json, evaluated_at, evaluated_model_id
- No evaluation history (simple overwrite, not append)
- `--evaluate` always runs Sonnet when passed — no idempotency check on evaluation. `--force` only affects extraction, not evaluation.

### Claude's Discretion
- Exact evaluation prompt wording and system prompt
- Evaluation tool schema field names (as long as they map to the 3 dimensions + flags)
- Whether to create `policy_extractor/evaluation.py` or keep inline
- How to thread evaluation into the upload API's `_run_extraction` background worker
- Low score threshold for "Low Score Files" in batch summary

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QAL-01 | User can run Sonnet evaluation on an extraction via `--evaluate` CLI flag | `--evaluate: bool = typer.Option(False, ...)` on `extract` and `batch` commands; call `evaluate_policy()` after successful `extract_policy()` |
| QAL-02 | Sonnet evaluator scores extraction completeness, accuracy, and hallucination risk | `build_evaluation_tool()` + forced `tool_use` call to `claude-sonnet-4-5-20250514`; tool schema enforces the 3 float dimensions + flags array |
| QAL-03 | Evaluation results are stored in dedicated database columns | `update_evaluation_columns()` in `writer.py` — targeted UPDATE to `evaluation_score`, `evaluation_json`, `evaluated_at`, `evaluated_model_id` on existing Poliza row |
| QAL-04 | Evaluation is opt-in only — never runs in the default extraction path | Evaluation code lives exclusively inside `if evaluate:` branches; never imported or called without the flag |
| QAL-05 | API upload endpoint accepts optional `evaluate=true` query parameter | Add `evaluate: bool = Query(False, ...)` to `upload_pdf()` route; pass `evaluate` into `_run_extraction()` |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.86.0 (already in pyproject.toml) | Sonnet API call for evaluation | Already used for extraction; same client instance pattern |
| typer | >=0.9.0 (already in pyproject.toml) | `--evaluate` flag on CLI commands | Already the CLI framework |
| rich | >=13.0.0 (already in pyproject.toml) | Separate cost lines in CLI output | Already used for all CLI output |
| sqlalchemy | >=2.0.48 (already in pyproject.toml) | Update evaluation columns in DB | Already used for all persistence |
| pydantic | >=2.12.5 (already in pyproject.toml) | Validate evaluation tool response | Already used for extraction schemas |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | N/A | Serialize evaluation_json for TEXT column | Already used in writer.py `_json_safe()` |
| datetime (stdlib) | N/A | Set `evaluated_at` timestamp | Already used throughout codebase |

**No new dependencies.** All libraries are already installed. No `pip install` step required.

---

## Architecture Patterns

### Recommended Project Structure Addition
```
policy_extractor/
├── evaluation.py          # NEW: evaluation module (QAL-02)
│   ├── EVAL_TOOL_NAME     # "evaluate_policy"
│   ├── EVAL_MODEL_ID      # "claude-sonnet-4-5-20250514"
│   ├── build_evaluation_tool()
│   ├── call_evaluation_api()
│   └── evaluate_policy()  # Public entry point → returns EvaluationResult
├── extraction/            # Unchanged
├── cli.py                 # Extended: --evaluate flag on extract + batch
├── storage/
│   └── writer.py          # Extended: update_evaluation_columns()
└── api/
    └── upload.py          # Extended: evaluate param in _run_extraction()
```

### Pattern 1: Forced tool_use for Evaluation (mirrors extraction pattern)

**What:** Sonnet is called with a structured evaluation tool and `tool_choice={"type": "tool", "name": "evaluate_policy"}` to guarantee a typed JSON response.
**When to use:** Whenever you need structured output from Claude — same pattern as extraction.

```python
# Source: policy_extractor/extraction/client.py call_extraction_api() — mirrors exactly
def call_evaluation_api(
    client: anthropic.Anthropic,
    assembled_text: str,
    extraction_json: str,
    model: str = EVAL_MODEL_ID,
    max_tokens: int = 1024,
) -> anthropic.types.Message:
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=EVAL_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"PDF TEXT:\n{assembled_text}\n\nEXTRACTED DATA:\n{extraction_json}"
        }],
        tools=[build_evaluation_tool()],
        tool_choice={"type": "tool", "name": EVAL_TOOL_NAME},
    )
```

### Pattern 2: Evaluation Tool Schema

**What:** Explicit JSON schema with float constraints for scores, array-of-objects for flags.
**When to use:** Building the `input_schema` for the evaluation tool.

```python
# Mirrors build_extraction_tool() in schema_builder.py
EVAL_TOOL_NAME = "evaluate_policy"

def build_evaluation_tool() -> dict:
    return {
        "name": EVAL_TOOL_NAME,
        "description": "Score the quality of an insurance policy extraction.",
        "input_schema": {
            "type": "object",
            "properties": {
                "completeness": {
                    "type": "number",
                    "description": "0.0-1.0: fraction of visible fields captured",
                },
                "accuracy": {
                    "type": "number",
                    "description": "0.0-1.0: plausibility/correctness of extracted values",
                },
                "hallucination_risk": {
                    "type": "number",
                    "description": "0.0-1.0: fraction of fields with invented data (0=none, 1=all invented)",
                },
                "flags": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "issue": {"type": "string"},
                        },
                        "required": ["field", "issue"],
                    },
                    "description": "List of specific field-level issues found",
                },
                "summary": {
                    "type": "string",
                    "description": "One-sentence overall assessment",
                },
            },
            "required": ["completeness", "accuracy", "hallucination_risk", "flags", "summary"],
        },
    }
```

### Pattern 3: evaluate_policy() Public Entry Point

**What:** Single callable that takes assembled_text + PolicyExtraction, returns a typed result dict. CLI and API both call this.
**When to use:** This is the only public symbol from evaluation.py that CLI and upload.py should import.

```python
# policy_extractor/evaluation.py
from dataclasses import dataclass

@dataclass
class EvaluationResult:
    score: float           # average of 3 dimensions
    evaluation_json: str   # JSON string for TEXT column
    evaluated_at: datetime
    model_id: str
    usage: anthropic.types.Usage

def evaluate_policy(
    assembled_text: str,
    policy: PolicyExtraction,
    model: str = EVAL_MODEL_ID,
) -> EvaluationResult | None:
    """Call Sonnet to score a completed extraction. Returns None on failure."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    extraction_json = policy.model_dump_json(indent=2)
    try:
        message = call_evaluation_api(client, assembled_text, extraction_json, model)
        return _parse_evaluation(message)
    except Exception as exc:
        logger.error(f"Evaluation failed: {exc}")
        return None
```

### Pattern 4: update_evaluation_columns() in writer.py

**What:** Targeted UPDATE that sets only the 4 evaluation columns — never touches extraction data.
**When to use:** After `upsert_policy()` succeeds and `evaluate_policy()` returns a result.

```python
# policy_extractor/storage/writer.py — new function
def update_evaluation_columns(
    session: Session,
    numero_poliza: str,
    aseguradora: str,
    score: float,
    evaluation_json: str,
    evaluated_at: datetime,
    model_id: str,
) -> None:
    """Overwrite evaluation columns on an existing Poliza row. Simple overwrite, no history."""
    poliza = (
        session.query(Poliza)
        .filter_by(numero_poliza=numero_poliza, aseguradora=aseguradora)
        .first()
    )
    if poliza is None:
        raise ValueError(f"Poliza not found: {numero_poliza} / {aseguradora}")
    poliza.evaluation_score = score
    poliza.evaluation_json = evaluation_json
    poliza.evaluated_at = evaluated_at
    poliza.evaluated_model_id = model_id
    session.commit()
```

### Pattern 5: CLI --evaluate integration on `extract` command

**What:** Add `evaluate: bool = typer.Option(False, "--evaluate", ...)`, call `evaluate_policy()` after extraction, display separate cost line.
**When to use:** Inside `extract` command, immediately after `upsert_policy()` succeeds.

```python
# policy_extractor/cli.py — additions to extract() command
evaluate: bool = typer.Option(False, "--evaluate", help="Run Sonnet quality evaluation after extraction"),

# After upsert_policy() succeeds:
if evaluate:
    from policy_extractor.evaluation import evaluate_policy
    from policy_extractor.storage.writer import update_evaluation_columns
    eval_result = evaluate_policy(assembled_text, policy)
    if eval_result is not None:
        update_evaluation_columns(
            session,
            policy.numero_poliza,
            policy.aseguradora,
            eval_result.score,
            eval_result.evaluation_json,
            eval_result.evaluated_at,
            eval_result.model_id,
        )
        if not quiet:
            console.print(f"[bold]Quality score:[/bold] {eval_result.score:.2f}")
            _print_cost(eval_result.model_id, eval_result.usage.input_tokens, eval_result.usage.output_tokens)
    else:
        console.print("[yellow]WARN[/yellow] Evaluation failed")
```

**Important:** `assembled_text` must be captured from `assemble_text(ingestion_result)` in the `extract` command. Currently cli.py calls `extract_policy()` which calls `assemble_text()` internally — the CLI needs to call `assemble_text()` itself before `extract_policy()`, OR evaluation.py re-assembles from the ingestion_result passed in. The simplest approach: have `evaluate_policy()` accept the `IngestionResult` directly and call `assemble_text()` internally.

### Pattern 6: Batch summary rows for evaluation

**What:** Two new rows added to the batch summary Rich table when `--evaluate` is used.
**When to use:** In the summary table section of the `batch` command.

```python
# Low score threshold — Claude's discretion, recommend 0.7
LOW_SCORE_THRESHOLD = 0.7

if evaluate:
    avg_score = total_eval_score / max(eval_count, 1)
    summary_table.add_row("Avg Score", f"{avg_score:.2f}")
    summary_table.add_row("Low Score Files", str(low_score_count))
    summary_table.add_row("Eval Cost (USD)", f"${total_eval_cost:.4f}")
```

### Pattern 7: Upload API evaluate parameter threading

**What:** `evaluate: bool = Query(False, ...)` on the route, passed into `_run_extraction()`.
**When to use:** The upload route spawns a thread; `evaluate` must be passed through.

```python
# policy_extractor/api/upload.py — modifications

# Route signature change:
async def upload_pdf(
    file: UploadFile = File(...),
    model: str | None = Query(None, ...),
    force: bool = Query(False, ...),
    evaluate: bool = Query(False, description="Run Sonnet quality evaluation after extraction"),
) -> JSONResponse:
    # ... existing validation ...
    t = threading.Thread(
        target=_run_extraction,
        args=(job["job_id"], save_path, model, force, evaluate),  # evaluate added
        daemon=True,
    )

# _run_extraction signature:
def _run_extraction(job_id: str, pdf_path: Path, model: str | None, force: bool, evaluate: bool = False) -> None:
    # ... after upsert_policy() succeeds ...
    if evaluate:
        from policy_extractor.evaluation import evaluate_policy
        from policy_extractor.storage.writer import update_evaluation_columns
        eval_result = evaluate_policy(ingestion_result, policy)
        if eval_result is not None:
            update_evaluation_columns(session, ...)
            # Merge eval fields into result dict
            result["evaluation_score"] = eval_result.score
            result["evaluation_json"] = eval_result.evaluation_json
```

### Anti-Patterns to Avoid

- **Calling evaluate_policy() before upsert_policy():** Always persist extraction first. If evaluation fails, the extraction is still saved. If evaluation runs before persist and extraction-persist fails, evaluation effort was wasted.
- **Putting evaluation logic directly in cli.py inline:** Creates untestable spaghetti. The evaluation module should be importable and testable without the CLI.
- **Re-using the extraction client.py call for evaluation:** The extraction client has `SYSTEM_PROMPT_V1` and `build_extraction_tool()` hardwired. Evaluation needs a different system prompt and a different tool — create parallel functions in evaluation.py.
- **Checking if evaluation already ran before evaluating:** Context.md decision: `--evaluate` always runs Sonnet when passed, no idempotency check. Don't add an "already evaluated" guard.
- **Storing `assembled_text` on the session/DB between phases:** Re-assemble from `ingestion_result` at evaluation time. The ingestion pipeline always returns the text needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON from Sonnet | Custom parsing of free-text response | `tool_use` + `tool_choice={"type": "tool", "name": "evaluate_policy"}` | Guaranteed schema adherence; avoids regex parsing of LLM output |
| Score float bounds validation | Manual clamp in Python | Pydantic field validator on the parsed response dict | Consistent with how extraction validates `confianza` values |
| Cost calculation for Sonnet | Separate PRICING dict | `estimate_cost()` already in `cli_helpers.py` — `"sonnet" in model_id` branch | Already handles Sonnet pricing ($3/$15 per 1M tokens) |
| DB column update | Raw SQL UPDATE | `update_evaluation_columns()` via SQLAlchemy ORM session | Consistent with existing writer.py patterns; benefits from session lifecycle management |

**Key insight:** The extraction pipeline already solved all the hard problems (tool_use, retry, cost, persistence) — evaluation is a lighter version of the same pattern.

---

## Common Pitfalls

### Pitfall 1: assembled_text Not Available in CLI
**What goes wrong:** `extract_policy()` calls `assemble_text()` internally — the CLI currently only gets back `(policy, usage, retries)`. The evaluator needs the assembled text as input to Sonnet.
**Why it happens:** `assemble_text()` is called inside `extract_policy()`, not returned to callers.
**How to avoid:** In `evaluate_policy()`, accept `IngestionResult` as an argument and call `assemble_text()` internally (same import as extraction/__init__.py already does). The CLI passes `ingestion_result` which it already has from the `ingest_pdf()` call at line 102 of cli.py.
**Warning signs:** If evaluate_policy() signature takes only `policy: PolicyExtraction`, you'll have no PDF text to send to Sonnet — evaluation will be low quality.

### Pitfall 2: SKIP Path in extract Does Not Evaluate
**What goes wrong:** When `not force and is_already_extracted(...)` is True, the command exits early at `raise typer.Exit(0)` — before any evaluation can run.
**Why it happens:** The skip path is designed to avoid redundant work. But the user may want to re-evaluate an already-extracted policy.
**How to avoid:** Document this behavior clearly. If `--evaluate` is passed but the file was already extracted and skipped, print a note: "Already extracted — skipped extraction. Use --force to re-extract and evaluate." The skip + evaluate interaction is a known limitation; no special handling needed per CONTEXT.md decisions.

### Pitfall 3: evaluation_json Column is TEXT, Not JSON
**What goes wrong:** `Poliza.evaluation_json` is `sa.Text()`, not `JSON`. If you store a Python dict directly, SQLAlchemy will stringify it with Python repr notation (single quotes, None instead of null) — invalid JSON.
**Why it happens:** The column was typed as TEXT for forward compatibility. JSON type in SQLite has no type enforcement.
**How to avoid:** Always serialize the evaluation result dict with `json.dumps()` before storing: `evaluation_json = json.dumps(eval_dict, ensure_ascii=False)`. Use `_json_safe()` from writer.py if the dict may contain datetime or Decimal.

### Pitfall 4: Thread Safety in batch --evaluate
**What goes wrong:** The batch command uses `ThreadPoolExecutor`. Each `_process_single_pdf()` call may now also run evaluation. The aggregation counters (`total_eval_score`, `low_score_count`) need the same `threading.Lock()` protection as `total_input`/`total_output` already use.
**Why it happens:** Concurrent write to shared counters without a lock produces race conditions.
**How to avoid:** Add `eval_score` and `low_score_flag` to the result dict returned by `_process_single_pdf()`. Accumulate them under the existing `lock` in the `as_completed` loop — same pattern as token counters.

### Pitfall 5: API Result Missing Evaluation Fields When evaluate=False
**What goes wrong:** The job result dict always needs a consistent shape. If evaluation fields are sometimes present and sometimes absent, callers must do defensive checks.
**Why it happens:** The result dict is built conditionally.
**How to avoid:** Include evaluation fields in the result dict always, defaulting to `None`. After `_run_extraction` completes without evaluation: `result["evaluation_score"] = None`, etc.

### Pitfall 6: `_process_single_pdf` Signature Change Breaks Thread Dispatch
**What goes wrong:** Adding `evaluate` to `_process_single_pdf()` requires updating both the sequential and concurrent call sites.
**Why it happens:** The function is called in two places in `batch` — the `concurrency == 1` loop and the `executor.submit(...)` call.
**How to avoid:** Add `evaluate: bool = False` as a keyword-only argument (after `*`) to `_process_single_pdf`. Update both call sites: `_process_single_pdf(pdf, model=model, force=force, output_dir=output_dir, evaluate=evaluate)`.

---

## Code Examples

Verified patterns from existing codebase:

### Existing: call_extraction_api with forced tool_use
```python
# Source: policy_extractor/extraction/client.py lines 19-43
return client.messages.create(
    model=model,
    max_tokens=max_tokens,
    system=SYSTEM_PROMPT_V1,
    messages=[{"role": "user", "content": assembled_text}],
    tools=[build_extraction_tool()],
    tool_choice={"type": "tool", "name": TOOL_NAME},
)
```

### Existing: Parsing tool_use response
```python
# Source: policy_extractor/extraction/client.py lines 66-72
if not message.content or message.content[0].type != "tool_use":
    raise ValueError(f"Expected tool_use response, got: ...")
raw_input: dict = dict(message.content[0].input)
```

### Existing: estimate_cost supports Sonnet
```python
# Source: policy_extractor/cli_helpers.py lines 23-28
pricing_key = "sonnet" if "sonnet" in model_id.lower() else "haiku"
rates = PRICING[pricing_key]
# PRICING["sonnet"] = {"input": 3.00, "output": 15.00}
```

### Existing: _print_cost pattern for separate cost lines
```python
# Source: policy_extractor/cli.py lines 61-67
def _print_cost(model_id: str, input_tokens: int, output_tokens: int) -> None:
    cost = estimate_cost(model_id, input_tokens, output_tokens)
    console.print(
        f"Tokens: {input_tokens:,} input, {output_tokens:,} output | "
        f"Est. cost: ${cost:.4f} USD"
    )
# Call once for extraction model, once for evaluation model — two separate lines
```

### Existing: Lazy imports inside CLI command functions
```python
# Source: policy_extractor/cli.py lines 116-118
try:
    from policy_extractor.storage.writer import upsert_policy
    upsert_policy(session, policy)
# Evaluation module import should follow same pattern:
if evaluate:
    from policy_extractor.evaluation import evaluate_policy
```

### Existing: evaluation_score column (already in schema)
```python
# Source: policy_extractor/storage/models.py lines 50-53
evaluation_score: Mapped[Optional[float]] = mapped_column(nullable=True)
evaluation_json: Mapped[Optional[str]] = mapped_column(sa.Text(), nullable=True)
evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
evaluated_model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

### Existing: _run_extraction pattern to extend
```python
# Source: policy_extractor/api/upload.py lines 107-149
# Currently: _run_extraction(job_id, pdf_path, model, force)
# Extended: _run_extraction(job_id, pdf_path, model, force, evaluate=False)
# After upsert_policy() and before result/cleanup, add evaluate branch
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-text quality assessment | Forced tool_use structured output | Anthropic tool_use launched 2023 | Guaranteed schema; no parsing needed |
| Single model for everything | Haiku extract + Sonnet evaluate | v1.1 design decision | ~20x cost difference; opt-in controls spend |

**Deprecated/outdated:**
- Parsing free-text Claude responses for structured data: replaced by `tool_use` with `tool_choice` forced schema.

---

## Evaluation Module Design

### evaluate_policy() Inputs and Outputs

**Inputs:**
- `ingestion_result: IngestionResult` — source of `assembled_text` via `assemble_text()`
- `policy: PolicyExtraction` — the Haiku extraction to evaluate
- `model: str = EVAL_MODEL_ID` — hardcoded Sonnet model

**Outputs (EvaluationResult dataclass):**
- `score: float` — average of completeness + accuracy + (1 - hallucination_risk)
  - Note: hallucination_risk is inverted when averaging. A score of 1.0 = hallucination_risk of 0.0. This interpretation should be validated.
  - Alternative simpler interpretation: average of all 3 raw values — decide during implementation.
- `evaluation_json: str` — JSON string storing raw `{"completeness": ..., "accuracy": ..., "hallucination_risk": ..., "flags": [...], "summary": "..."}`
- `evaluated_at: datetime` — UTC timestamp of when evaluation ran
- `model_id: str` — `EVAL_MODEL_ID` constant
- `usage: anthropic.types.Usage` — for cost reporting

### Evaluation Prompt Strategy (Claude's Discretion)

The system prompt for evaluation should instruct Sonnet to:
1. Compare extracted field values against the PDF text character by character for key fields (numero_poliza, prima_total, fechas)
2. Check for fields visible in the PDF that Haiku left as null
3. Flag any value that does not appear verbatim or calculably in the source text

**Recommended structure for user message:**
```
PDF TEXT (source of truth):
---
{assembled_text}
---

EXTRACTED DATA (to evaluate):
---
{policy.model_dump_json(indent=2)}
---

Evaluate the quality of this extraction using the evaluate_policy tool.
```

### Low Score Threshold (Claude's Discretion)

Recommend `0.7` as the "Low Score Files" threshold. This flags extractions where the average of the 3 dimensions falls below 70%, which indicates material quality concerns. The threshold should be a named constant in evaluation.py (`LOW_SCORE_THRESHOLD = 0.7`) to make it easy to tune.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already installed, `pyproject.toml [tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` — `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_evaluation.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QAL-01 | `extract --evaluate` triggers Sonnet call after extraction | unit | `pytest tests/test_evaluation.py::test_evaluate_called_with_flag -x` | Wave 0 |
| QAL-01 | `extract` without `--evaluate` makes no Sonnet call | unit | `pytest tests/test_evaluation.py::test_evaluate_not_called_without_flag -x` | Wave 0 |
| QAL-01 | `batch --evaluate` evaluates each successfully extracted PDF | unit | `pytest tests/test_evaluation.py::test_batch_evaluate_flag -x` | Wave 0 |
| QAL-02 | evaluate_policy() returns EvaluationResult with 3 float scores | unit | `pytest tests/test_evaluation.py::test_evaluate_policy_returns_scores -x` | Wave 0 |
| QAL-02 | Sonnet tool_use call uses correct forced tool_choice | unit | `pytest tests/test_evaluation.py::test_evaluation_tool_schema -x` | Wave 0 |
| QAL-03 | Evaluation columns updated in DB after evaluate_policy() | unit | `pytest tests/test_evaluation.py::test_update_evaluation_columns -x` | Wave 0 |
| QAL-03 | evaluation_json stored as valid JSON string | unit | `pytest tests/test_evaluation.py::test_evaluation_json_is_valid_json -x` | Wave 0 |
| QAL-04 | No Sonnet call when --evaluate not passed | unit | `pytest tests/test_evaluation.py::test_evaluate_not_called_without_flag -x` | Wave 0 |
| QAL-05 | POST /polizas/upload?evaluate=true triggers evaluation | unit | `pytest tests/test_upload.py::test_upload_evaluate_param -x` | Wave 0 |
| QAL-05 | POST /polizas/upload (no param) does not trigger evaluation | unit | `pytest tests/test_upload.py::test_upload_no_evaluate_by_default -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_evaluation.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green (`pytest tests/ -x`) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_evaluation.py` — covers all QAL-01 through QAL-05 unit tests
- [ ] No new conftest.py needed — existing `tests/conftest.py` and MockMessage pattern from `test_extraction.py` are sufficient

*(test_upload.py already exists — new tests for evaluate param are additions to that file)*

---

## Open Questions

1. **Score average formula: raw average vs. inverted hallucination_risk**
   - What we know: CONTEXT.md says `evaluation_score = average of 3 dimensions`. The 3 dimensions are completeness, accuracy, hallucination_risk.
   - What's unclear: hallucination_risk is a risk score (higher = worse). Averaging it raw means high hallucination_risk pulls the average UP, which would be counterintuitive for a quality score.
   - Recommendation: Invert hallucination_risk: `score = (completeness + accuracy + (1 - hallucination_risk)) / 3`. This makes 1.0 mean "perfect quality". Document this inversion in the code comment.

2. **assembled_text access in batch `_process_single_pdf`**
   - What we know: `_process_single_pdf()` currently calls `extract_policy(ingestion_result)` and discards the ingestion_result after. The evaluation needs assembled_text or ingestion_result.
   - What's unclear: Should `_process_single_pdf()` pass `ingestion_result` to `evaluate_policy()`, or re-assemble text from the already-available `ingestion_result`?
   - Recommendation: Pass `ingestion_result` directly to `evaluate_policy()`. It's already in scope at that point and `assemble_text()` is cheap.

3. **Batch result dict with evaluate fields**
   - What we know: `_process_single_pdf()` returns a dict with `status, name, input_tokens, output_tokens, retries, error`. Batch aggregation uses these keys.
   - What's unclear: How to propagate per-file eval scores back for "Avg Score" and "Low Score Files" without breaking the existing skipped/failed paths.
   - Recommendation: Add `eval_score: float | None = None` to the returned dict. Skipped and failed files get `None`. The aggregation in the `as_completed` loop counts `sum(r["eval_score"] for r in results if r["eval_score"] is not None)` for the average.

---

## Sources

### Primary (HIGH confidence)
- Direct reading of `policy_extractor/extraction/client.py` — call_extraction_api pattern, parse_and_validate pattern
- Direct reading of `policy_extractor/extraction/schema_builder.py` — build_extraction_tool pattern
- Direct reading of `policy_extractor/extraction/prompt.py` — assemble_text, SYSTEM_PROMPT_V1
- Direct reading of `policy_extractor/cli.py` — extract command lines 73-134, batch command lines 140-277, _process_single_pdf lines 142-201
- Direct reading of `policy_extractor/cli_helpers.py` — estimate_cost with Sonnet pricing already present
- Direct reading of `policy_extractor/storage/writer.py` — upsert_policy pattern for targeted column update
- Direct reading of `policy_extractor/storage/models.py` lines 50-53 — evaluation columns confirmed present
- Direct reading of `policy_extractor/api/upload.py` — _run_extraction pattern lines 107-149
- Direct reading of `.planning/phases/10-quality-evaluator/10-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)
- `policy_extractor/extraction/__init__.py` — confirmed extract_policy returns (PolicyExtraction|None, Usage|None, int) 3-tuple

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all libraries already in pyproject.toml
- Architecture: HIGH — evaluation.py module mirrors extraction patterns verified in source
- Pitfalls: HIGH — identified from direct code inspection of call sites and data types
- Evaluation prompt design: MEDIUM — prompt wording is Claude's discretion; quality depends on empirical testing

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable — no external APIs changing; all patterns internal)
