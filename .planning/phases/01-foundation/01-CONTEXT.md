# Phase 1: Foundation - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the non-retrofittable data contracts before any extraction code is written: Pydantic schemas for all extracted fields, SQLite database schema with relational tables, canonical format definitions, project scaffolding with Python package structure. No LLM calls, no API costs — pure data modeling and project setup.

</domain>

<decisions>
## Implementation Decisions

### Insured parties model
- A single policy can have BOTH persons and assets insured simultaneously (e.g., auto policy lists driver + vehicle)
- **Person attributes:** nombre completo, edad/fecha de nacimiento, RFC, CURP, dirección, parentesco con contratante
- **Asset types:** vehículos (marca, modelo, año, placas, VIN), inmuebles (dirección, tipo construcción, m2), otros bienes (descripción, número de serie, valor)
- Model as a single `asegurados` table with a `tipo` discriminator column (persona/bien) — shared fields (nombre/descripción) plus type-specific fields in JSON overflow column on the asegurado record itself
- No equipment/machinery type needed — only vehículos, inmuebles, and "otro"

### Coverage structure
- Core fields per coverage: nombre de cobertura, suma asegurada, deducible
- Some insurers add extra fields (coaseguro, copago, prima individual, periodo de espera) but this is NOT the norm — handle via JSON overflow on coverage record
- Typical range: 5-20 coverages per policy
- Model as a `coberturas` table (one-to-many from policy) with core typed columns + JSON overflow for insurer-specific extras

### Core vs overflow fields
- **Core typed columns (filterable):** número de póliza, aseguradora, tipo de seguro, fecha de emisión, inicio de vigencia, fin de vigencia, nombre del agente, nombre del contratante, prima total
- **Also core but less filtered:** forma de pago, frecuencia de pago, moneda
- **JSON overflow (informativo, no filtrable):** VIN, placas, m2, tipo de construcción, RFC del contratante, datos específicos por tipo de seguro — these are captured but stored in a JSON column since they vary wildly by insurer/type
- ALL fields selected for filtering → proper indexed columns

### Project conventions
- Package name: `policy_extractor`
- Code language: English (variables, functions, class names)
- Domain terms: **Spanish** — `contratante`, `asegurado`, `cobertura`, `vigencia`, `prima`, `deducible` kept in Spanish for field names in Pydantic models and database columns. This ensures output JSON/data is readable by the agency team.
- Comments: English
- Directory structure: Claude's discretion following Python best practices

### Claude's Discretion
- Exact directory/module structure within `policy_extractor/`
- SQLAlchemy model naming conventions
- Migration strategy (Alembic or manual for v1)
- Test framework choice
- Development tooling (linting, formatting)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Research findings
- `.planning/research/STACK.md` — Verified library versions and rationale for each technology choice
- `.planning/research/ARCHITECTURE.md` — Component boundaries, data flow, and recommended build order
- `.planning/research/PITFALLS.md` — Non-retrofittable schema pitfalls that Phase 1 must prevent (flat schema, date/currency inconsistency, missing provenance)
- `.planning/research/SUMMARY.md` — Executive summary with critical pitfalls and phase implications

### Project scope
- `.planning/REQUIREMENTS.md` — DATA-01 through DATA-05 are the requirements for this phase
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 criteria that must be TRUE)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None — patterns will be established in this phase

### Integration Points
- Pydantic schemas defined here become the contract for Phase 2 (ingestion) and Phase 3 (extraction)
- SQLAlchemy models defined here are used by Phase 5 (storage/API)
- The `asegurados` and `coberturas` table schemas must support the variety described in the decisions above

</code_context>

<specifics>
## Specific Ideas

- Domain terms in Spanish throughout the data layer — the agency team needs to read JSON output and database fields without translation
- Insured parties model must handle the real-world case of a car insurance policy listing both the driver (persona) and vehicle (bien) as separate asegurado records on the same policy
- Coverage overflow for insurer-specific extras should be per-coverage-record, not a single blob on the policy

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-18*
