# Milestones

## v1.0 MVP (Shipped: 2026-03-19)

**Phases completed:** 5 phases, 10 plans, 153 tests passing
**Timeline:** 2 days (2026-03-17 → 2026-03-19)
**Python LOC:** 5,161 across 96 files
**Requirements:** 24/24 v1 requirements satisfied
**UAT:** 33/33 tests passed across all 5 phases

**Key accomplishments:**
1. Pydantic v2 extraction contract with Spanish domain terms, date normalization, Decimal precision
2. Per-page PDF classifier using image coverage ratio with OCR fallback (Spanish + English)
3. Claude API extraction pipeline with tool_use structured output, hallucination verification, confidence scoring
4. `poliza-extractor` CLI with extract/batch/export/import/serve subcommands and Rich progress
5. SQLite persistence with upsert dedup by (numero_poliza, aseguradora) + FastAPI CRUD with filtering

**Delivered:** Complete pipeline for extracting structured data from any insurance policy PDF — ingest, classify, OCR, extract via Claude API, persist to SQLite, query via CLI or REST API.

---

