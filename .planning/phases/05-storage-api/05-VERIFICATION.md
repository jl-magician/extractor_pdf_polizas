---
phase: 05-storage-api
verified: 2026-03-18T00:00:00Z
status: passed
score: 16/16 must-haves verified
gaps: []
human_verification:
  - test: "Start the FastAPI server with `poliza-extractor serve --port 8000` and confirm /docs returns Swagger UI in a browser"
    expected: "Browser opens http://127.0.0.1:8000/docs and displays the interactive Swagger UI with all routes listed"
    why_human: "uvicorn.run() blocks; cannot verify the running server programmatically in this context"
  - test: "Run `poliza-extractor export` after batch-processing real PDFs and confirm the JSON file is importable with `poliza-extractor import`"
    expected: "Round-trip produces equivalent DB state — same numero_poliza, aseguradora, asegurados, coberturas counts"
    why_human: "Requires real PDFs and a running environment; test suite covers this with in-memory DB but not with real files on disk"
---

# Phase 5: Storage & API Verification Report

**Phase Goal:** All extracted data is persisted in SQLite and queryable via both JSON export and a REST API
**Verified:** 2026-03-18
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | upsert_policy() saves a PolicyExtraction to DB and returns a Poliza ORM row | VERIFIED | `writer.py` lines 35-103: full implementation with dedup query, setattr loop, child append, commit |
| 2 | Re-upserting same (numero_poliza, aseguradora) updates the row, does not create a duplicate | VERIFIED | `writer.py` lines 49-53: filter_by dedup query; test `test_upsert_deduplicates_same_poliza` confirms count stays 1 |
| 3 | Child asegurados and coberturas are persisted and round-trip back via orm_to_schema | VERIFIED | `writer.py` lines 77-100 (persist), 123-147 (reconstruct); 3 round-trip tests pass |
| 4 | CLI extract command auto-persists to DB after successful extraction | VERIFIED | `cli.py` lines 105-110: upsert_policy called after print(policy.model_dump_json(indent=2)) |
| 5 | CLI batch command auto-persists each successful extraction to DB | VERIFIED | `cli.py` lines 211-218: same pattern inside batch loop after succeeded += 1 |
| 6 | Persistence failure in CLI logs warning to stderr but does not break JSON output | VERIFIED | `cli.py`: JSON printed BEFORE persist block; try/except catches all exceptions and prints WARN to console (stderr=True) |
| 7 | User can run poliza-extractor export and get JSON array of all policies to stdout | VERIFIED | `cli.py` lines 281-328: export_policies subcommand with selectinload + orm_to_schema + json.dumps to stdout |
| 8 | Export supports --insurer, --agent, --from-date, --to-date, --type filters | VERIFIED | `cli.py` lines 303-316: all 5 filters applied as .where() clauses |
| 9 | Export supports --output file.json to write to file instead of stdout | VERIFIED | `cli.py` lines 322-326: output path check with write_text |
| 10 | User can run poliza-extractor import to load JSON into DB | VERIFIED | `cli.py` lines 336-356: import_json subcommand reads file, handles dict-or-list, upserts each record |
| 11 | Import handles both single-object and array JSON | VERIFIED | `cli.py` line 346: `records = [data] if isinstance(data, dict) else data` |
| 12 | FastAPI GET /polizas returns JSON array with nested asegurados/coberturas | VERIFIED | `api/__init__.py` lines 87-117: selectinload for both relationships, orm_to_schema, JSONResponse |
| 13 | GET /polizas supports aseguradora, tipo_seguro, nombre_agente, desde, hasta filters | VERIFIED | `api/__init__.py` lines 103-113: all 5 filters present with correct Poliza column mappings |
| 14 | GET /polizas supports skip and limit pagination | VERIFIED | `api/__init__.py` line 114: stmt.offset(skip).limit(limit) |
| 15 | GET /polizas/{id} returns single policy with 404 for missing | VERIFIED | `api/__init__.py` lines 120-131: scalar_one_or_none + HTTPException(404) |
| 16 | FastAPI POST/PUT/DELETE /polizas all functional with correct status codes | VERIFIED | `api/__init__.py` lines 134-222: POST=201, PUT=200+404, DELETE=200+404; all 5 CRUD route tests pass |

**Score:** 16/16 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `policy_extractor/storage/writer.py` | upsert_policy() and orm_to_schema() functions | VERIFIED | 171 lines; both functions fully implemented with complete logic |
| `policy_extractor/storage/__init__.py` | Exports upsert_policy and orm_to_schema | VERIFIED | Lines 4, 15-16: both symbols exported in __all__ |
| `policy_extractor/cli.py` | Auto-persist in extract + batch; export/import/serve subcommands | VERIFIED | 373 lines; all 5 subcommands present, auto-persist wired into extract and batch |
| `policy_extractor/api/__init__.py` | FastAPI app with CRUD routes and filtering | VERIFIED | 223 lines; 5 routes, all filters, selectinload, orm_to_schema, get_db dependency |
| `tests/test_storage_writer.py` | Unit tests for writer module | VERIFIED | 304 lines (>50 required); 13 tests covering create, dedup, children, round-trip, Decimal |
| `tests/test_api.py` | TestClient tests for all CRUD and filter endpoints | VERIFIED | 327 lines (>80 required); 16 tests covering all routes, filters, pagination, 404 cases, Decimal, /docs |
| `pyproject.toml` | fastapi and uvicorn dependencies declared | VERIFIED | Lines 18-19: fastapi>=0.135.1 and uvicorn[standard]>=0.42.0 present |

---

### Key Link Verification

#### Plan 01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `storage/writer.py` | `storage/models.py` | imports Poliza, Asegurado, Cobertura | WIRED | Line 14: `from policy_extractor.storage.models import Asegurado, Cobertura, Poliza` |
| `storage/writer.py` | `schemas/poliza.py` | imports PolicyExtraction | WIRED | Line 13: `from policy_extractor.schemas.poliza import PolicyExtraction` |
| `cli.py` | `storage/writer.py` | calls upsert_policy after extraction | WIRED | Lines 107-108 (extract) and 213-214 (batch): deferred import + upsert_policy call |

#### Plan 02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `api/__init__.py` | `storage/writer.py` | imports upsert_policy and orm_to_schema | WIRED | Line 23: `from policy_extractor.storage.writer import orm_to_schema, upsert_policy` |
| `api/__init__.py` | `storage/database.py` | imports SessionLocal and init_db | WIRED | Line 21: `from policy_extractor.storage.database import SessionLocal, init_db` |
| `api/__init__.py` | `storage/models.py` | queries Poliza with selectinload | WIRED | Lines 101, 125: `selectinload(Poliza.asegurados), selectinload(Poliza.coberturas)` |
| `cli.py` | `storage/writer.py` | export uses orm_to_schema, import uses upsert_policy | WIRED | Lines 294, 342: deferred imports of orm_to_schema (export) and upsert_policy (import) |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| STOR-01 | 05-01-PLAN.md | All extracted data is persisted in a local SQLite database | SATISFIED | upsert_policy wired into both extract and batch CLI commands; writer tests confirm persistence |
| STOR-02 | 05-02-PLAN.md | User can export extracted policy data as JSON | SATISFIED | export subcommand outputs JSON array; --insurer/--agent/--type/--from-date/--to-date filters; --output file flag |
| STOR-03 | 05-02-PLAN.md | System exposes a REST API (FastAPI) for querying stored policies | SATISFIED | FastAPI app with 5 CRUD routes at /polizas; uvicorn served via `poliza-extractor serve`; /docs endpoint returns 200 |
| STOR-04 | 05-02-PLAN.md | API supports filtering by insurer, date range, agent, and policy type | SATISFIED | GET /polizas accepts aseguradora, tipo_seguro, nombre_agente, desde, hasta query params; all tested |

No orphaned requirements. All 4 STOR-* requirements are claimed by plans and verified against code.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `api/__init__.py` line 37 | `@app.on_event("startup")` — deprecated in FastAPI in favor of lifespan handlers | Info | Produces deprecation warning in test output; no functional impact |

No blockers. No stubs. No TODO/FIXME comments in phase-5 files. No empty implementations.

---

### Test Suite Results

```
153 passed, 2 skipped, 34 warnings in 2.17s
```

- `tests/test_storage_writer.py` — 13 passed (writer create, dedup, children, Decimal, round-trip)
- `tests/test_api.py` — 16 passed (all CRUD, filters, pagination, 404 cases, Decimal, /docs)
- `tests/test_cli.py` — 20 passed (12 existing + 8 new export/import/serve tests)
- All prior-phase tests — 104 passed, 2 skipped (Tesseract OCR tests skipped, not failures)

Commits documented in SUMMARY match actual git log exactly:
- `5a5ffd9` — feat(05-01): writer module
- `973b80c` — feat(05-01): CLI auto-persist
- `1f31465` — test(05-02): RED for export/import/serve
- `b5bd55b` — feat(05-02): export/import/serve CLI subcommands
- `9b6fa60` — test(05-02): RED for FastAPI CRUD
- `36ec20f` — feat(05-02): FastAPI CRUD endpoints

---

### Human Verification Required

#### 1. Uvicorn Server Starts and Serves /docs

**Test:** Run `poliza-extractor serve --port 8000` in a terminal, then navigate to http://127.0.0.1:8000/docs in a browser.
**Expected:** Swagger UI loads, listing GET /polizas, GET /polizas/{id}, POST /polizas, PUT /polizas/{id}, DELETE /polizas/{id}.
**Why human:** uvicorn.run() is a blocking call; the test suite verifies /docs via TestClient (which does not start a real HTTP server). Real network behavior cannot be confirmed programmatically.

#### 2. End-to-End Extraction to DB Retrieval

**Test:** Run `poliza-extractor extract <real_pdf>`, then immediately run `poliza-extractor export`. Confirm the extracted policy appears in the JSON output.
**Expected:** The exported JSON array contains one entry matching the extraction output, including nested asegurados and coberturas.
**Why human:** Requires real PDF files and a valid Claude API key; integration across the full pipeline cannot be verified without live dependencies.

---

### Gaps Summary

No gaps. All 16 observable truths are verified. All artifacts are substantive and wired. All 4 STOR requirements are satisfied. The full test suite (153 tests) passes with no regressions across all 5 phases.

The only open item is the `@app.on_event("startup")` deprecation warning — this is informational and does not affect functionality or tests. It can be addressed in a future phase by migrating to the FastAPI lifespan context manager pattern.

---

_Verified: 2026-03-18_
_Verifier: Claude (gsd-verifier)_
