# Extractor PDF Polizas

## What This Is

Sistema de extraccion inteligente de informacion de polizas de seguros en formato PDF. Utiliza IA (Claude API con Haiku) para interpretar y extraer datos estructurados de polizas provenientes de ~10 aseguradoras diferentes, cada una con 5-7 tipos de seguros (~50-70 estructuras de PDF distintas). Incluye CLI completo (`poliza-extractor`), base de datos SQLite con migraciones Alembic, API REST (FastAPI) con upload de PDFs, procesamiento concurrente por lotes, evaluacion de calidad con Sonnet, y suite de regresion con fixtures doradas.

## Core Value

Extraer automaticamente toda la informacion posible de cualquier poliza de seguro en PDF — sin importar la aseguradora o estructura — y almacenarla de forma estructurada para consulta, reporteo e integracion con otros sistemas.

## Current State (v1.1 shipped 2026-03-19)

- **Python LOC:** 3,565 (app) + 5,820 (tests) = 9,385 total
- **Tech stack:** Python 3.11+, Pydantic v2, SQLAlchemy 2.0, Alembic, PyMuPDF, ocrmypdf, Anthropic SDK, Typer, Rich, FastAPI, openpyxl
- **Tests:** 263 passing, 3 skipped (2 Tesseract-dependent, 1 regression fixture)
- **CLI:** `poliza-extractor` with extract, batch, export, import-json, serve, create-fixture subcommands
- **API:** FastAPI CRUD + PDF upload endpoint at localhost:8000 with Swagger docs
- **Database:** SQLite with WAL mode, Alembic migrations, polizas (with evaluation columns), asegurados, coberturas, ingestion_cache tables
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

(No active requirements — next milestone needs `/gsd:new-milestone`)

### Out of Scope

- Generacion de reportes PDF — v2.0, requiere web UI
- Interfaz web — v2.0, primero se solidifica el backend
- Aplicacion movil — fuera de alcance por ahora
- Edicion manual de datos extraidos en UI — v2.0, requiere web UI
- Integracion directa con sistemas de aseguradoras — fuera de alcance

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

---
*Last updated: 2026-03-19 after v1.1 milestone completion*
