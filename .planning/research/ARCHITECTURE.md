# Architecture Research

**Domain:** Insurance PDF extraction + LLM structured data pipeline
**Researched:** 2026-03-17
**Confidence:** HIGH (Claude API official docs) / MEDIUM (pipeline patterns from multiple sources)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Entry Layer (CLI)                       │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Single PDF  │  │  Batch mode  │  │  API server      │   │
│  │  command     │  │  (folder)    │  │  (future web)    │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         └─────────────────┴─────────────────── ┘            │
│                            │                                 │
├────────────────────────────▼────────────────────────────────┤
│                    Ingestion Layer                           │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐       ┌────────────────────────────┐   │
│  │  PDF Loader      │       │  OCR Detection             │   │
│  │  (file → bytes)  │──────▶│  (digital vs scanned?)     │   │
│  └──────────────────┘       └────────────────┬───────────┘   │
│                                              │               │
├──────────────────────────────────────────────▼──────────────┤
│                    Extraction Layer                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐    │
│  │               Claude API Client                       │    │
│  │   • Sends PDF as base64 document block               │    │
│  │   • Handles both digital text + scanned images       │    │
│  │   • Receives structured JSON via tool_use schema     │    │
│  └──────────────────────────┬───────────────────────────┘    │
│                             │                                │
├─────────────────────────────▼───────────────────────────────┤
│                    Validation Layer                          │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────────┐  ┌──────────────────────────────┐    │
│  │  Pydantic Schema   │  │  Field-level validation       │    │
│  │  Validation        │  │  (dates, currency, RFC, etc.) │    │
│  └─────────┬──────────┘  └──────────────┬───────────────┘    │
│            └─────────────────────────── ┘                    │
│                           │                                  │
├───────────────────────────▼─────────────────────────────────┤
│                    Storage Layer                             │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────────────────────┐   │
│  │  SQLite DB       │  │  Raw JSON files                  │   │
│  │  (structured     │  │  (original API response,         │   │
│  │   core fields)   │  │   audit trail, unknown fields)   │   │
│  └──────────────────┘  └──────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    Query/API Layer                           │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────────────────────┐   │
│  │  CLI query tool  │  │  FastAPI JSON endpoints          │   │
│  │  (immediate use) │  │  (for future web/integrations)   │   │
│  └──────────────────┘  └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| CLI Entry | Accept file paths, options (single/batch), invoke pipeline | `click` or `typer` Python library |
| PDF Loader | Open PDF file, read bytes, detect if path is valid | `pathlib` + file I/O |
| OCR Detection | Determine if PDF has selectable text or is image-only | `pymupdf` (fitz) text coverage heuristic |
| Claude API Client | Send PDF to Claude, receive structured extraction, retry on failure | `anthropic` Python SDK, base64 document blocks |
| Pydantic Schema | Define expected fields, types, optional vs required; validate LLM output | `pydantic` v2 models |
| Field Validator | Post-extraction checks: date format, currency range, RFC/ID patterns | Pydantic field validators + regex |
| Storage Writer | Persist structured data to SQLite core tables + JSON blob for extras | `sqlmodel` or `sqlite3` + `json` |
| Raw JSON Store | Save full Claude response per PDF for debugging / re-processing | Flat files in `data/raw/` folder |
| Query CLI | Simple data retrieval: search by insurer, date, policy number | `sqlite3` queries via CLI |
| FastAPI Server | REST endpoints exposing stored data as JSON | `fastapi` + `uvicorn` (built in v1 for future use) |

## Recommended Project Structure

```
extractor_pdf_polizas/
├── cli.py                    # Main CLI entry point (typer app)
├── config.py                 # API keys, DB path, settings (from env)
│
├── ingestion/
│   ├── __init__.py
│   ├── loader.py             # Read PDF file → bytes
│   └── detector.py           # Detect digital vs scanned PDF
│
├── extraction/
│   ├── __init__.py
│   ├── client.py             # Claude API calls (send PDF, get response)
│   ├── prompts.py            # Extraction prompt templates
│   └── schemas.py            # Pydantic models for extracted data
│
├── validation/
│   ├── __init__.py
│   └── validators.py         # Field-level validation rules (dates, RFC, etc.)
│
├── storage/
│   ├── __init__.py
│   ├── database.py           # SQLite setup, migrations, connection
│   ├── models.py             # SQLModel/SQLAlchemy table definitions
│   └── writer.py             # Save extracted data to DB + raw JSON
│
├── api/
│   ├── __init__.py
│   ├── main.py               # FastAPI app + routes
│   └── serializers.py        # Response shapes for API consumers
│
├── data/
│   ├── raw/                  # Raw Claude API responses (JSON files)
│   ├── input/                # PDFs to process (drop folder for batch)
│   └── polizas.db            # SQLite database file
│
└── tests/
    ├── fixtures/             # Sample PDFs for testing (anonymized)
    ├── test_extraction.py
    ├── test_validation.py
    └── test_storage.py
```

### Structure Rationale

- **ingestion/:** Isolated file handling — no LLM concerns here. Detector decides early whether to tell Claude "this is scanned" in the prompt.
- **extraction/:** All Claude API interaction lives here. `schemas.py` is the contract between LLM output and the rest of the system. Changing the schema only touches this module.
- **validation/:** Separated from extraction intentionally — LLM gives a best-effort result, validation catches what's wrong without tangling with API calls.
- **storage/:** Single responsibility: persist. `writer.py` accepts a validated Pydantic object and writes it; it does not know about Claude.
- **api/:** The FastAPI layer is thin — it reads from DB and serializes. No business logic here.
- **data/raw/:** Saving raw Claude responses enables re-processing if schemas change without re-calling the API and paying again.

## Architectural Patterns

### Pattern 1: PDF-as-Document to Claude (Native Vision)

**What:** Send the entire PDF as a `document` content block to Claude. Claude converts each page to an image internally and processes both text and visual layout. No pre-processing OCR step required.

**When to use:** Always, for this project. Claude handles both digital text and scanned PDFs natively. For scanned PDFs, Claude's vision reads the image. For digital PDFs, Claude gets both the extracted text and page images.

**Trade-offs:** Simpler pipeline (no local OCR library dependency). Token cost is higher (~1,500-3,000 tokens/page for text + image cost per page). For a 10-page policy at ~$3/1M tokens, extraction per policy is approximately $0.05-0.15. At 200 policies/month = $10-30/month.

**Example:**
```python
import anthropic
import base64
from pathlib import Path

def extract_policy(pdf_path: Path, schema_prompt: str) -> dict:
    client = anthropic.Anthropic()
    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    message = client.messages.create(
        model="claude-sonnet-4-5",  # balance cost/quality
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {"type": "text", "text": schema_prompt},
            ],
        }],
    )
    return message.content
```

### Pattern 2: Pydantic Schema as Extraction Contract

**What:** Define a Pydantic v2 model representing every field you want to extract. Use this model both as the prompt schema description (auto-generate JSON Schema for the prompt) and as the validation target for LLM output.

**When to use:** Always. This is the key architectural decision that makes the extraction reliable and the data consistent regardless of how messy or varied the source PDF is.

**Trade-offs:** Up-front effort to define good schemas. Optional fields (most insurance fields are conditional) require `Optional[X] = None` which is verbose. The benefit is that downstream code (storage, API) can rely on typed data.

**Example:**
```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class Asegurado(BaseModel):
    nombre: str
    rfc: Optional[str] = None
    fecha_nacimiento: Optional[date] = None

class PolicyExtraction(BaseModel):
    numero_poliza: str
    aseguradora: str
    tipo_seguro: str
    fecha_inicio_vigencia: Optional[date] = None
    fecha_fin_vigencia: Optional[date] = None
    prima_total: Optional[float] = None
    moneda: Optional[str] = "MXN"
    contratante: Optional[str] = None
    asegurados: list[Asegurado] = Field(default_factory=list)
    coberturas: list[dict] = Field(default_factory=list)
    deducible: Optional[str] = None
    suma_asegurada: Optional[float] = None
    agente: Optional[str] = None
    campos_adicionales: dict = Field(default_factory=dict)
    # ^ catch-all for insurer-specific fields not in core schema
```

### Pattern 3: Hybrid SQLite Storage (Core Columns + JSON Blob)

**What:** Store well-known, frequently queried fields as proper SQLite columns. Store the remainder (insurer-specific fields, full extracted object) in a JSON TEXT column. This accommodates the 50-70 structure variations without requiring schema migrations every time a new insurer is added.

**When to use:** This project specifically, where core fields are predictable (policy number, insurer, dates, premium) but extended fields vary wildly by insurer and product type.

**Trade-offs:** SQL queries on core fields remain fast and indexable. JSON fields require `json_extract()` for filtering — acceptable for low-volume local use. Avoids EAV (entity-attribute-value) complexity or schema explosion with 50+ nullable columns.

**Example:**
```python
# SQLite table: policies
# Core columns: id, numero_poliza, aseguradora, tipo_seguro,
#               fecha_inicio, fecha_fin, prima_total, moneda,
#               contratante, created_at, source_file
# JSON column:  extracted_data (full Pydantic model as JSON)
#               campos_adicionales (insurer-specific extras)

import sqlite3, json

def save_policy(conn, extraction: PolicyExtraction, source_file: str):
    conn.execute("""
        INSERT INTO policies
            (numero_poliza, aseguradora, tipo_seguro,
             fecha_inicio, fecha_fin, prima_total, moneda,
             contratante, source_file, extracted_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        extraction.numero_poliza,
        extraction.aseguradora,
        extraction.tipo_seguro,
        str(extraction.fecha_inicio_vigencia),
        str(extraction.fecha_fin_vigencia),
        extraction.prima_total,
        extraction.moneda,
        extraction.contratante,
        source_file,
        extraction.model_dump_json(),  # full JSON blob
    ))
```

## Data Flow

### Single PDF Processing Flow

```
User runs: python cli.py extract poliza.pdf
    │
    ▼
[CLI] validates file path exists, is .pdf
    │
    ▼
[ingestion/loader.py] reads PDF → bytes
    │
    ▼
[ingestion/detector.py] checks text coverage via pymupdf
    │  (annotates metadata: "scanned=True/False", page count)
    ▼
[extraction/client.py] encodes PDF as base64
    │  builds prompt with Pydantic schema description
    │  calls anthropic.messages.create()
    ▼
[Claude API] processes PDF (pages as images + text)
    │  returns JSON structured response
    ▼
[extraction/schemas.py] parses raw JSON → PolicyExtraction (Pydantic)
    │  raises ValidationError if required fields missing
    ▼
[validation/validators.py] applies domain rules
    │  (date coherence, currency format, RFC pattern)
    │  logs warnings for fields that couldn't be extracted
    ▼
[storage/writer.py] writes to SQLite (core columns + JSON blob)
    │  saves raw Claude response to data/raw/{uuid}.json
    ▼
[CLI] prints summary: "Extracted: Poliza #12345, AXA, Auto, 2025-01-01 → 2026-01-01"
```

### Batch Processing Flow

```
User runs: python cli.py batch ./input_folder/
    │
    ▼
[CLI] glob all *.pdf in folder → list of paths
    │  (optionally filters already-processed by checking DB)
    ▼
[loop] for each PDF, runs single PDF flow above
    │  tracks: processed, failed, skipped counts
    │  continues on per-PDF errors (logs, does not abort batch)
    ▼
[CLI] prints final summary table
```

### API Query Flow (v1 — local use)

```
GET /api/policies?aseguradora=AXA&year=2025
    │
    ▼
[FastAPI route] parses query params
    │
    ▼
[storage/database.py] builds SQL query with filters
    │  SELECT * FROM policies WHERE aseguradora = ? AND fecha_inicio LIKE '2025%'
    ▼
[serializers.py] converts SQLite rows → Pydantic response models
    │
    ▼
JSON response: [{numero_poliza, aseguradora, tipo_seguro, ...}]
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-200 policies/month (current) | Monolith is correct. Single process, SQLite, no queue needed. Run batch manually or via Windows Task Scheduler. |
| 500-2000 policies/month | Add simple job queue (SQLite-backed with `rq` or just a `processing_status` column). Consider prompt caching for repeated insurer templates. |
| 2000+ policies/month | Move to PostgreSQL. Add async processing with Celery or `asyncio`. Consider Anthropic Batch API (50% cost reduction for non-urgent processing). |

### Scaling Priorities

1. **First bottleneck:** Claude API rate limits and cost. Mitigation: use Anthropic Message Batches API for bulk processing, enable prompt caching for system prompt (saves tokens on repeated calls to same insurer type).
2. **Second bottleneck:** SQLite write contention (only relevant for concurrent access). Mitigation: SQLite WAL mode, or migrate to PostgreSQL when web UI is added.

## Anti-Patterns

### Anti-Pattern 1: Template-per-Insurer Approach

**What people do:** Build regex or XPath templates for each insurer (AXA template, GNP template, Qualitas template, etc.) to extract fixed fields from known positions.

**Why it's wrong:** 50-70 PDF structures means 50-70 templates to maintain. Any change to an insurer's PDF format breaks the template silently. New insurers require developer work before the system can process them. This is exactly the manual work being replaced.

**Do this instead:** Send the whole PDF to Claude with a schema describing what to extract. Claude handles layout variation automatically. One prompt serves all insurers.

### Anti-Pattern 2: Pre-Processing OCR Before Sending to Claude

**What people do:** Run Tesseract/PaddleOCR locally on the PDF, get plain text, then send that text to Claude for extraction.

**Why it's wrong:** Discards layout information. OCR errors propagate into extraction. Extra dependency (Tesseract) with Windows installation friction. Claude's native PDF support already converts pages to images and extracts text — it does both simultaneously with better context about spatial relationships between fields.

**Do this instead:** Send the raw PDF bytes as a base64 `document` block. Claude handles both digital text and scanned images natively. Reserve local OCR only as a fallback if Claude's PDF endpoint returns quality issues for a specific document.

### Anti-Pattern 3: Strict Schema — Failing on Missing Fields

**What people do:** Define all insurance fields as required in the Pydantic schema. Treat any missing field as a hard error.

**Why it's wrong:** Insurance PDFs are notoriously inconsistent. Some policies lack certain fields (e.g., individual auto policies don't have "suma asegurada por bien"). Hard failures on every policy with unusual structure kills the batch and requires manual intervention.

**Do this instead:** All fields except the identity fields (numero_poliza, aseguradora) should be `Optional`. Use a `campos_adicionales: dict` catch-all for truly unknown fields. Log extraction confidence warnings but persist what was extracted. Let users review incomplete extractions rather than blocking the pipeline.

### Anti-Pattern 4: No Raw Response Storage

**What people do:** Extract structured data, save to DB, discard the original API response.

**Why it's wrong:** When the extraction schema changes (it will), or when a field was extracted wrongly, there's no way to re-process without re-calling the Claude API (paying again). Raw response storage is the audit trail.

**Do this instead:** Always save the full Claude response JSON to `data/raw/{source_file_hash}.json` alongside the DB record. Implement a `re-process` CLI command that reads from raw JSON instead of calling Claude.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Claude API (Anthropic) | REST via `anthropic` Python SDK. Base64 PDF document blocks. | Max 32MB per request, 100 pages/request. Use Files API for large PDFs to avoid re-uploading same file. Prompt cache eligible after 1024 tokens. |
| Anthropic Files API | Upload PDF once, reference by `file_id` | Beta feature as of 2025. Useful for batch processing same PDF with multiple queries. Avoids repeated base64 encoding. |
| Anthropic Message Batches API | Submit up to 100 requests per batch, async results | 50% cost reduction. Useful for nightly batch runs. Results available within 24 hours. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI ↔ extraction/ | Direct Python function calls | CLI is the orchestrator; extraction module is stateless |
| extraction/ ↔ validation/ | Pydantic model passing | `client.py` returns raw dict; `schemas.py` parses to Pydantic; `validators.py` receives typed model |
| extraction/ ↔ storage/ | Pydantic model passing | storage/writer.py receives validated PolicyExtraction; no knowledge of Claude |
| storage/ ↔ api/ | SQLite connection + ORM queries | FastAPI reads from DB; no direct coupling to extraction layer |
| CLI ↔ storage/ | DB connection for dedup check | CLI checks `processed_files` table before submitting to extraction; avoids re-processing |

## Suggested Build Order

Dependencies between components dictate this order:

1. **schemas.py (Pydantic models)** — All other components depend on the data contract. Define this first, even if incomplete.
2. **extraction/client.py** — Can be developed and tested in isolation with a single sample PDF. Proves Claude integration works.
3. **storage/database.py + storage/models.py** — Define DB schema based on what extraction produces.
4. **storage/writer.py** — Connects extraction output to storage. Proves end-to-end flow.
5. **cli.py (single file mode)** — Wires ingestion → extraction → validation → storage into one command.
6. **validation/validators.py** — Add domain validation incrementally; not a blocker for MVP.
7. **cli.py (batch mode)** — Extends single-file mode with loop + error handling.
8. **api/main.py (FastAPI)** — Built last. Reads from already-populated DB. Low risk.

## Sources

- Claude PDF Support official documentation: [https://platform.claude.com/docs/en/build-with-claude/pdf-support](https://platform.claude.com/docs/en/build-with-claude/pdf-support)
- LLMs for Structured Data Extraction from PDFs (Unstract, 2026): [https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/)
- Designing an LLM-Based Document Extraction System (Medium): [https://medium.com/@dikshithraj03/turning-messy-documents-into-structured-data-with-llms-d8a6242a31cc](https://medium.com/@dikshithraj03/turning-messy-documents-into-structured-data-with-llms-d8a6242a31cc)
- Hybrid OCR-LLM Pipeline Pattern: [https://aiexpjourney.substack.com/p/hybrid-ocr-llm-not-a-bigger-model](https://aiexpjourney.substack.com/p/hybrid-ocr-llm-not-a-bigger-model)
- Instructor (structured LLM outputs library): [https://python.useinstructor.com/](https://python.useinstructor.com/)
- Pydantic AI structured outputs: [https://ai.pydantic.dev/output/](https://ai.pydantic.dev/output/)
- SQLite JSON1 extension (hybrid schema pattern): [https://charlesleifer.com/blog/using-the-sqlite-json1-and-fts5-extensions-with-python/](https://charlesleifer.com/blog/using-the-sqlite-json1-and-fts5-extensions-with-python/)
- AI-Powered Insurance Document Extractor (FastAPI + AI): [https://medium.com/@shibashishnayak97/building-an-ai-powered-insurance-document-extractor-with-fastapi-vertex-ai-streamlit-10d2568bc5e1](https://medium.com/@shibashishnayak97/building-an-ai-powered-insurance-document-extractor-with-fastapi-vertex-ai-streamlit-10d2568bc5e1)
- Structured data extraction with LLM schemas (Simon Willison, 2025): [https://simonwillison.net/2025/Feb/28/llm-schemas/](https://simonwillison.net/2025/Feb/28/llm-schemas/)

---
*Architecture research for: Insurance PDF data extraction + LLM pipeline*
*Researched: 2026-03-17*
