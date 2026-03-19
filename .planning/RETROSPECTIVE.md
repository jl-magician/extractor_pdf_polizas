# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-19
**Phases:** 5 | **Plans:** 10 | **Timeline:** 2 days

### What Was Built
- Pydantic v2 extraction schemas with Spanish domain terms, date normalization, Decimal precision
- Per-page PDF classifier with OCR pipeline (Spanish + English fallback)
- Claude API extraction with tool_use, hallucination verification, 3-level confidence scoring
- `poliza-extractor` CLI with 5 subcommands (extract, batch, export, import-json, serve)
- SQLite persistence with upsert dedup + FastAPI CRUD with filtering and Swagger docs

### What Worked
- TDD approach across all phases caught issues early (e.g., PyMuPDF API differences from docs)
- Phase-by-phase discuss → research → plan → execute → verify pipeline kept each phase focused
- Mocking API calls in tests allowed full test coverage without incurring Claude API costs
- Spanish domain terms in field names was the right call — agency team can read JSON directly
- Single-pass extraction (vs two-pass classify+extract) saved complexity and API costs

### What Was Inefficient
- Research sometimes found outdated API patterns (e.g., `get_image_rects()` signature changed between PyMuPDF versions) — executors had to auto-fix
- Some multiline Python commands in UAT tests broke when users copy-pasted due to lost spaces — should use scripts or run commands directly
- `datetime.utcnow()` deprecation warnings across the codebase — should have used `datetime.now(UTC)` from the start

### Patterns Established
- Pydantic v2 models as contracts between phases (schemas define the API, ORM mirrors exactly)
- `campos_adicionales` JSON overflow pattern on every table for insurer-specific fields
- `Settings` class with python-dotenv for all configuration
- Rich for CLI progress + Console(stderr=True) for pipe-friendly output
- Mocked Anthropic API tests with synthetic ToolUseBlock responses

### Key Lessons
1. Lock data contracts (Pydantic schemas) before writing any processing code — Phase 1 paid off hugely
2. Per-page PDF classification is essential for Mexican insurance PDFs that mix digital text with scanned pages
3. Haiku is sufficient for structured data extraction from insurance PDFs — start cheap, upgrade only if needed
4. Post-hoc hallucination verification (checking extracted values against source text) is a lightweight safety net worth adding

### Cost Observations
- Model mix: opus for planning, sonnet for execution/verification/research, haiku for runtime extraction
- 79 commits across 2 days
- Notable: All 10 plans executed successfully on first attempt — zero gap closure cycles needed

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Timeline | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | 2 days | 5 | Initial process — discuss → research → plan → execute → verify |

### Cumulative Quality

| Milestone | Tests | UAT | Verification |
|-----------|-------|-----|-------------|
| v1.0 | 153 | 33/33 pass | 5/5 phases passed |

### Top Lessons (Verified Across Milestones)

1. Non-retrofittable contracts first — data model decisions cascade through every subsequent phase
2. TDD with mocked external APIs gives full coverage without runtime costs
