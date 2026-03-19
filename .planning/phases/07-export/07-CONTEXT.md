# Phase 7: Export - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Excel and CSV export from stored polizas with multi-sheet workbook and correct numeric/date types. Extends the existing `export` CLI command with `--format` flag. No new query capabilities — uses existing filter infrastructure.

</domain>

<decisions>
## Implementation Decisions

### Excel workbook structure
- Three sheets: polizas, asegurados, coberturas
- Column headers use Spanish field names matching DB columns (numero_poliza, aseguradora, prima_total, etc.) — consistent with JSON export and v1.0 convention
- Asegurados and coberturas sheets include `numero_poliza` column for VLOOKUP/filtering back to parent poliza
- `campos_adicionales` (JSON overflow) expanded into individual columns using union-of-all-keys approach: scan all rows, collect every unique key, create a column for each; rows missing a key get empty cells. Applied to all three sheets.
- Auto-filter enabled on all columns, first row frozen for easier browsing

### CSV format design
- CSV exports polizas only (flat) — users needing asegurados/coberturas use Excel format
- `campos_adicionales` expanded into individual columns (same union-of-all-keys approach as Excel)
- UTF-8 with BOM encoding, comma delimiter — ensures Spanish characters display correctly in Excel on Windows

### Filter flag naming
- New formats (xlsx, csv) use Spanish flag names: `--aseguradora`, `--agente`, `--tipo`, `--desde`, `--hasta`
- Existing JSON export keeps current English flags (`--insurer`, `--from-date`, `--to-date`, `--agent`, `--type`) for backward compatibility
- `--format` flag added to existing `export` command: `json` (default), `xlsx`, `csv`
- `--output`/`-o` required for xlsx and csv formats; json can still go to stdout

### Number and date formatting
- Monetary values (prima_total, suma_asegurada, deducible) written as plain numbers with 2 decimal places, no currency symbol — SUM works out of the box, moneda column indicates currency
- Date columns (fecha_emision, inicio_vigencia, fin_vigencia) formatted as DD/MM/YYYY (Mexican convention) — written as Excel date types so sorting/filtering works
- openpyxl for Excel generation (already decided in STATE.md — avoids 30 MB pandas dependency)

### Claude's Discretion
- Column ordering within each sheet
- openpyxl cell styling details beyond auto-filter and freeze
- Internal architecture (separate module vs inline in cli.py)
- Error handling for empty result sets
- CSV quoting strategy for fields containing commas

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing export implementation
- `policy_extractor/cli.py` lines 277-328 — Current JSON export command with filter flags, query logic, and orm_to_schema conversion
- `policy_extractor/storage/models.py` — ORM models defining all columns including campos_adicionales (JSON) on Poliza, Asegurado, Cobertura
- `policy_extractor/storage/writer.py` — `orm_to_schema()` function that converts ORM objects to Pydantic schemas

### Requirements
- `.planning/REQUIREMENTS.md` §Export — EXP-01 through EXP-05 defining multi-sheet Excel, CSV, filter flags, and numeric/date formatting

### Project decisions
- `.planning/STATE.md` §Accumulated Context — Documents openpyxl choice over pandas, Spanish domain terms convention

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `export_policies()` in `cli.py`: Existing filter logic (insurer, agent, type, date range) and ORM query with selectinload — new formats can reuse the query building
- `orm_to_schema()` in `writer.py`: Converts ORM → Pydantic schema → dict; already used for JSON export
- `SessionLocal` and `_setup_db()`: Database session pattern used by all CLI commands

### Established Patterns
- Typer CLI with Rich console for output
- Lazy imports inside command functions
- `_setup_db()` called at start of each command (handles auto-migration)
- Filter options defined as `typer.Option(None, ...)` with Optional types

### Integration Points
- `export` command in `cli.py` — extend with `--format` flag and new format handlers
- `pyproject.toml` — add openpyxl dependency
- Existing test patterns in `tests/test_cli.py` — extend with export format tests

</code_context>

<specifics>
## Specific Ideas

- Agency team primarily uses Excel on Windows — BOM encoding and DD/MM/YYYY date format are critical for their workflow
- campos_adicionales expansion is important because different insurers store different extra fields (deducible_umas, copago, vigencia_km, etc.) and the team needs to see all of them as proper columns

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-export*
*Context gathered: 2026-03-19*
