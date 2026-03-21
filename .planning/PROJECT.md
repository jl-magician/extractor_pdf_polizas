# Extractor PDF Polizas

## What This Is

Sistema de extraccion inteligente de informacion de polizas de seguros en formato PDF. Utiliza IA (Claude API con Haiku) para interpretar y extraer datos estructurados de polizas provenientes de ~10 aseguradoras diferentes, cada una con 5-7 tipos de seguros (~50-70 estructuras de PDF distintas). Incluye CLI completo (`poliza-extractor`), base de datos SQLite con migraciones Alembic, API REST (FastAPI) con upload de PDFs, procesamiento concurrente por lotes, evaluacion de calidad con Sonnet, y suite de regresion con fixtures doradas.

## Core Value

Extraer automaticamente toda la informacion posible de cualquier poliza de seguro en PDF — sin importar la aseguradora o estructura — y almacenarla de forma estructurada para consulta, reporteo e integracion con otros sistemas.

## Current State (v2.0 in progress, Phase 14 complete 2026-03-21)

- **Python LOC:** ~4,500 (app) + ~7,500 (tests) = ~12,000 total
- **Tech stack:** Python 3.11+, Pydantic v2, SQLAlchemy 2.0, Alembic, PyMuPDF, ocrmypdf, Anthropic SDK, Typer, Rich, FastAPI, openpyxl, Jinja2, HTMX, Tailwind CSS
- **Tests:** 418 passing, 3 skipped (2 Tesseract-dependent, 1 regression fixture)
- **CLI:** `poliza-extractor` with extract, batch, export, import-json, serve, create-fixture subcommands
- **API:** FastAPI CRUD + PDF upload + Web UI at localhost:8000 (5 pages: Dashboard, Upload, Poliza List, Detail, Job History)
- **Database:** SQLite with WAL mode, Alembic migrations (4 versions), polizas, asegurados, coberturas, ingestion_cache, batch_jobs tables
- **Milestones shipped:** v1.0 MVP (2026-03-18), v1.1 API & Quality (2026-03-19)

## Requirements

### Validated

- ✓ Extraccion de datos de PDFs de polizas usando Claude API (texto digital y escaneados con OCR) — v1.0
- ✓ Soporte para espanol e ingles — v1.0
- ✓ Extraccion flexible sin templates fijos (~50-70 estructuras) — v1.0
- ✓ Captura de todos los datos posibles (contratante, asegurados, coberturas, costos, vigencia, etc.) — v1.0
- ✓ Manejo de multiples asegurados por poliza — v1.0
- ✓ Base de datos local SQLite — v1.0
- ✓ API/JSON para datos estructurados — v1.0
- ✓ CLI para procesamiento individual y por lote — v1.0
- ✓ Esquema dinamico con campos variables por aseguradora — v1.0
- ✓ Alembic migrations for schema versioning — v1.1
- ✓ Excel/CSV export with correct numeric/date types — v1.1
- ✓ PDF Upload API with async job system — v1.1
- ✓ Concurrent batch processing with rate limit retry — v1.1
- ✓ Sonnet quality evaluator (opt-in) — v1.1
- ✓ Golden dataset regression suite — v1.1

### Active

- [x] Web UI for uploading PDFs and viewing extraction results — Phase 14
- [ ] Manual data editing/correction of extracted fields in browser
- [x] Dashboard with extraction statistics and quality metrics — Phase 14
- [ ] PDF report generation from extracted poliza data
- [ ] Customizable report templates per insurer
- [x] Extraction prompt improvements for financial table handling — Phase 13
- [x] Post-extraction validation (cross-check financial fields) — Phase 13
- [x] Configurable field exclusion list — Phase 13
- [x] Auto-OCR fallback for digital pages with <10 chars — Phase 13
- [ ] Sonnet review pass for campos_adicionales field swaps
- [ ] Human-in-the-loop review UI (side-by-side PDF + extraction)
- [ ] Expanded golden dataset (20+ fixtures, all 10 insurers)
- [ ] Evaluator auto-triggered on batch samples

### Out of Scope

- Aplicacion movil — fuera de alcance por ahora
- Integracion directa con sistemas de aseguradoras — fuera de alcance
- Celery/Redis distributed job queue — not needed at current scale (<10k PDFs/month)
- Automated golden dataset expansion from production — needs human review workflow first
- Policy comparison and analytics (coverage gap analysis) — requires stable schema and UI first

## Context

- Oficina de agentes de seguros en Mexico que trabaja con 10 aseguradoras
- Cada aseguradora tiene 5-7 tipos de seguros (auto, vida, gastos medicos, hogar, etc.)
- Actualmente todo el proceso de extraccion es manual: alguien lee cada PDF y copia datos
- Los PDFs son mixtos: algunos son texto digital seleccionable, otros son imagenes escaneadas
- El volumen es de mas de 200 polizas nuevas por mes
- A futuro, los datos extraidos serviran como base para un sistema propio de gestion de polizas
- Los PDFs estan en espanol principalmente, con algunos en ingles
- v1.0 shipped with full pipeline: ingest → extract → persist → query
- v1.1 added HTTP integration, concurrent batch, quality evaluation, export formats, and regression testing

## Constraints

- **LLM Provider**: Claude API (Anthropic) — Haiku default, Sonnet for evaluation
- **Plataforma**: Windows 11, aplicacion local CLI + API REST
- **PDFs mixtos**: Soporta texto digital e imagenes escaneadas (OCR via ocrmypdf + Tesseract)
- **Idioma**: Soporte para espanol e ingles en los PDFs
- **Escalabilidad**: Debe manejar 200+ polizas/mes con tiempos razonables (concurrent batch with 3 workers default)
- **Almacenamiento**: SQLite local con WAL mode, Alembic migrations, JSON/Excel/CSV export, FastAPI query layer

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Claude API para extraccion | Usuario ya tiene API key; Claude maneja bien documentos complejos y multilingues | ✓ Good — works with tool_use for structured output |
| IA sin templates fijos | 50-70 estructuras diferentes hacen insostenible mantener templates; IA se adapta automaticamente | ✓ Good — single-pass extraction handles variety |
| Local-first, web despues | Validar la extraccion antes de invertir en infraestructura web | ✓ Good — CLI + API delivered in v1.0, upload API in v1.1 |
| Haiku default, Sonnet configurable | Cost efficiency for 200+ policies/month; --model flag for quality upgrade | ✓ Good — configurable via Settings; Sonnet evaluation opt-in |
| Single-pass extraction | One API call per PDF instead of two-pass classify+extract | ✓ Good — simpler, cheaper, sufficient quality |
| Upsert by (numero_poliza, aseguradora) | Dedup on re-extraction without losing data | ✓ Good — handles prompt version updates cleanly |
| Spanish domain terms in field names | Agency team reads JSON/DB directly | ✓ Good — consistent across Pydantic + SQLAlchemy + Excel headers |
| Per-page PDF classification | Image coverage ratio handles mixed PDFs correctly | ✓ Good — watermark filtering prevents false positives |
| Alembic with render_as_batch=True | SQLite ALTER TABLE limitations require batch mode | ✓ Good — auto-migrate on startup, backup before migration |
| openpyxl for Excel export | Avoids 30 MB pandas dependency for a 50-line operation | ✓ Good — lightweight, correct date/number types |
| In-memory job_store for upload API | Acceptable for single-user local use; lost on restart | ✓ Good — simple, job expiry after 1 hour |
| ThreadPoolExecutor for concurrent batch | Sync pipeline stays sync; threads handle I/O-bound API calls | ✓ Good — 3 workers default, max 10 |
| Rate limit retry inside extract_with_retry | Wraps call_extraction_api directly; 2s/4s/8s backoff + jitter | ✓ Good — handles 429, 5xx, connection errors |
| Sonnet evaluation opt-in only | 20x cost of Haiku; never in default extraction path | ✓ Good — --evaluate flag on CLI, evaluate=true on API |
| PII-redacted golden fixtures | Real PDFs gitignored, JSON fixtures with [REDACTED] committed | ✓ Good — regression tests work locally, CI-safe |

## Current Milestone: v2.0 Web UI & Extraction Quality

**Goal:** Add browser-based interface for PDF upload, extraction review/editing, reporting, and improve extraction quality with validation, prompt improvements, and expanded test coverage.

**Target features:**
- Web UI (upload, view, edit, dashboard)
- PDF report generation with per-insurer templates
- Extraction quality improvements (prompt, validation, auto-OCR fallback)
- Human-in-the-loop review workflow
- Expanded golden dataset and auto-evaluation

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-21 after Phase 14 completion*
