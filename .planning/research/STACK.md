# Stack Research

**Domain:** Insurance PDF data extraction system (LLM-powered, local-first, Python CLI + API)
**Researched:** 2026-03-17
**Confidence:** HIGH — all versions verified against PyPI, all core claims verified against official Anthropic docs

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Runtime | 3.11 required by ocrmypdf 17.x; best balance of current ecosystem support and stability on Windows |
| anthropic (SDK) | 0.85.0 | Claude API client | Official Anthropic SDK; native PDF document block support (base64 + Files API); handles both digital-text and vision-based PDFs in one call |
| PyMuPDF | 1.27.2 | PDF parsing (digital-text PDFs) | Fastest Python PDF library; extracts text with layout preservation; detects whether PDF has selectable text (vs. scanned); needed to pre-check before sending to Claude |
| pydantic | 2.12.5 | Data validation + output schema | Industry standard for typed data models; instructor uses pydantic models to define Claude's output schema; models for PolicyData, Insured, Coverage, etc. |
| instructor | 1.14.5 | Structured LLM output | Wraps anthropic SDK to enforce pydantic-defined JSON output from Claude; handles retries on validation failure; removes need to manually parse Claude's response |
| SQLAlchemy | 2.0.48 | ORM for local database | Production-stable 2.0 style; supports SQLite for local-first operation and PostgreSQL for future web migration — same code, different connection string |
| FastAPI | 0.135.1 | JSON/REST API layer | Native pydantic v2 integration; auto-generates OpenAPI docs; same type system as extraction layer; future-ready for web UI |
| Typer | 0.24.1 | CLI interface | Same author as FastAPI; uses same type-hint pattern; single-file or batch PDF processing commands |
| ocrmypdf | 17.3.0 | OCR preprocessing for scanned PDFs | Wraps Tesseract internally; adds searchable text layer to scanned PDFs before sending to Claude; preserves PDF structure; Spanish language pack support built-in |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pdf2image | 1.17.0 | PDF page → PIL image | When ocrmypdf pre-OCR output is insufficient and you need raw image pages sent directly to Claude vision; requires Poppler on Windows |
| pytesseract | 0.3.13 | Direct Tesseract OCR | Fallback or quality-check against ocrmypdf output; useful for per-page confidence scoring to decide if manual review is needed |
| python-dotenv | 1.0.1 | Environment variable management | Store ANTHROPIC_API_KEY outside code; required on Windows where shell env management is less convenient |
| alembic | 1.15.x | Database schema migrations | When schema evolves (new insurer types, new coverage fields); tracks migration history |
| httpx | 0.27.x | Async HTTP client | Already a dependency of anthropic SDK; use for any future webhook or external API calls |
| rich | 13.x | Terminal output formatting | Progress bars and tables for batch CLI processing; shows extraction status per PDF |
| loguru | 0.7.x | Structured logging | Simple drop-in for Python logging; critical for debugging extraction failures at 200+ PDFs/month volume |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Fast Python package manager + virtual env | Replaces pip + venv; dramatically faster installs; lock file support; use `uv sync` for reproducible envs on Windows |
| pytest | Test runner | Test extraction quality with fixture PDFs from each insurer; parametrize over PDF corpus |
| pytest-asyncio | Async test support | Required for testing async FastAPI routes and any async anthropic SDK calls |
| ruff | Linter + formatter | Replaces black + flake8 + isort in one tool; fast; configure in pyproject.toml |

---

## Installation

```bash
# Create virtual environment and install all dependencies
uv venv
uv pip install anthropic==0.85.0 pymupdf==1.27.2 pydantic==2.12.5 instructor==1.14.5
uv pip install sqlalchemy==2.0.48 fastapi==0.135.1 "uvicorn[standard]" typer==0.24.1
uv pip install ocrmypdf==17.3.0 pdf2image==1.17.0 pytesseract
uv pip install python-dotenv rich loguru alembic

# Dev dependencies
uv pip install --dev pytest pytest-asyncio ruff

# Windows: Tesseract must be installed separately
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# Install Spanish language pack: tesseract-ocr-spa.exe
# Add to PATH: C:\Program Files\Tesseract-OCR

# Windows: Poppler must be installed separately (for pdf2image)
# Download: https://github.com/oschwartz10612/poppler-windows/releases
# Add bin/ folder to PATH or pass poppler_path= argument
```

---

## Architecture Decision: When to Use Claude's Native PDF Support vs. OCR Pre-processing

This is the critical fork in the extraction pipeline:

**Digital-text PDFs (selectable text):**
1. Use PyMuPDF to detect if PDF has extractable text (`page.get_text()` returns non-empty)
2. Send PDF directly to Claude via `document` block (base64 or Files API)
3. Claude processes both the extracted text AND the rendered visual — best accuracy

**Scanned PDFs (image-only):**
1. Run ocrmypdf first to produce a text-layer PDF
2. Send that OCR-enhanced PDF to Claude as a document block
3. Claude gets both OCR text (imperfect) and visual — higher accuracy than OCR alone

**Why this hybrid approach:** Claude's PDF support processes each page as an image AND extracts text simultaneously (as of February 2025). For scanned PDFs, sending the raw scan still works but pre-OCR with ocrmypdf improves accuracy because Claude gets text confirmation alongside the visual. The cost is approximately 1,500–3,000 tokens per page for text-heavy documents.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| instructor + pydantic | langchain | Never for this project — LangChain adds abstraction overhead without benefit when using a single provider (Claude) with direct SDK |
| instructor + pydantic | raw tool_use JSON parsing | Only if instructor becomes incompatible with a future anthropic SDK version; same output, more boilerplate |
| SQLAlchemy + SQLite | TinyDB / JSON files | If schema were truly flat and queries never needed; insurance policies have relational data (policy → insureds → coverages) that needs proper relations |
| SQLAlchemy + SQLite | PostgreSQL from day one | When multi-user web access is needed; SQLAlchemy makes migration trivial — just change DATABASE_URL |
| FastAPI | Flask | Flask lacks native async; pydantic integration requires extra plugins; FastAPI is now the standard for new Python APIs |
| ocrmypdf | Unstructured.io | Unstructured is excellent for RAG/chunk workflows; overkill here — we want raw text for Claude, not chunked embeddings |
| PyMuPDF | pdfplumber | pdfplumber is better for coordinate-based table extraction but is 10x slower; not needed when Claude handles structure understanding |
| Typer | argparse / click | argparse has no type hints; Typer is built on Click but with zero boilerplate; same Click ecosystem under the hood |
| uv | pip + venv | pip is slower; uv resolves dependencies faster and produces lock files; especially valuable on Windows where pip can struggle with binary dependencies |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyPDF2 | Abandoned in 2023; superseded by pypdf; extract quality is inferior to PyMuPDF | PyMuPDF for full extraction; pypdf only if you need minimal PDF manipulation without MuPDF dependency |
| Camelot / tabula-py | Table extraction libraries designed for structured PDFs with defined table regions; insurance PDFs vary too much in layout; Claude handles tables directly | Claude's visual comprehension via document blocks |
| LangChain | Adds unnecessary abstraction for a single-provider, single-task pipeline; version compatibility issues are frequent; debugging is harder | Direct anthropic SDK + instructor |
| textract | Windows support is broken/requires WSL; relies on external binaries that conflict on Windows 11 | ocrmypdf (Tesseract-based, Windows native) |
| EasyOCR | PyTorch dependency (~2GB); slow on CPU; accuracy not significantly better than Tesseract 5.x for Spanish printed text; unnecessary for insurance policy documents (printed, not handwritten) | ocrmypdf + Tesseract with spa language pack |
| SQLite JSON-only schema | Storing all extracted data as a single JSON blob loses queryability — you cannot filter by insurer, date range, or coverage type without loading all rows | SQLAlchemy ORM with structured columns + JSON column only for variable/overflow fields |
| Alembic auto-migrate on startup | Auto-migration on app start is dangerous in production; can corrupt data | Explicit `alembic upgrade head` as a deploy/setup step |

---

## Stack Patterns by Variant

**If a PDF is digital-text (detected by PyMuPDF):**
- Skip OCR entirely
- Send PDF as base64 document block to Claude directly
- Lower cost, faster processing, higher accuracy

**If a PDF is scanned (image-only):**
- Run `ocrmypdf --language spa+eng input.pdf ocr_output.pdf`
- Send `ocr_output.pdf` to Claude as document block
- Claude uses OCR text as anchor + visual confirmation

**If a PDF exceeds 32MB or 100 pages:**
- Split with PyMuPDF: `doc.select([0..49])` to produce sub-documents
- Process each chunk, merge extracted fields in application layer
- Uncommon for insurance policies but handle gracefully

**If batch processing 200+ PDFs/month:**
- Use Anthropic Message Batches API (`client.messages.batches.create`)
- 50% cost reduction vs. synchronous calls
- Results available within 24 hours; suitable for end-of-day batch jobs

**If schema evolves (new insurer, new coverage type):**
- Add JSON overflow column to store insurer-specific fields not in base schema
- Use pydantic `model_extra = "allow"` to capture arbitrary fields from Claude
- Run Alembic migration to add columns when a field becomes standard

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| anthropic 0.85.0 | instructor 1.14.5 | Instructor uses `instructor.from_anthropic(client)` pattern; verified working |
| pydantic 2.12.5 | instructor 1.14.5 | Instructor requires pydantic v2; pydantic v1 is EOL and incompatible |
| pydantic 2.12.5 | FastAPI 0.135.1 | FastAPI 0.100+ requires pydantic v2; fully compatible |
| SQLAlchemy 2.0.48 | alembic 1.15.x | Alembic 1.13+ required for SQLAlchemy 2.0 compatibility |
| ocrmypdf 17.3.0 | Python 3.11+ | ocrmypdf 17.x dropped support for Python 3.10; requires 3.11 minimum |
| PyMuPDF 1.27.2 | Python 3.9-3.13 | No external MuPDF install needed since 1.24.0; bundled binaries |

---

## Claude API Constraints (Verified from Official Docs)

These limits directly affect system design decisions:

| Constraint | Value | Impact |
|------------|-------|--------|
| Max PDF size per request | 32 MB | Most insurance policies are <5MB; not a practical limit |
| Max pages per request (claude-sonnet-4-6) | 100 pages | Use claude-sonnet-4-6 (200k context); standard policies are <50 pages |
| Max pages per request (claude-opus-4-6) | 600 pages | Reserve for edge cases; opus costs 3x more |
| Token cost per page | 1,500–3,000 tokens | Budget ~2,000 tokens/page + 2,000 for extraction prompt; 10-page policy ≈ 22,000 tokens |
| Supported formats | Standard PDF, no encryption | Reject password-protected PDFs before sending |
| PDF via Files API | Reusable file_id | Upload once, query multiple times; useful for re-extraction with improved prompts |

---

## Sources

- [Anthropic PDF Support — Official Docs](https://platform.claude.com/docs/en/build-with-claude/pdf-support) — PDF limits, document block format, Files API (HIGH confidence)
- [anthropic PyPI](https://pypi.org/project/anthropic/) — SDK version 0.85.0 (HIGH confidence, verified March 2026)
- [instructor PyPI](https://pypi.org/project/instructor/) — version 1.14.5 (HIGH confidence, verified March 2026)
- [Instructor + Anthropic Integration](https://python.useinstructor.com/integrations/anthropic/) — Pydantic structured output pattern (HIGH confidence)
- [PyMuPDF PyPI](https://pypi.org/project/PyMuPDF/) — version 1.27.2 (HIGH confidence, verified March 2026)
- [ocrmypdf PyPI](https://pypi.org/project/ocrmypdf/) — version 17.3.0, Python 3.11+ requirement (HIGH confidence)
- [SQLAlchemy PyPI](https://pypi.org/project/SQLAlchemy/) — version 2.0.48 stable (HIGH confidence)
- [FastAPI PyPI](https://pypi.org/project/fastapi/) — version 0.135.1 (HIGH confidence)
- [Typer PyPI](https://pypi.org/project/typer/) — version 0.24.1 (HIGH confidence)
- [pdf2image PyPI](https://pypi.org/project/pdf2image/) — version 1.17.0 (MEDIUM confidence — last release Jan 2024, still maintained)
- [PyMuPDF4LLM docs](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/) — LLM-optimized extraction patterns (HIGH confidence)
- [I Tested 7 Python PDF Extractors (2025 Edition)](https://dev.to/onlyoneaman/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-akm) — PyMuPDF performance comparison (MEDIUM confidence)
- [Best Python PDF to Text Parser Libraries: A 2026 Evaluation](https://unstract.com/blog/evaluating-python-pdf-to-text-libraries/) — Current library landscape (MEDIUM confidence)

---

*Stack research for: Insurance PDF data extraction system (extractor_pdf_polizas)*
*Researched: 2026-03-17*
