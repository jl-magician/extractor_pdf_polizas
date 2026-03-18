# Phase 03: Extraction - Research

**Researched:** 2026-03-18
**Domain:** Anthropic Python SDK tool_use, structured JSON extraction, Pydantic schema coercion
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Single-pass extraction: one Claude API call per PDF, Claude extracts all fields AND classifies insurer/type
- Detailed system prompt (~500 tokens) with every field, Spanish insurance terminology, "return null, never invent"
- Versioned prompt template stored as constant (e.g., `PROMPT_V1 = "v1.0.0"`); each extraction records `prompt_version`
- Text delivery: concatenate page texts with `--- Page N ---` separators into a single user message
- Claude self-reports confidence per field in the same response — three levels: `high`, `medium`, `low`
- Confidence stored as parallel `confianza` dict on PolicyExtraction (separate from main fields)
- Retry once on Pydantic validation failure with a refined prompt that mentions the specific validation error
- After retry failure: log, return null/partial result so batch continues
- Store raw Claude API response alongside extracted data (DATA-05)
- Hallucination prevention: prompt instruction PLUS post-hoc check that `numero_poliza` / `aseguradora` appear in source text
- Anthropic Python SDK with `tool_use` — define PolicyExtraction as tool schema, Claude returns structured JSON
- Default model: `claude-haiku-4-5-20251001` (cheapest, ~$1/M input tokens)
- Configurable to Sonnet via Settings class
- Add `EXTRACTION_MODEL`, `EXTRACTION_MAX_RETRIES`, `EXTRACTION_PROMPT_VERSION` to `policy_extractor/config.py`

### Claude's Discretion
- Exact tool_use schema construction from Pydantic model
- System prompt wording and field descriptions
- Post-hoc hallucination verification algorithm details
- Raw response storage format (JSON field vs separate file)
- How to structure the retry prompt with validation error context

### Deferred Ideas (OUT OF SCOPE)
- Sonnet as quality evaluator recommending model upgrade (v2, QAL-03)
- Image-based extraction via Claude vision API
- Per-insurer prompt tuning or examples
- Golden dataset regression suite for model drift (v2, QAL-01)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXT-01 | Extract all available fields from a policy PDF using Claude API (contratante, asegurado(s), costo, coberturas, sumas aseguradas, compañía, vigencia, agente, forma de pago, deducibles, additional fields) | tool_use with PolicyExtraction schema forces Claude to return every field or null |
| EXT-02 | Extraction output is structured JSON validated against Pydantic schemas | `tool_choice: {type: tool, name: extract_policy}` forces tool call; parse `content[0].input` into `PolicyExtraction(**data)` |
| EXT-03 | Automatically classify insurer and insurance type from PDF content | `aseguradora` + `tipo_seguro` are required/optional fields in the tool schema — Claude classifies in-context |
| EXT-04 | Each extracted field includes a confidence score indicating extraction certainty | `confianza` dict field added to PolicyExtraction; Claude self-reports in same tool call |
| EXT-05 | System handles PDFs in both Spanish and English | System prompt explicitly instructs bilingual handling; Claude API natively understands both |
</phase_requirements>

---

## Summary

Phase 3 implements the core extraction loop: receive an `IngestionResult` from Phase 2, build a prompt with all page text, call the Anthropic API using `tool_use` to force structured JSON, validate the result against `PolicyExtraction`, and return the populated model. The entire phase is pure Python with no storage — data flows in as `IngestionResult`, out as `PolicyExtraction`.

The API integration uses the `tool_choice: {type: "tool", name: "..."}` pattern to guarantee Claude calls the extraction tool rather than responding conversationally. The Pydantic schema is converted to a JSON schema via `model_json_schema()` and passed as `input_schema` — but the raw schema has a known issue: `Decimal` fields emit a complex `anyOf [number | pattern-string | null]` definition that may confuse the model. The fix is to provide a simplified manual schema for monetary fields.

The `confianza` confidence dict is a new field that must be added to `PolicyExtraction` before implementation begins. This is the only schema change required for Phase 3.

**Primary recommendation:** Use `tool_choice` forced tool call with a manually simplified input schema (not raw `model_json_schema()` output) to avoid Decimal pattern noise; add `confianza: dict` to `PolicyExtraction`; store raw API response in a separate field.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.86.0 (installed) | Anthropic API client | Official SDK; already installed |
| pydantic | >=2.12.5 (project) | Schema validation, JSON schema generation | Already established in project |
| loguru | >=0.7 (project) | Structured logging of errors and retries | Already established in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | — | Parse tool_use response `input` dict | Always — it's a dict, not a string |
| datetime (stdlib) | — | Set `extracted_at` UTC timestamp | Always on successful extraction |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tool_use + tool_choice | `output_config.format` JSON schema (new beta) | Beta feature (header `structured-outputs-2025-11-13`); Haiku 4.5 support confirmed; tool_use is GA and fully tested — use tool_use for stability |
| tool_use + tool_choice | instructor library | Extra dependency; tool_use is sufficient and avoids abstraction layer |
| manual schema simplification | raw `model_json_schema()` | Raw schema has Decimal `anyOf` noise; manual simplification is 10 lines |

**Installation:**
```bash
pip install anthropic>=0.86.0
```
(Already installed. Add to `pyproject.toml` dependencies.)

**Version verification:** `anthropic 0.86.0` confirmed installed and is latest as of 2026-03-18.

---

## Architecture Patterns

### Recommended Project Structure
```
policy_extractor/
├── extraction/
│   ├── __init__.py          # Public API: extract_policy(ingestion_result) -> PolicyExtraction
│   ├── client.py            # Anthropic client singleton, API call logic
│   ├── prompt.py            # PROMPT_V1 constant, system prompt, text assembly
│   └── verification.py      # Post-hoc hallucination check
policy_extractor/
├── schemas/
│   └── poliza.py            # Add confianza: dict field here (new in Phase 3)
policy_extractor/
└── config.py                # Add EXTRACTION_MODEL, EXTRACTION_MAX_RETRIES, EXTRACTION_PROMPT_VERSION
tests/
└── test_extraction.py       # Unit tests for extraction layer
```

### Pattern 1: Forced Tool Call for Structured Extraction

**What:** Define `PolicyExtraction` fields as a tool's `input_schema`. Set `tool_choice={"type": "tool", "name": "extract_policy"}` to force Claude to call that tool. Parse the response from `message.content[0].input` (a dict, not a string).

**When to use:** Any time a guaranteed structured output is required. This is the only approach that eliminates ambiguous prose responses.

**Example:**
```python
# Source: https://murraycole.com/posts/claude-tool-use-pydantic
# Source: https://platform.claude.com/docs/en/build-with-claude/tool-use/overview

import anthropic
from policy_extractor.schemas.poliza import PolicyExtraction

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# DO NOT use PolicyExtraction.model_json_schema() raw — Decimal fields
# produce complex anyOf patterns. Use a simplified manual schema instead.
extraction_tool = {
    "name": "extract_policy",
    "description": "Extract all available fields from an insurance policy PDF",
    "input_schema": _build_extraction_schema(),   # see Pattern 2 below
}

message = client.messages.create(
    model=settings.EXTRACTION_MODEL,
    max_tokens=4096,
    system=SYSTEM_PROMPT_V1,
    messages=[{"role": "user", "content": assembled_text}],
    tools=[extraction_tool],
    tool_choice={"type": "tool", "name": "extract_policy"},
)

# Response is always a dict (tool_use block)
raw_input: dict = message.content[0].input
policy = PolicyExtraction(**raw_input)
```

### Pattern 2: Simplified Manual Schema for Monetary Decimal Fields

**What:** `Pydantic` serializes `Optional[Decimal]` as `anyOf [number | pattern-string | null]`. The regex pattern string (`^(?!^[-+.]*$)[+-]?0*\\d*\\.?\\d*$`) is noise in the tool schema and can cause Claude Haiku to emit unexpected string values. Simplify monetary fields to `anyOf [number | null]` in the tool schema.

**When to use:** Whenever passing a Pydantic schema with `Decimal` fields to Claude.

**Example:**
```python
def _build_extraction_schema() -> dict:
    """Build tool input_schema, simplifying Decimal fields to number|null."""
    schema = PolicyExtraction.model_json_schema()

    # Fix Decimal anyOf patterns — keep only number|null
    decimal_fields = ["prima_total"]
    for field in decimal_fields:
        schema["properties"][field] = {
            "anyOf": [{"type": "number"}, {"type": "null"}],
            "default": None,
            "title": schema["properties"][field].get("title", field),
        }

    # Fix nested Decimal fields in CoberturaExtraction
    cobertura_def = schema["$defs"]["CoberturaExtraction"]["properties"]
    for field in ["suma_asegurada", "deducible"]:
        cobertura_def[field] = {
            "anyOf": [{"type": "number"}, {"type": "null"}],
            "default": None,
            "title": cobertura_def[field].get("title", field),
        }

    # Add confianza dict to schema
    schema["properties"]["confianza"] = {
        "type": "object",
        "description": "Confidence level per field: 'high' | 'medium' | 'low'",
        "additionalProperties": {"type": "string"},
        "default": {},
    }

    return schema
```

### Pattern 3: Retry with Validation Error Context

**What:** On `ValidationError`, rebuild the user message to include the specific validation error, then retry once.

**Example:**
```python
from pydantic import ValidationError

def _call_with_retry(client, tool, system_prompt, user_text, model, max_tokens):
    message = _call_api(client, tool, system_prompt, user_text, model, max_tokens)
    raw = message.content[0].input
    try:
        return PolicyExtraction(**raw), message
    except ValidationError as exc:
        # Retry once with error context
        retry_text = (
            f"{user_text}\n\n"
            f"IMPORTANT: Your previous response failed validation:\n{exc}\n"
            f"Please correct the fields and respond again."
        )
        message2 = _call_api(client, tool, system_prompt, retry_text, model, max_tokens)
        raw2 = message2.content[0].input
        return PolicyExtraction(**raw2), message2
```

### Pattern 4: Post-hoc Hallucination Verification

**What:** After successful extraction, check that key identity fields (`numero_poliza`, `aseguradora`) appear verbatim (or as substrings) somewhere in the source text. If not found, downgrade confidence to `low`.

**Example:**
```python
def verify_no_hallucination(policy: PolicyExtraction, source_text: str) -> PolicyExtraction:
    """Flag fields that don't appear in source text as potentially hallucinated."""
    confianza = dict(policy.confianza)
    for field, value in [
        ("numero_poliza", policy.numero_poliza),
        ("aseguradora", policy.aseguradora),
    ]:
        if value and value.lower() not in source_text.lower():
            confianza[field] = "low"  # Possible hallucination — override Claude's confidence
    return policy.model_copy(update={"confianza": confianza})
```

### Pattern 5: Text Assembly from IngestionResult

**What:** Concatenate `PageResult.text` strings with separator lines.

**Example:**
```python
def assemble_text(ingestion: IngestionResult) -> str:
    parts = []
    for page in ingestion.pages:
        parts.append(f"--- Page {page.page_num} ---")
        parts.append(page.text)
    return "\n\n".join(parts)
```

### Anti-Patterns to Avoid
- **Using `model_json_schema()` directly as `input_schema`:** The Decimal regex pattern in the raw schema may confuse Haiku — always pass a simplified schema.
- **Parsing `message.content[0].text`:** When `tool_choice` forces a tool call, the response block is `ToolUseBlock`, not `TextBlock`. Access `.input` not `.text`.
- **`temperature > 0` for extraction:** Deterministic field extraction benefits from `temperature=0` (or omitting the parameter to use the default). Avoid adding creativity to structured extraction.
- **Putting provenance fields in the tool schema:** `source_file_hash`, `model_id`, `prompt_version`, `extracted_at` are set by extraction code, not by Claude. Exclude them from `input_schema` to prevent confusion.
- **Passing `confianza` without description:** Claude will not know what scale to use unless the tool schema description explicitly states `'high' | 'medium' | 'low'`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON from Claude | Custom JSON prompt + regex parser | `tool_use` + `tool_choice` | Forces tool call; avoids prose preamble, trailing text, markdown fences |
| Schema generation from Pydantic | Manual dict description | `model_json_schema()` + simplification pass | Gets all field names/types automatically; only patch Decimal |
| API key management | Custom env loader | `python-dotenv` + `Settings` (already exists) | Already established in project |
| Retry with backoff | Manual sleep loop | `anthropic` SDK handles transient HTTP errors automatically | SDK retries 429/5xx; only need manual retry for validation failures |
| Request/response logging | Custom file logger | `loguru` (already in project) | JSON-structured logs already configured |

**Key insight:** `tool_choice` is the single most important API feature for this phase — it eliminates the entire class of problems where Claude responds conversationally instead of calling the tool.

---

## Common Pitfalls

### Pitfall 1: Accessing `.text` Instead of `.input` on Tool Response
**What goes wrong:** `AttributeError: 'ToolUseBlock' object has no attribute 'text'` or silent None.
**Why it happens:** When `tool_choice` forces a tool call, `message.content[0]` is a `ToolUseBlock`, not a `TextBlock`.
**How to avoid:** Always access `message.content[0].input` (a dict) for tool_use responses. Assert `message.content[0].type == "tool_use"` defensively.
**Warning signs:** `AttributeError` on `.text`, or `message.stop_reason == "tool_use"` but parsing fails.

### Pitfall 2: Decimal Pattern in JSON Schema Confusing Claude
**What goes wrong:** Claude Haiku returns monetary values as strings matching the regex pattern (`"12345.67"`) instead of numbers, causing `Pydantic` to accept the string but downstream code (Phase 5 storage) to fail on type checks.
**Why it happens:** The Pydantic v2 `Decimal` serializer emits `anyOf [number | pattern-string | null]` in JSON schema mode. Claude interprets the `pattern-string` option as valid.
**How to avoid:** Use `_build_extraction_schema()` pattern above to simplify Decimal fields to `anyOf [number | null]` before passing to `input_schema`.
**Warning signs:** `prima_total` or `suma_asegurada` returns as a string in test responses.

### Pitfall 3: Provenance Fields in Tool Schema
**What goes wrong:** Claude attempts to fill `source_file_hash`, `model_id`, `prompt_version`, `extracted_at` — often hallucinating values.
**Why it happens:** These fields exist in `PolicyExtraction.model_json_schema()` and Claude will try to populate everything in the schema.
**How to avoid:** Remove provenance fields (`source_file_hash`, `model_id`, `prompt_version`, `extracted_at`) from the tool's `input_schema`. Set them programmatically after the API call.
**Warning signs:** `model_id` appears in Claude response with a made-up model name.

### Pitfall 4: Tool Name Mismatch Between `tools` and `tool_choice`
**What goes wrong:** `ValidationError` from the API: `tool_choice.name — The name in tool_choice must exactly match the name in your tools list`.
**Why it happens:** Typo or refactor changes tool name in one place but not the other.
**How to avoid:** Define tool name as a constant: `TOOL_NAME = "extract_policy"` and reference it in both `tools[0]["name"]` and `tool_choice["name"]`.
**Warning signs:** `400 Bad Request` from Anthropic API with message about tool_choice.name.

### Pitfall 5: Schema Includes `$defs` References
**What goes wrong:** Some versions of Anthropic's API do not resolve `$ref` pointers in `input_schema`. The raw `model_json_schema()` output uses `$defs` + `$ref` for nested models (`AseguradoExtraction`, `CoberturaExtraction`).
**Why it happens:** Pydantic v2 uses `$defs` by default for referenced models.
**How to avoid:** Use `PolicyExtraction.model_json_schema(mode="serialization")` — or after generating, call `jsonschema.RefResolver` / inline the `$defs` manually. The simpler approach: verify empirically that the Anthropic API resolves `$defs` correctly (it does as of 2025), but add a test assertion.
**Warning signs:** API returns `400` about `input_schema` being invalid, or nested `asegurados` list is empty in responses.

### Pitfall 6: Max Tokens Insufficient for Large PDFs
**What goes wrong:** Response truncates mid-JSON, causing `ValidationError` on parse.
**Why it happens:** Haiku 4.5 has 64k max output tokens, but large policies with many coverages produce large tool_use responses.
**How to avoid:** Set `max_tokens=4096` for typical policies; make configurable. Monitor `message.usage.output_tokens` in tests to understand typical sizes.
**Warning signs:** `stop_reason == "max_tokens"` instead of `"tool_use"`.

---

## Code Examples

### Full Extraction Call (Verified Pattern)
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/tool-use/overview
# Source: https://murraycole.com/posts/claude-tool-use-pydantic

import anthropic
from datetime import datetime, timezone

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

TOOL_NAME = "extract_policy"

message = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=4096,
    system=SYSTEM_PROMPT_V1,
    messages=[{"role": "user", "content": assembled_text}],
    tools=[{
        "name": TOOL_NAME,
        "description": "Extract all available fields from an insurance policy document.",
        "input_schema": _build_extraction_schema(),   # simplified, no provenance
    }],
    tool_choice={"type": "tool", "name": TOOL_NAME},
)

assert message.content[0].type == "tool_use"
raw: dict = message.content[0].input

# Inject provenance fields not included in tool schema
raw["source_file_hash"] = ingestion.file_hash
raw["model_id"] = message.model
raw["prompt_version"] = PROMPT_VERSION_V1
raw["extracted_at"] = datetime.now(timezone.utc)

policy = PolicyExtraction(**raw)
```

### System Prompt Structure (Template)
```python
# Source: CONTEXT.md decisions
PROMPT_VERSION_V1 = "v1.0.0"

SYSTEM_PROMPT_V1 = """
You are an expert insurance data extractor. You will be given the full text of an insurance policy PDF.

Your task is to call the `extract_policy` tool with ALL available information found in the document.

RULES:
1. Extract only what is explicitly stated in the document — return null for any field not present.
2. NEVER invent, guess, or hallucinate values. A null is always better than a wrong value.
3. The document may be in Spanish or English. Handle both.
4. For `aseguradora` (insurer name) and `tipo_seguro` (insurance type), classify from context if not explicitly labeled.
5. For each field you populate, report your confidence in the `confianza` dict:
   - "high": value is clearly and explicitly stated
   - "medium": value is inferred or partially visible
   - "low": value is ambiguous or reconstructed

SPANISH INSURANCE TERMS:
- Póliza / No. de póliza = policy number (numero_poliza)
- Prima total / Prima neta = total premium (prima_total)
- Vigencia = coverage period (inicio_vigencia / fin_vigencia)
- Deducible = deductible
- Suma asegurada = insured amount
- Contratante = policyholder (nombre_contratante)
- Asegurado = insured party
- Agente / Promotor = agent (nombre_agente)
- Forma de pago = payment method (forma_pago)
- Periodicidad = payment frequency (frecuencia_pago)
"""
```

### Adding `confianza` Field to PolicyExtraction
```python
# Add to policy_extractor/schemas/poliza.py — new field for Phase 3

# Confidence dict: {field_name: "high" | "medium" | "low"}
# Claude self-reports; post-hoc verification may downgrade to "low"
confianza: dict = Field(default_factory=dict)
```

---

## Schema Change Required Before Implementation

The `confianza` dict field does NOT yet exist on `PolicyExtraction`. This is a required schema addition for EXT-04.

**Wave 0 task:** Add `confianza: dict = Field(default_factory=dict)` to `policy_extractor/schemas/poliza.py`.

This field is intentionally excluded from the SQLAlchemy ORM model in Phase 1 (storage is Phase 5). Phase 3 only needs it in the Pydantic model. No DB migration is needed.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Prompt Claude for JSON, parse text response | `tool_use` + `tool_choice` forced call | ~2024 | Eliminates prose preamble, markdown fences, truncation issues |
| Regex/template-per-insurer extraction | Single generic LLM call | This project decision | Handles 50-70 layouts without maintenance |
| `instructor` library for structured output | Native Anthropic tool_use | 2024 | One less dependency; same result |
| `output_config.format` structured outputs | `tool_use` (this project) | Nov 2025 (beta) | Newer feature, but tool_use is GA and equivalent for this use case |

**Current Claude models (as of 2026-03-18, verified from official docs):**
- `claude-haiku-4-5-20251001` — $1/M input, $5/M output, 200k context — DEFAULT for this project
- `claude-sonnet-4-6` — $3/M input, $15/M output, 1M context — configurable upgrade
- Note: `claude-3-haiku-20240307` is DEPRECATED (retiring April 19, 2026). Do NOT use.

**Deprecated/outdated:**
- `claude-3-haiku-20240307`: Deprecated, retiring April 2026. The CONTEXT.md reference to "$0.25/M input" applies to this old model. Haiku 4.5 is $1/M.

---

## Open Questions

1. **Does the Anthropic API fully resolve `$defs` / `$ref` in `input_schema`?**
   - What we know: Community reports suggest it works, but some litellm issues mention nested model failures with certain configurations.
   - What's unclear: Whether `$defs` resolution is guaranteed or model-dependent.
   - Recommendation: Add a test that sends a schema with `$defs` and asserts the nested `asegurados` list populates correctly. If it fails, inline the definitions.

2. **What is the practical token usage for a typical 10-20 page policy PDF?**
   - What we know: Spanish policies tend to have moderate text density; OCR output may add noise.
   - What's unclear: Whether 4096 output tokens is sufficient for a policy with 20+ coverages.
   - Recommendation: Add `message.usage` logging in tests; use fixture PDFs from `tests/fixtures/` to measure empirically.

3. **Does `confianza` need validation (only allow "high"/"medium"/"low")?**
   - What we know: CONTEXT.md defines three levels; `dict` type accepts anything.
   - What's unclear: Whether strict validation adds value vs. flexibility for edge cases.
   - Recommendation: Use `dict` (plain) for now — Claude may occasionally use other values; strict validation can be added in Phase 5 if storage requires it.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed, no config file — uses `pyproject.toml` `testpaths = ["tests"]`) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_extraction.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXT-01 | All policy fields extracted from page text | unit (mocked API) | `pytest tests/test_extraction.py::test_extract_all_fields -x` | Wave 0 |
| EXT-02 | Output validates against PolicyExtraction Pydantic schema | unit (mocked API) | `pytest tests/test_extraction.py::test_output_is_valid_schema -x` | Wave 0 |
| EXT-03 | Insurer and type classified without hard-coding | unit (mocked API) | `pytest tests/test_extraction.py::test_insurer_classification -x` | Wave 0 |
| EXT-04 | Each field has confidence in `confianza` dict | unit (mocked API) | `pytest tests/test_extraction.py::test_confianza_populated -x` | Wave 0 |
| EXT-05 | Spanish PDF and English PDF both extract correctly | unit (two fixture texts) | `pytest tests/test_extraction.py::test_spanish_and_english -x` | Wave 0 |

**Testing approach:** All unit tests mock the `anthropic.Anthropic.messages.create` call and return a synthetic `ToolUseBlock` response. No live API calls in the test suite — tests verify the parsing/validation/retry logic, not Claude's extraction quality.

### Sampling Rate
- **Per task commit:** `pytest tests/test_extraction.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_extraction.py` — covers EXT-01 through EXT-05 with mocked API responses
- [ ] `policy_extractor/schemas/poliza.py` — add `confianza: dict` field (schema change)
- [ ] `policy_extractor/config.py` — add `EXTRACTION_MODEL`, `EXTRACTION_MAX_RETRIES`, `EXTRACTION_PROMPT_VERSION`
- [ ] `pyproject.toml` — add `anthropic>=0.86.0` to dependencies

---

## Sources

### Primary (HIGH confidence)
- [Anthropic Models Overview](https://platform.claude.com/docs/en/about-claude/models/overview) — verified current model IDs and pricing
- [Anthropic Tool Use Overview](https://platform.claude.com/docs/en/build-with-claude/tool-use/overview) — tool_use pattern, `tool_choice` forcing
- [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — comparison of tool_use vs output_config
- `anthropic 0.86.0` — verified installed via `pip show anthropic`
- `PolicyExtraction.model_json_schema()` output — verified locally; Decimal anyOf pattern confirmed

### Secondary (MEDIUM confidence)
- [Claude Tool Use with Pydantic](https://murraycole.com/posts/claude-tool-use-pydantic) — `model_json_schema()` + `tool_choice` pattern, verified against official docs
- [Anthropic Structured Outputs TDS](https://towardsdatascience.com/hands-on-with-anthropics-new-structured-output-capabilities/) — structured output feature overview, Nov 2025

### Tertiary (LOW confidence)
- [LiteLLM Bug: nested models with Anthropic](https://github.com/BerriAI/litellm/issues/7755) — `$defs` resolution concern; unconfirmed for direct SDK use

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — anthropic SDK installed, version verified, official docs read
- Architecture: HIGH — tool_use pattern verified against official docs and working examples
- Pitfalls: MEDIUM — Decimal schema issue verified locally via `model_json_schema()`; `$defs` resolution is MEDIUM (community report only)
- Prompt design: MEDIUM — system prompt structure from CONTEXT.md decisions; exact wording at Claude's discretion

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (Anthropic API stable; model IDs could change)
