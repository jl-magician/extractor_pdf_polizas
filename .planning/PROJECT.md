# Extractor PDF Polizas

## What This Is

Sistema de extraccion inteligente de informacion de polizas de seguros en formato PDF. Utiliza IA (Claude API con Haiku) para interpretar y extraer datos estructurados de polizas provenientes de ~10 aseguradoras diferentes, cada una con 5-7 tipos de seguros (~50-70 estructuras de PDF distintas). Incluye CLI completo (`poliza-extractor`), base de datos SQLite, API REST (FastAPI), y procesamiento por lotes con seguimiento de costos.

## Core Value

Extraer automaticamente toda la informacion posible de cualquier poliza de seguro en PDF — sin importar la aseguradora o estructura — y almacenarla de forma estructurada para consulta, reporteo e integracion con otros sistemas.

## Current Milestone: v1.1 API & Quality

**Goal:** Make the extraction pipeline integratable via HTTP, improve extraction quality with automated evaluation, and add throughput/export capabilities.

**Target features:**
- PDF Upload API — POST a PDF, get structured extraction back
- Async/concurrent batch processing
- Golden dataset regression suite
- Sonnet quality evaluator for Haiku extractions
- Alembic migrations for schema evolution
- Excel export from stored polizas

## Current State (v1.0 shipped 2026-03-19)

- **Python LOC:** 5,161 across 96 files
- **Tech stack:** Python 3.11+, Pydantic v2, SQLAlchemy 2.0, PyMuPDF, ocrmypdf, Anthropic SDK, Typer, Rich, FastAPI
- **Tests:** 183 passing, 2 skipped (Tesseract-dependent)
- **CLI:** `poliza-extractor` with extract, batch, export, import-json, serve subcommands
- **API:** FastAPI CRUD at localhost:8000 with Swagger docs
- **Database:** SQLite with polizas, asegurados, coberturas, ingestion_cache tables

## Requirements

### Validated

- ✓ Extraccion de datos de PDFs de polizas usando Claude API (texto digital y escaneados con OCR) — v1.0
- ✓ Soporte para PDFs en espanol e ingles — v1.0
- ✓ Extraccion flexible que se adapte a las ~50-70 estructuras diferentes sin templates fijos — v1.0
- ✓ Captura de todos los datos posibles: contratante, asegurado(s), costo, coberturas, sumas aseguradas, compania, vigencia, agente, forma de pago, deducibles, etc. — v1.0
- ✓ Manejo de multiples asegurados (personas o bienes) por poliza — v1.0
- ✓ Base de datos local para almacenar toda la informacion extraida — v1.0
- ✓ API/JSON para exponer los datos estructurados — v1.0
- ✓ Interfaz de linea de comandos para procesar PDFs individual o en lote — v1.0
- ✓ Esquema de datos dinamico que soporte campos variables por tipo de poliza/aseguradora — v1.0

### Active

- [ ] PDF Upload API endpoint for external integrations
- [ ] Async/concurrent batch processing for throughput
- [ ] Golden dataset regression suite for extraction quality
- [ ] Sonnet quality evaluator to verify Haiku extractions
- ✓ Alembic migrations for schema versioning — Validated in Phase 6: Migrations
- ✓ Excel/CSV export from stored polizas — Validated in Phase 7: Export

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

## Constraints

- **LLM Provider**: Claude API (Anthropic) — Haiku default, Sonnet configurable
- **Plataforma**: Windows 11, aplicacion local CLI + API REST
- **PDFs mixtos**: Soporta texto digital e imagenes escaneadas (OCR via ocrmypdf + Tesseract)
- **Idioma**: Soporte para espanol e ingles en los PDFs
- **Escalabilidad**: Debe manejar 200+ polizas/mes con tiempos razonables
- **Almacenamiento**: SQLite local con JSON export y FastAPI query layer

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Claude API para extraccion | Usuario ya tiene API key; Claude maneja bien documentos complejos y multilingues | ✓ Good — works with tool_use for structured output |
| IA sin templates fijos | 50-70 estructuras diferentes hacen insostenible mantener templates; IA se adapta automaticamente | ✓ Good — single-pass extraction handles variety |
| Local-first, web despues | Validar la extraccion antes de invertir en infraestructura web | ✓ Good — CLI + API delivered in v1 |
| BD + JSON/API como v1 | Base solida sobre la cual construir Excel/reportes/web despues | ✓ Good — SQLite + FastAPI CRUD operational |
| Haiku default, Sonnet configurable | Cost efficiency for 200+ policies/month; --model flag for quality upgrade | ✓ Good — configurable via Settings |
| Single-pass extraction | One API call per PDF instead of two-pass classify+extract | ✓ Good — simpler, cheaper, sufficient quality |
| Upsert by (numero_poliza, aseguradora) | Dedup on re-extraction without losing data | ✓ Good — handles prompt version updates cleanly |
| Skip Alembic for v1 | create_all() sufficient for greenfield; add when schema evolves | ✓ Good — no migration overhead in v1 |
| Spanish domain terms in field names | Agency team reads JSON/DB directly | ✓ Good — consistent across Pydantic + SQLAlchemy |
| Per-page PDF classification | Image coverage ratio handles mixed PDFs correctly | ✓ Good — watermark filtering prevents false positives |

---
*Last updated: 2026-03-19 after Phase 7 (Export) completion*
