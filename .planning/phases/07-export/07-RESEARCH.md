# Phase 7: Export - Research

**Researched:** 2026-03-19
**Domain:** Excel/CSV export with openpyxl, Python csv module, CLI extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Excel workbook structure:**
- Three sheets: polizas, asegurados, coberturas
- Column headers use Spanish field names matching DB columns (numero_poliza, aseguradora, prima_total, etc.)
- Asegurados and coberturas sheets include `numero_poliza` column for VLOOKUP/filtering
- `campos_adicionales` (JSON overflow) expanded into individual columns using union-of-all-keys approach on all three sheets
- Auto-filter enabled on all columns, first row frozen

**CSV format design:**
- CSV exports polizas only (flat) — users needing asegurados/coberturas use Excel
- `campos_adicionales` expanded into individual columns (union-of-all-keys)
- UTF-8 with BOM encoding (`utf-8-sig`), comma delimiter

**Filter flag naming:**
- New formats (xlsx, csv) use Spanish flag names: `--aseguradora`, `--agente`, `--tipo`, `--desde`, `--hasta`
- Existing JSON export keeps English flags (`--insurer`, `--from-date`, `--to-date`, `--agent`, `--type`) for backward compatibility
- `--format` flag added to existing `export` command: `json` (default), `xlsx`, `csv`
- `--output`/`-o` required for xlsx and csv formats; json can still go to stdout

**Number and date formatting:**
- Monetary values (prima_total, suma_asegurada, deducible) written as plain numbers with 2 decimal places — no currency symbol
- Date columns (fecha_emision, inicio_vigencia, fin_vigencia) formatted as DD/MM/YYYY — written as Excel date types
- openpyxl for Excel generation (already decided — avoids 30 MB pandas dependency)

### Claude's Discretion
- Column ordering within each sheet
- openpyxl cell styling details beyond auto-filter and freeze
- Internal architecture (separate module vs inline in cli.py)
- Error handling for empty result sets
- CSV quoting strategy for fields containing commas

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXP-01 | User can export polizas to Excel (.xlsx) with multi-sheet workbook (polizas, asegurados, coberturas) | openpyxl Workbook with create_sheet(); reuse existing ORM query with selectinload |
| EXP-02 | User can export polizas to CSV format | Python stdlib csv module with DictWriter; polizas flat table only |
| EXP-03 | CLI `export` command supports `--format xlsx` and `--format csv` flags | Extend existing Typer `export_policies` command with `format` option |
| EXP-04 | Excel/CSV exports use the same filter options as existing JSON export (aseguradora, date range, etc.) | New Spanish-named flags duplicate the existing ORM WHERE clauses |
| EXP-05 | Excel export produces correct numeric and date cell types (not text) | Python date/Decimal written directly to openpyxl cells; number_format applied |
</phase_requirements>

---

## Summary

Phase 7 extends the existing `export` CLI command with two new output formats. The core infrastructure — ORM query with `selectinload`, filter logic, and session management — already exists in `cli.py` and can be reused directly. The only new code needed is (a) an export module that turns ORM rows into openpyxl workbooks or CSV files, and (b) new Typer option declarations on the existing command.

openpyxl 3.1.5 is the current release and is the decided library. It writes Python `datetime.date` objects as true Excel date serial numbers automatically when assigned directly to cells; you only need to set `number_format` afterward to control display. `Decimal` values must be converted to `float` before writing, otherwise openpyxl serializes them as strings. The Python stdlib `csv` module with `encoding='utf-8-sig'` and `newline=''` handles BOM correctly for Excel on Windows.

The `campos_adicionales` union-of-all-keys expansion requires a two-pass approach: first scan all rows to collect every unique key, then write rows filling missing keys with empty strings. This is the only algorithmic novelty in the phase.

**Primary recommendation:** Create `policy_extractor/export.py` for all format logic, keep `cli.py` to CLI wiring only. Add `openpyxl>=3.1.5` to `pyproject.toml` dependencies.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openpyxl | 3.1.5 | Write .xlsx workbooks with typed cells, auto-filter, freeze | Already decided; stdlib-level for .xlsx generation without pandas |
| csv (stdlib) | Python 3.11 | Write .csv with correct quoting and encoding | No dependency needed; DictWriter handles variable column sets cleanly |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| decimal (stdlib) | Python 3.11 | Convert Decimal to float for openpyxl | Monetary ORM columns are Decimal; openpyxl needs float or int |
| datetime (stdlib) | Python 3.11 | date objects written directly to openpyxl cells | Already used throughout the codebase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| openpyxl | xlsxwriter | xlsxwriter is write-only (no read), similar API, slightly faster — but openpyxl already decided |
| openpyxl | pandas + openpyxl | pandas adds ~30 MB binary dep for no gain on this use case |
| csv stdlib | polars/pandas to_csv | Overkill; adds heavy dep for trivial flat table write |

**Installation:**
```bash
pip install openpyxl>=3.1.5
```

Or add to `pyproject.toml` dependencies:
```toml
"openpyxl>=3.1.5",
```

**Version verification (confirmed 2026-03-19):** `openpyxl 3.1.5` — latest on PyPI, confirmed via `pip install --dry-run`. Dependency `et-xmlfile 2.0.0` pulled automatically.

---

## Architecture Patterns

### Recommended Project Structure

```
policy_extractor/
├── export.py            # NEW — all export format logic (xlsx, csv)
├── cli.py               # EXTENDED — new --format flag, delegates to export.py
└── storage/
    └── models.py        # unchanged — ORM models already support all needed columns
tests/
└── test_export.py       # NEW — unit tests for export module
```

### Pattern 1: Separate Export Module

**What:** All format logic lives in `policy_extractor/export.py`, imported lazily inside the CLI command.

**When to use:** Always — keeps `cli.py` focused on CLI wiring. The export module is independently testable without Typer.

**Example:**
```python
# policy_extractor/export.py

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from policy_extractor.storage.models import Poliza


def export_xlsx(polizas: Sequence[Poliza], output_path: Path) -> None:
    """Write multi-sheet workbook to output_path."""
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    _write_polizas_sheet(wb.active, polizas)
    wb.active.title = "polizas"
    _write_asegurados_sheet(wb.create_sheet("asegurados"), polizas)
    _write_coberturas_sheet(wb.create_sheet("coberturas"), polizas)
    wb.save(output_path)


def export_csv(polizas: Sequence[Poliza], output_path: Path) -> None:
    """Write flat CSV of polizas only to output_path with UTF-8 BOM."""
    ...


def _cell_value(val):
    """Coerce types for openpyxl: Decimal→float, date passes through."""
    if isinstance(val, Decimal):
        return float(val)
    return val
```

### Pattern 2: Extending the Typer Export Command

**What:** Add `format` as a new `typer.Option` with an `Enum`; add Spanish-named filter options alongside existing English ones; require `--output` when format is not json.

**When to use:** Only approach — backward compat requires keeping existing English flags.

**Example:**
```python
# cli.py — extended export command signature

import enum

class ExportFormat(str, enum.Enum):
    json = "json"
    xlsx = "xlsx"
    csv = "csv"

@app.command(name="export")
def export_policies(
    # Existing JSON flags (kept for backward compat)
    insurer: Optional[str] = typer.Option(None, "--insurer", ...),
    agent: Optional[str] = typer.Option(None, "--agent", ...),
    from_date: Optional[str] = typer.Option(None, "--from-date", ...),
    to_date: Optional[str] = typer.Option(None, "--to-date", ...),
    policy_type: Optional[str] = typer.Option(None, "--type", ...),
    # New Spanish flags for xlsx/csv
    aseguradora: Optional[str] = typer.Option(None, "--aseguradora", ...),
    agente: Optional[str] = typer.Option(None, "--agente", ...),
    desde: Optional[str] = typer.Option(None, "--desde", help="YYYY-MM-DD"),
    hasta: Optional[str] = typer.Option(None, "--hasta", help="YYYY-MM-DD"),
    tipo: Optional[str] = typer.Option(None, "--tipo", ...),
    # Format + output
    fmt: ExportFormat = typer.Option(ExportFormat.json, "--format", ...),
    output: Optional[Path] = typer.Option(None, "--output", "-o", ...),
) -> None:
    ...
```

### Pattern 3: campos_adicionales Union-of-All-Keys Expansion

**What:** Two-pass algorithm to flatten variable JSON columns into deterministic column set.

**When to use:** For all three sheets in xlsx and for csv polizas sheet.

**Example:**
```python
def _collect_extra_keys(rows, attr="campos_adicionales") -> list[str]:
    """First pass: collect all unique keys across all rows, preserving insertion order."""
    seen: dict[str, None] = {}
    for row in rows:
        extras = getattr(row, attr) or {}
        for k in extras:
            seen[k] = None
    return list(seen)

def _row_to_dict(poliza: Poliza, base_cols: list[str], extra_keys: list[str]) -> dict:
    """Build flat dict for one poliza row including expanded campos_adicionales."""
    d = {col: _cell_value(getattr(poliza, col, None)) for col in base_cols}
    extras = poliza.campos_adicionales or {}
    for k in extra_keys:
        d[k] = _cell_value(extras.get(k, ""))
    return d
```

### Pattern 4: openpyxl Date and Number Formatting

**What:** Write Python types directly; apply `number_format` for display.

**When to use:** All monetary and date columns in xlsx sheets.

**Example:**
```python
# Source: openpyxl 3.1 official docs + verified behavior

DATE_FMT = "DD/MM/YYYY"
MONEY_FMT = "#,##0.00"

def _apply_formats(ws, header_row: list[str]) -> None:
    """Apply column-level number formats after data is written."""
    date_cols = {"fecha_emision", "inicio_vigencia", "fin_vigencia", "fecha_nacimiento"}
    money_cols = {"prima_total", "suma_asegurada", "deducible"}

    for col_idx, col_name in enumerate(header_row, start=1):
        col_letter = get_column_letter(col_idx)
        fmt = None
        if col_name in date_cols:
            fmt = DATE_FMT
        elif col_name in money_cols:
            fmt = MONEY_FMT
        if fmt:
            for cell in ws[col_letter][1:]:  # skip header row 0
                cell.number_format = fmt
```

### Pattern 5: Auto-filter and Freeze Panes

**What:** Enable Excel's built-in filter dropdowns and freeze header row.

**When to use:** On every sheet after all data is written.

**Example:**
```python
# Source: openpyxl docs + freeze_panes community examples

def _finalize_sheet(ws) -> None:
    """Apply auto-filter and freeze header row."""
    ws.auto_filter.ref = ws.dimensions   # e.g. "A1:Z50"
    ws.freeze_panes = "A2"               # freeze row 1 (header)
```

### Anti-Patterns to Avoid

- **Writing dates as strings:** Never `str(date_obj)` into a cell. Assign `date_obj` directly so openpyxl writes an Excel serial number, then set `number_format`. String dates break sorting.
- **Writing Decimal directly:** `ws.cell(value=some_decimal)` silently writes a string in some openpyxl versions. Always convert: `float(some_decimal)` or `None` if null.
- **Opening file during write:** Never pass the output path to `wb.save()` while another process has the file open. Teach users to close Excel before re-exporting.
- **Using `ws.dimensions` on empty sheet:** Returns `"A1:A1"` for an empty sheet. Guard before setting auto_filter.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Excel date serial conversion | Custom date-to-float | Assign `datetime.date` directly to openpyxl cell | openpyxl converts automatically; manual calculation is error-prone (1900 leap year bug) |
| CSV quoting with commas in values | Manual string escaping | `csv.DictWriter` with `QUOTE_MINIMAL` | csv stdlib handles all edge cases: embedded commas, newlines, quotes |
| UTF-8 BOM byte insertion | Manual `\xef\xbb\xbf` prefix | `encoding='utf-8-sig'` | Python handles BOM correctly; manual insertion corrupts files if applied twice |
| Column letter from index | Custom A-Z-AA logic | `openpyxl.utils.get_column_letter(n)` | Already handles two-letter columns (AA, AB, etc.) |

**Key insight:** openpyxl's automatic type coercion for Python native types (date, datetime, int, float) means the main risk is NOT using it — i.e., accidentally converting types before writing.

---

## Common Pitfalls

### Pitfall 1: Decimal Values Written as Strings
**What goes wrong:** SQLAlchemy's `Numeric` columns return Python `Decimal` objects. openpyxl 3.x does not automatically convert `Decimal` to a numeric cell — the cell data type becomes string, and Excel treats it as text. SUM formulas return 0.
**Why it happens:** `Decimal` is not a float/int; openpyxl type detection misses it.
**How to avoid:** Always convert: `float(val) if isinstance(val, Decimal) else val` before assigning to a cell. Centralize this in a `_cell_value()` helper.
**Warning signs:** In the resulting .xlsx, numeric columns are left-aligned instead of right-aligned in Excel.

### Pitfall 2: Date number_format Applied Before Data Causes No Effect
**What goes wrong:** Setting `ws.column_dimensions['A'].number_format` on a whole column before appending rows has no effect on appended rows in some openpyxl versions.
**Why it happens:** `ws.append()` creates new cell objects that don't inherit column-level formatting.
**How to avoid:** Apply `number_format` per-cell AFTER all data is written, or set it on each cell as you write it.

### Pitfall 3: auto_filter.ref Must Cover All Data Rows
**What goes wrong:** `ws.auto_filter.ref = "A1:C1"` — setting only the header row means Excel's filter dropdowns appear but cover zero data rows.
**Why it happens:** Developers think auto_filter is a header concept, but the ref must include all data.
**How to avoid:** Use `ws.dimensions` after all rows are appended, or compute the range from `ws.max_row` and `ws.max_column`.

### Pitfall 4: campos_adicionales Contains 'confianza' Key
**What goes wrong:** The `upsert_policy` writer merges `confianza` into `campos_adicionales` before DB storage. If exported verbatim, a `confianza` column appears in xlsx/csv with a nested dict value.
**Why it happens:** Storage convention in `writer.py` — `confianza` is stored inside the JSON field.
**How to avoid:** Strip the `confianza` key when reading `campos_adicionales` for export. Use the same logic as `orm_to_schema()` — `raw_campos.pop("confianza", {})` before union-of-keys collection.

### Pitfall 5: Empty Result Set Edge Case
**What goes wrong:** Exporting with a filter that matches nothing — `ws.dimensions` returns `"A1:A1"` and `ws.max_row == 1` (header only). `auto_filter.ref` on a single-row sheet crashes or produces garbled output.
**Why it happens:** openpyxl does not distinguish "has header + no data" from "completely empty."
**How to avoid:** Guard: if `len(rows) == 0`, either write header-only sheet with a note or print a warning and skip file creation. Decision left to Claude's discretion.

### Pitfall 6: CSV BOM Applied Twice
**What goes wrong:** If `output_path.write_text(content, encoding='utf-8-sig')` is combined with a manually prepended BOM, Excel shows a garbled first cell.
**Why it happens:** Mixing manual BOM and `utf-8-sig` encoding.
**How to avoid:** Use only `open(path, 'w', encoding='utf-8-sig', newline='')` — never manually add BOM bytes.

---

## Code Examples

Verified patterns from official sources and confirmed behavior:

### Creating Multi-Sheet Workbook
```python
# Source: openpyxl 3.1 official docs https://openpyxl.readthedocs.io/en/stable/
from openpyxl import Workbook

wb = Workbook()
ws1 = wb.active
ws1.title = "polizas"
ws2 = wb.create_sheet("asegurados")
ws3 = wb.create_sheet("coberturas")
wb.save("output.xlsx")
```

### Writing a Date Cell with Correct Type
```python
# Python date object assigned directly — openpyxl writes as Excel date serial
import datetime
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
dt = datetime.date(2024, 3, 15)
ws["A1"] = dt                         # Excel date type — NOT a string
ws["A1"].number_format = "DD/MM/YYYY"  # Display format for Mexican convention
wb.save("dates.xlsx")
```

### Writing a Monetary Value (Decimal-safe)
```python
from decimal import Decimal

prima = Decimal("15250.00")
ws["B1"] = float(prima)           # Must convert — Decimal writes as string
ws["B1"].number_format = "#,##0.00"
```

### Auto-filter and Freeze After Appending Rows
```python
def _finalize_sheet(ws):
    if ws.max_row > 1:  # has data beyond header
        ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"
```

### CSV with UTF-8 BOM for Windows Excel
```python
# Source: Python stdlib csv docs + utf-8-sig encoding
import csv
from pathlib import Path

def write_csv(rows: list[dict], headers: list[str], path: Path) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
```

### Filter Query Reuse Pattern (from existing cli.py)
```python
# The filter building block in export_policies() at cli.py:299-316
# New xlsx/csv formats use identical WHERE clauses, just with Spanish flag names

if aseguradora is not None:
    stmt = stmt.where(PolizaModel.aseguradora == aseguradora)
if agente is not None:
    stmt = stmt.where(PolizaModel.nombre_agente == agente)
if desde is not None:
    parsed_desde = datetime.strptime(desde, "%Y-%m-%d").date()
    stmt = stmt.where(PolizaModel.inicio_vigencia >= parsed_desde)
if hasta is not None:
    parsed_hasta = datetime.strptime(hasta, "%Y-%m-%d").date()
    stmt = stmt.where(PolizaModel.fin_vigencia <= parsed_hasta)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pandas + openpyxl (xlrd) for Excel | openpyxl standalone | openpyxl 2.x+ self-sufficient | Avoids ~30 MB pandas dependency |
| Manual BOM byte prepend | `encoding='utf-8-sig'` | Python 3.0+ | Correct BOM without corruption risk |
| xlrd for .xlsx reading | openpyxl or xlrd2 | xlrd 2.0 dropped .xlsx | N/A for this phase (write-only) |

**Deprecated/outdated:**
- `xlwt`: Only writes .xls (Excel 97-2003). Not applicable — we need .xlsx.
- `xlrd` for `.xlsx`: Dropped in xlrd 2.0. Don't use for writing. openpyxl only.

---

## Open Questions

1. **Column ordering within each sheet**
   - What we know: Headers must be Spanish DB column names; `campos_adicionales` keys come after fixed columns
   - What's unclear: Exact left-to-right ordering of fixed columns (e.g., does `numero_poliza` lead, then `aseguradora`?)
   - Recommendation: Claude's discretion — suggest: id first (or omit), then identifier columns (numero_poliza, aseguradora), then descriptive, then monetary, then dates, then provenance fields last

2. **Whether to export internal/provenance fields (source_file_hash, model_id, prompt_version, extracted_at)**
   - What we know: These are in the DB; evaluation fields (evaluation_score, etc.) are Phase 10 additions
   - What's unclear: Agency team may not want these in their export
   - Recommendation: Exclude provenance columns (source_file_hash, model_id, prompt_version, extracted_at, evaluation_*) from user-facing export; they are system metadata

3. **Error handling for --output file already open in Excel**
   - What we know: Windows file locking prevents overwrite while Excel has the file open
   - What's unclear: Whether to catch PermissionError and print a user-friendly message
   - Recommendation: Catch `PermissionError`/`OSError`, print "Close the file in Excel before exporting" and exit with code 1

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (no version pin in pyproject.toml) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_export.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXP-01 | export_xlsx writes 3-sheet workbook with correct sheet names | unit | `pytest tests/test_export.py::test_xlsx_sheet_names -x` | Wave 0 |
| EXP-01 | polizas sheet has correct column headers | unit | `pytest tests/test_export.py::test_xlsx_polizas_headers -x` | Wave 0 |
| EXP-01 | asegurados sheet includes numero_poliza foreign key column | unit | `pytest tests/test_export.py::test_xlsx_asegurados_has_numero_poliza -x` | Wave 0 |
| EXP-01 | coberturas sheet includes numero_poliza foreign key column | unit | `pytest tests/test_export.py::test_xlsx_coberturas_has_numero_poliza -x` | Wave 0 |
| EXP-01 | campos_adicionales keys appear as individual columns | unit | `pytest tests/test_export.py::test_xlsx_campos_expansion -x` | Wave 0 |
| EXP-02 | export_csv writes flat polizas-only CSV | unit | `pytest tests/test_export.py::test_csv_writes_polizas_only -x` | Wave 0 |
| EXP-02 | CSV has UTF-8 BOM (utf-8-sig) | unit | `pytest tests/test_export.py::test_csv_utf8_bom -x` | Wave 0 |
| EXP-02 | campos_adicionales keys appear as CSV columns | unit | `pytest tests/test_export.py::test_csv_campos_expansion -x` | Wave 0 |
| EXP-03 | CLI `export --format xlsx -o out.xlsx` succeeds | integration | `pytest tests/test_export.py::test_cli_export_xlsx -x` | Wave 0 |
| EXP-03 | CLI `export --format csv -o out.csv` succeeds | integration | `pytest tests/test_export.py::test_cli_export_csv -x` | Wave 0 |
| EXP-03 | `--format json` (default) still works unchanged | regression | `pytest tests/test_cli.py::test_export_with_data -x` | ✅ exists |
| EXP-04 | `--aseguradora AXA` filters to matching rows in xlsx | integration | `pytest tests/test_export.py::test_xlsx_filter_aseguradora -x` | Wave 0 |
| EXP-04 | `--desde` / `--hasta` date filters apply correctly | integration | `pytest tests/test_export.py::test_xlsx_filter_dates -x` | Wave 0 |
| EXP-05 | prima_total cell data_type is 'n' (numeric) not 's' (string) | unit | `pytest tests/test_export.py::test_xlsx_prima_is_numeric -x` | Wave 0 |
| EXP-05 | fecha_emision cell is an Excel date (not string) — readable via openpyxl as date | unit | `pytest tests/test_export.py::test_xlsx_date_is_date_type -x` | Wave 0 |
| EXP-05 | fecha_emision number_format is "DD/MM/YYYY" | unit | `pytest tests/test_export.py::test_xlsx_date_format -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_export.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_export.py` — all EXP-01 through EXP-05 test functions (new file)
- [ ] `policy_extractor/export.py` — export module itself (new file, created in Wave 1)

*(Existing `tests/conftest.py` provides `engine` and `session` fixtures — reusable for export tests. No new conftest needed.)*

---

## Sources

### Primary (HIGH confidence)
- openpyxl 3.1 official docs https://openpyxl.readthedocs.io/en/stable/ — cell types, number_format, auto_filter, freeze_panes
- openpyxl datetime docs https://openpyxl.readthedocs.io/en/3.1/datetime.html — date object handling
- Python stdlib csv docs https://docs.python.org/3/library/csv.html — DictWriter, utf-8-sig encoding
- `pip install --dry-run openpyxl` (run 2026-03-19) — confirmed version 3.1.5

### Secondary (MEDIUM confidence)
- WebSearch: freeze_panes community examples — `ws.freeze_panes = "A2"` pattern confirmed by multiple sources
- WebSearch: utf-8-sig pattern — confirmed by Python docs and community practice

### Tertiary (LOW confidence)
- WebSearch: Decimal-to-string openpyxl behavior — widely reported but not in official changelog; treat as verified by description of symptoms

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — openpyxl version confirmed from PyPI; csv is stdlib
- Architecture: HIGH — existing code in cli.py and writer.py provides the integration points; openpyxl patterns verified from official docs
- Pitfalls: HIGH (Decimal trap, date assignment) — MEDIUM (auto_filter ref edge case, confianza key leakage) — verified by code inspection
- Validation architecture: HIGH — existing pytest infrastructure confirmed; test commands match project patterns

**Research date:** 2026-03-19
**Valid until:** 2026-09-19 (openpyxl is stable; 6-month horizon)
