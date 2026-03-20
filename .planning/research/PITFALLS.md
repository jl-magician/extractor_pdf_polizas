# Pitfalls Research

**Domain:** PDF extraction pipeline — v1.1 additions (async batch, file upload API, golden dataset, Sonnet evaluator, Alembic migrations, Excel export) onto existing Python system
**Researched:** 2026-03-18 (v1.1); updated 2026-03-20 (v2.0 Web UI & Extraction Quality)
**Confidence:** HIGH (critical pitfalls verified against official docs and GitHub issues; integration pitfalls from confirmed real-world reports)

---

## v2.0 Pitfalls — Web UI, PDF Reports, Extraction Validation, Human Review

These cover adding a browser-based interface, PDF report generation, extraction validation, and human-in-the-loop review to the existing FastAPI/SQLite/CLI system. The v1.1 pitfalls below remain valid and are not repeated here.

---

### Pitfall v2-1: WeasyPrint GTK Dependencies Fail Silently on Windows 11

**What goes wrong:**
WeasyPrint requires Pango, cairo, and GDK-PixBuf (GTK+ libraries) that are not bundled with the pip package. On Windows 11, the libraries must be installed separately via MSYS2. The install appears to succeed (`pip install weasyprint` exits 0), but the first PDF render call raises `OSError: dlopen() failed to load a library: cairo` at runtime. Critically, this project already has Tesseract installed via ocrmypdf, and Tesseract ships its own conflicting GTK DLLs — the MSYS2 GTK libraries may be shadowed by Tesseract's copies if MSYS2 is not first in PATH.

**Why it happens:**
WeasyPrint's pip package cannot declare native library dependencies because pip cannot install system libraries. A known library naming mismatch (WeasyPrint looks for `gobject-2.0-0.dll` but GTK3 installs `libgobject-2.0-0.dll`) means even a correct MSYS2 install can fail without an explicit rename step. The Tesseract DLL conflict is specific to this project's existing stack and not commonly documented.

**How to avoid:**
Validate WeasyPrint on the target Windows 11 machine before writing any report template code. Test the full sequence: MSYS2 GTK install → PATH ordering (MSYS2 bin before Tesseract bin) → DLL rename if needed → `python -c "import weasyprint; weasyprint.HTML(string='<p>ok</p>').write_pdf('test.pdf')"`. If the setup is fragile after one attempt, switch to `xhtml2pdf` — a pure-Python library with no native dependencies that accepts Jinja2-generated HTML and works on Windows without any system library setup. The API is similar enough that switching costs less than debugging GTK conflicts.

**Warning signs:**
- `pip install weasyprint` succeeds but `import weasyprint` raises `OSError` mentioning cairo, pango, or gobject.
- PDF generation works in one terminal session but not another (PATH ordering issue caused by terminal startup environment).
- PDF generation breaks after Tesseract is updated (new Tesseract version ships different GTK DLLs).

**Phase to address:**
PDF report generation phase — first task. Run the Windows installation test before writing any template or generation code. Block the phase on this test passing.

---

### Pitfall v2-2: CORS Blocks All Frontend Requests Until Explicitly Configured

**What goes wrong:**
The React dev server runs on `localhost:5173` (Vite default) while FastAPI runs on `localhost:8000`. Every fetch request fails with `Access to fetch blocked by CORS policy`. The existing FastAPI app has no `CORSMiddleware`. The reflex response — `allow_origins=["*"]` — works for GET requests but breaks when combined with `allow_credentials=True`, which browsers silently reject as an invalid combination.

**Why it happens:**
FastAPI does not enable CORS by default. `localhost:5173` and `localhost:8000` are different origins by browser rules. The `["*"]` + `credentials=True` combination is rejected by the browser spec (not by FastAPI), so the server accepts the configuration while browsers refuse responses — the error only appears in the browser DevTools Network tab, not in server logs.

**How to avoid:**
Add `CORSMiddleware` as the very first task in the web UI foundation phase — before any frontend component makes an API call. Use explicit origins: `allow_origins=["http://localhost:5173"]`. Note that `http://localhost` and `http://127.0.0.1` are treated as different origins by browsers — pick one and use it consistently across all dev URLs. For this single-user local-first system, `allow_credentials=False` is correct; avoid cookies entirely. In the production deployment (React build served by FastAPI as static files), CORS disappears entirely because the frontend and API share the same origin.

**Warning signs:**
- Browser console shows `Access to fetch at '...' blocked by CORS policy` but curl/httpx to the same endpoint returns 200.
- Adding `["*"]` fixes GET but POST with any custom header still fails.
- CORSMiddleware is added but after other middleware (it must be first in the middleware stack).

**Phase to address:**
Web UI foundation phase — first task. No frontend component should attempt an API call before CORSMiddleware is confirmed working with a smoke test fetch.

---

### Pitfall v2-3: SQLite "Database is Locked" Under Concurrent Web UI Polling + Background Extraction

**What goes wrong:**
When a user uploads a PDF via the web UI, a background extraction job writes to SQLite while the UI simultaneously polls for job status and loads the poliza list. Even with WAL mode (already enabled in v1.1), SQLite serializes all writers. If the extraction worker holds a write transaction open during a slow Claude API response, a concurrent API write (e.g., status update) times out with `OperationalError: database is locked`. The v1.1 system only needed to worry about concurrent batch workers; adding a continuously polling web UI creates a new concurrent-write scenario.

**Why it happens:**
The v1.1 system correctly set WAL mode and busy_timeout for the batch extraction case. However, the web UI introduces a new pattern: persistent short-interval polling from the browser that fires API requests every 1-2 seconds while extraction is running. If any of those requests trigger a DB write (e.g., updating `job_store` to a DB table, or any status update), it competes with the extraction write.

**How to avoid:**
Keep job state in the in-memory `job_store` (already existing from v1.1) rather than persisting it to SQLite. This means polling requests (`GET /jobs/{job_id}`) never touch the database and never compete with extraction writes. Only write to SQLite once: when extraction completes successfully (single atomic write with all extracted fields). Verify `PRAGMA busy_timeout=5000` is active on all connections — this provides a 5-second retry window for the rare case where two genuine DB writes overlap.

**Warning signs:**
- `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked` appears in logs during active UI sessions with extraction running.
- UI polling requests return HTTP 500 intermittently during batch processing.
- Extraction completes successfully (Claude API returns data) but poliza never appears in the DB (write was dropped on lock error).

**Phase to address:**
Web UI foundation phase (when polling is introduced). Confirm that polling endpoints read only from in-memory `job_store`, not SQLite, before any concurrent upload + polling scenario is tested.

---

### Pitfall v2-4: LLM Field Value Swaps Are Systematic and Pass Type-Only Validation

**What goes wrong:**
As documented in `.planning/v2-extraction-errors.md`, Claude consistently swapped `financiamiento` (808.2) with `otros_servicios_contratados` (0) and `folio` with `clave` in the same Zurich auto policy. Post-extraction validation that checks only for null values, type errors, or Pydantic schema compliance will mark this extraction as "valid" while the data is systematically wrong. A validation layer without cross-field financial logic provides false confidence.

**Why it happens:**
LLMs extract adjacent table fields by proximity heuristics. When two fields share the same numeric format in a multi-column financial breakdown, the model resolves column ordering inconsistently. This is exacerbated when the extraction prompt lacks a concrete example of the financial breakdown table layout. The error pattern repeats across extractions of the same document structure, making it systematic — not noise.

**How to avoid:**
Post-extraction validation must include cross-field financial invariants, not just per-field type checks. Key invariants for Mexican auto insurance policies (validated against known error patterns):
- `primer_pago + (subsecuentes * num_pagos)` should approximate `prima_total` within ±5% tolerance.
- If `financiamiento > 0`, verify `otros_servicios_contratados` is not suspiciously zero (flag for review, do not auto-reject).
- `folio` and `clave` have distinct format patterns (folio is typically a longer numeric string; clave is shorter) — regex-validate format expectations.
- If validation fails, store the failure details alongside the extracted record so the human review UI can pre-highlight flagged fields.

Separately, improve the extraction prompt with a concrete example of a financial breakdown table showing correct field-to-value mapping (the most effective prevention). Add the Sonnet review pass specifically for `campos_adicionales` financial fields as recommended in `v2-extraction-errors.md`.

**Warning signs:**
- Validation passes (no Pydantic errors) but `prima_total` does not reconcile with `primer_pago` + `subsecuentes`.
- The same two specific fields are corrected repeatedly by the same human reviewer.
- `financiamiento` and `otros_servicios_contratados` are swapped in the majority of Zurich auto extractions.

**Phase to address:**
Extraction validation phase. Financial invariant checks must be written and tested against the known-bad fixture from `v2-extraction-errors.md` before the human review UI is built. The UI should surface pre-computed validation failures, not expect reviewers to detect swaps manually.

---

### Pitfall v2-5: Human Review Corrections Overwrite LLM Output — Feedback Loop Never Closes

**What goes wrong:**
A correction is saved via `PATCH /polizas/{id}` that updates the extracted field directly in the `polizas` table. The original LLM-extracted value is overwritten and permanently lost. No record exists of what Claude extracted vs. what the human corrected. The "feedback loop" and "system learns from corrections" capabilities described in `v2-extraction-errors.md` (section: v2 Feature Request) are architecturally impossible without this correction history. The system cannot answer "which fields are wrong most often?" or grow the golden dataset from reviewed records.

**Why it happens:**
The natural implementation is a PATCH endpoint that updates the record in place — matching the existing API pattern. It ships quickly and appears functionally correct (the corrected value is saved). The missing piece (correction history) is invisible until someone asks for the analytics or golden dataset growth capabilities.

**How to avoid:**
Design a `corrections` table before implementing any correction endpoint. Schema: `{id, poliza_id, field_name, original_value, corrected_value, corrected_at, validation_flag}`. The human review UI writes to `corrections`, not to `polizas` directly. The display layer merges `corrections` on top of `polizas` for the reviewer's view. This enables:
1. Correction frequency report (which fields are wrong most often, by insurer/document type).
2. Golden dataset growth: polizas with all fields reviewed and approved become new test fixtures.
3. Prompt improvement: patterns in correction data identify which prompt instructions to add.

Never overwrite the original LLM-extracted value in the `polizas` table. Add a Alembic migration for the `corrections` table as the first task in the human review phase.

**Warning signs:**
- Correction endpoint is `PATCH /polizas/{id}` that updates `polizas` fields directly.
- No `corrections` table in the Alembic migration history.
- Team cannot answer "which field does Claude get wrong most often?" from the database.

**Phase to address:**
Human review UI phase — schema design is the first task. The `corrections` table must exist before any correction endpoint is implemented. Retrofitting this after UI is live requires a data migration and API redesign, and all corrections made before the migration are permanently unrecoverable.

---

### Pitfall v2-6: Auto-OCR Fallback Triggers Universally Instead of Only When Needed

**What goes wrong:**
The v2 requirement adds auto-OCR fallback: if a "digital" PDF page has <10 chars extracted, reclassify as scanned and OCR it. Implemented without the conditional gate, OCR runs on every PDF page in the hot path — including pages that extracted text perfectly. Tesseract OCR via ocrmypdf adds 5-30 seconds per page. A 5-page digital policy that previously processed in 3 seconds now takes 30+ seconds. This is catastrophic for the batch workflow that processes 200+ polizas per month.

**Why it happens:**
The fallback check is added as a post-extraction processing step applied uniformly, or the threshold is miscalibrated. Developers test with the specific failing PDF (`Poliza 8650156226.pdf`) and confirm it now works, without testing that normal digital PDFs are not affected.

**How to avoid:**
The fallback is conditional on two gates:
1. Per-page gate: page classification is "digital" AND char count after `get_text()` is below threshold (10 chars). Only then trigger OCR for that page.
2. Full-document gate: if the complete extraction result has all core fields null or `<UNKNOWN>`, auto-retry the entire document through the OCR pipeline regardless of per-page classification. This catches vector-path PDFs that fool the image coverage ratio heuristic (the root cause of `Poliza 8650156226.pdf`).

Log every auto-OCR trigger with the triggering condition (`per_page_char_count=3`, `all_core_fields_null=True`) so the threshold can be tuned. Add a test that processes 5 known-digital PDFs and asserts zero OCR triggers in the logs.

**Warning signs:**
- Batch processing time doubles or triples after auto-OCR fallback is added.
- Logs show OCR triggered on PDFs with 500+ characters per page.
- Single-PDF extraction time increases from ~3 seconds to 30+ seconds consistently for all PDFs, not just the previously failing ones.

**Phase to address:**
Extraction quality improvement phase. The conditional gate and logging must be part of the implementation — not a follow-up fix. Test against both the failing PDF and a set of known-digital PDFs before the phase is complete.

---

### Pitfall v2-7: PDF Viewer Freezes the Browser Tab on Large Scanned Policies

**What goes wrong:**
The human review UI needs to display the original PDF alongside the extraction editor. PDF.js (the natural choice for a React app) renders PDF pages into canvas elements. A 31-page scanned home insurance policy (like `danPol00112212110End00000ZJZHCL.Pdf`) embeds full-resolution scanned images — approximately 2-3 MB per page as uncompressed canvas data. Rendering all 31 pages simultaneously allocates 60-90 MB of canvas memory, causing the browser tab to freeze or crash with "Aw, Snap!" on Windows 11 with typical office hardware.

**Why it happens:**
PDF.js loads and renders all pages by default. Developers test with small (3-5 page) digital PDFs during development and the performance is fine. Scanned multi-page policies are the production workload, not the development test case.

**How to avoid:**
Use the browser's native PDF viewer via `<iframe src="/api/polizas/{id}/pdf" />` instead of PDF.js. The native Chrome/Edge viewer handles large scanned PDFs with lazy page rendering and automatic memory management — zero extra code required. FastAPI serves the PDF with `FileResponse` and `Content-Type: application/pdf`; the browser handles the rest. This approach requires no npm package, no canvas memory management, and handles any PDF the browser can natively display. Reserve PDF.js only if page-level annotation or text highlighting is needed (not in scope for v2).

**Warning signs:**
- Browser tab memory usage exceeds 200 MB when opening a review for a multi-page scanned policy.
- Chrome shows "Aw, Snap!" page crash on 20+ page scanned PDFs.
- PDF.js takes more than 3 seconds to display the first page of a large scanned document.

**Phase to address:**
Human review UI phase — the PDF serving strategy must be decided before building the side-by-side layout. Test with the 31-page scanned policy fixture before declaring the review UI complete.

---

### Pitfall v2-8: Unsaved Field Corrections Lost on In-App Navigation

**What goes wrong:**
A reviewer edits 5 fields in the correction form for a poliza, then clicks the next poliza in the list. React Router performs an in-app route transition. All edits disappear without warning. The `beforeunload` browser event only fires on page refresh or browser close — not on React Router route changes — so standard browser "leave page?" guards do not protect against this.

**Why it happens:**
React Router route transitions do not trigger `beforeunload`. The in-app navigation feels like the browser navigating, but it is JavaScript updating the view — the browser has no opportunity to warn the user. Developers test by clicking "Save" carefully and never trigger the navigation-while-dirty scenario.

**How to avoid:**
Implement auto-save on field blur: each field saves its correction independently when the user leaves the input, rather than requiring a "Save All" button. This eliminates the unsaved-changes problem entirely and matches the expected UX for an inline correction tool (comparable to editing a spreadsheet cell). As a safety net for any multi-field submit forms, use React Router's `useBlocker` hook (available since React Router v6.7) to intercept route transitions when the form has unsaved changes. Show a confirmation dialog: "You have unsaved corrections. Leave without saving?"

**Warning signs:**
- "Save" button exists at the bottom of a long scrollable correction form (users miss it).
- No `useBlocker` import or `isDirty` state in the review component.
- Testers report that clicking the next poliza in the list discards their corrections silently.

**Phase to address:**
Human review UI phase. Auto-save-on-blur is the primary design decision; `useBlocker` is the guard for any form that does not auto-save.

---

### Pitfall v2-9: WeasyPrint PDF Generation Blocks the FastAPI Event Loop

**What goes wrong:**
A `POST /polizas/{id}/report` endpoint calls `weasyprint.HTML(...).write_pdf()` synchronously inside an `async def` route handler. WeasyPrint's HTML rendering + PDF layout computation takes 1-3 seconds on a typical document. During this time, FastAPI's ASGI event loop is blocked — all other in-flight requests (including UI polling calls) queue and appear frozen. The single user experiences the UI as unresponsive for several seconds during every report generation.

**Why it happens:**
`weasyprint.HTML().write_pdf()` is a synchronous CPU-bound call. Calling it directly in `async def` does not use `await`, so it runs in the event loop thread, blocking all other coroutines. This is a common FastAPI mistake with any synchronous heavy operation.

**How to avoid:**
Wrap the synchronous PDF generation call in `asyncio.get_event_loop().run_in_executor(None, generate_pdf_fn)` to run it in a thread pool, freeing the event loop for other requests:

```python
import asyncio
from functools import partial

@app.post("/polizas/{id}/report")
async def generate_report(id: int):
    loop = asyncio.get_event_loop()
    pdf_bytes = await loop.run_in_executor(None, partial(build_pdf_for_poliza, id))
    return Response(content=pdf_bytes, media_type="application/pdf")
```

Alternatively, treat report generation as a background job (return a job ID, generate asynchronously, return the PDF via `GET /jobs/{job_id}/result` when complete) — but for a single-user local system, `run_in_executor` is simpler and sufficient.

**Warning signs:**
- All API requests (including the poliza list refresh) return slowly during report generation.
- FastAPI logs show requests queuing during report endpoint calls.
- `asyncio.get_event_loop().run_in_executor` is not used anywhere in the report generation route.

**Phase to address:**
PDF report generation phase — the executor pattern must be part of the initial implementation, not a performance fix.

---

## Technical Debt Patterns — v2.0 Additions

Shortcuts specific to adding v2.0 features to the existing system.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| PATCH corrections directly to `polizas` table (no history) | Simpler API, no schema change | Cannot identify systematic LLM errors; no golden dataset growth; correction feedback loop is impossible | Never — implement `corrections` table from the start |
| `allow_origins=["*"]` CORS in development | Zero CORS errors during development | Developers forget to restrict before UAT; `credentials=True` combo silently breaks auth | Only in dev, with explicit TODO comment, and only if no credential flows exist |
| Synchronous WeasyPrint call in async route handler | No executor boilerplate | Event loop blocked 1-3 seconds per report; all requests queue during generation | Never — always use `run_in_executor` |
| Serving PDFs via `Response(content=bytes)` instead of `FileResponse` | Simple one-liner endpoint | Loads entire scanned PDF (50-150 MB) into Python memory on every viewer request | Acceptable for PDFs under 5 MB; use `FileResponse` for all others |
| Hardcoding report template HTML as Python strings | Fast to implement | Non-technical staff cannot adjust; insurer-specific customization requires code deploys | Never — use Jinja2 templates on the filesystem from day one |
| Auto-OCR fallback with no conditional gate | Fixes the zero-text PDF bug | OCR triggers on all PDFs; batch time multiplies by 10x | Never — the gate is not optional |
| PDF.js for the review viewer without virtualization | Standard npm package, familiar API | Freezes browser on 20+ page scanned policies | Acceptable for digital PDFs only; do not use without virtualization if scanned PDFs are reviewed |

---

## Integration Gotchas — v2.0 Additions

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| React frontend + FastAPI | Hardcoding `http://localhost:8000` in fetch calls | Use `VITE_API_BASE_URL` environment variable; configure once in `.env.development` |
| FastAPI static files + React Router | Mounting React build at `/` but React Router routes conflict with API routes | Mount the React build at `/app` or serve `index.html` only for paths not matching `/api/*` |
| PDF iframe viewer + FastAPI | Omitting `Content-Type: application/pdf` header on the PDF endpoint | Browsers may download instead of display; set header explicitly in `FileResponse` |
| WeasyPrint + Jinja2 templates | Using relative image `src` paths in HTML templates | WeasyPrint resolves relative paths from template file location, not server root — use absolute paths or pass `base_url` to `HTML()` |
| Correction UI + poliza API | PATCH endpoint accepts free-text for numeric fields without validation | Validate each corrected field value against the same Pydantic schema used for extraction; reject corrections that corrupt the field type |
| ocrmypdf + filenames with spaces/special chars | Passing raw path strings to `ocrmypdf.ocr()` | Use `pathlib.Path` objects throughout; the batch test failure in `v2-extraction-errors.md` (error 10) was likely caused by unquoted paths |
| Alembic + web server startup | Running Alembic auto-migrate on startup while a previous process still holds a WAL write lock | Ensure only one process runs migrations; restart the server after migration, not before |

---

## Performance Traps — v2.0 Additions

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading all polizas for dashboard statistics without SQL aggregates | Dashboard loads in 3+ seconds; Python memory spikes | Use SQL `COUNT`, `AVG`, `SUM` via SQLAlchemy aggregate queries; never load all records into Python for statistics | Around 500-1000 polizas in the DB |
| Synchronous WeasyPrint in async route | All API responses queue during report generation | `run_in_executor` for the synchronous PDF render call | Every report request — it blocks from the first one |
| Storing PDF binaries as SQLite BLOBs for the review viewer | Database file grows to gigabytes; Alembic migrations slow; backups unusable | Store PDFs on the filesystem; keep only the file path in the DB | Around 100-200 scanned PDFs (50-150 MB each) |
| Fetching full extraction JSON for every row in the poliza list | Network payload grows linearly with record count; list view slows | Return only summary fields in the list endpoint (numero_poliza, aseguradora, fecha, quality score); load full detail only when selected | Around 200-500 records |
| Triggering Sonnet re-evaluation on every human correction save | $0.20+ per correction session; 3-5 second delay per save | Sonnet evaluation is explicit-trigger only ("Re-evaluate" button or batch job), never on inline edits | Immediate — Sonnet is 20x Haiku cost |

---

## Security Mistakes — v2.0 Additions

| Mistake | Risk | Prevention |
|---------|------|------------|
| Serving PDFs at predictable `GET /polizas/{id}/pdf` without any access control | Any browser tab can fetch any poliza PDF by guessing sequential IDs | Acceptable for single-user local system; document explicitly that the API must not be exposed beyond localhost without authentication added |
| Rendering user-corrected field values directly into HTML report templates without escaping | XSS in generated HTML; if PDF is served inline, could execute in browser context | Jinja2 auto-escaping handles this by default — do not use `| safe` filter on any user-supplied field value |
| Accepting file uploads without magic-byte validation | Malicious file disguised as PDF could exploit PyMuPDF parser | Validate `%PDF-` magic bytes at offset 0 in addition to `Content-Type` header (already has MIME check; add byte check) |

---

## UX Pitfalls — v2.0 Additions

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing all 40+ extracted fields in the correction UI including nulls | Reviewer scrolls past 30 empty fields to find the 8 that need correction | Show null/empty fields collapsed; float non-null fields and validation-flagged fields to the top; expand collapsed fields on click |
| "Save All" button at the bottom of a long scrollable correction form | Reviewer edits a field at the top, scrolls to next poliza without saving, loses work | Auto-save on field blur; show a persistent "N unsaved changes" counter in the sticky header |
| No visible quality score in the poliza list | Reviewer does not know which polizas need attention | Show Sonnet quality score as a color-coded badge (green ≥0.9, yellow 0.7-0.9, red <0.7) in the list view; show validation failure count as a separate indicator |
| Upload queue showing only "Processing..." with no progress detail | Agency staff submits 20 PDFs and has no idea which succeeded or failed | Show per-file status (queued / extracting / done / failed) and elapsed time per file in the upload queue panel |
| Financial validation failures shown as generic red icons | Reviewer sees a flag but does not know what was expected | Show validation failure message with context: "prima_total (12,500) does not match primer_pago (5,000) + subsecuentes×pagos (29,956) — likely field swap" |

---

## "Looks Done But Isn't" Checklist — v2.0 Additions

- [ ] **PDF report generation:** Template renders correctly in local browser test — but verify WeasyPrint on Windows 11 with `python -c "import weasyprint; weasyprint.HTML(string='<p>test</p>').write_pdf('test.pdf')"` before any template work starts. A pytest test mocking the render call does not catch library loading failures.
- [ ] **Human review UI:** Fields are editable and corrections are saved — but verify corrections go to a `corrections` table (not overwriting `polizas` fields in place) and that the correction history is queryable as a frequency report.
- [ ] **Extraction validation:** Validation runs and returns pass/fail — but verify cross-field financial invariants are tested, not just per-field type checks. Run the known-bad fixture from `v2-extraction-errors.md` and confirm it produces a validation failure.
- [ ] **Auto-OCR fallback:** OCR triggers for `Poliza 8650156226.pdf` and extraction succeeds — but also verify that 5 known-digital PDFs process with zero OCR triggers (check logs).
- [ ] **Dashboard statistics:** Numbers display correctly — but verify they come from SQL aggregates, not Python-side iteration. Test with a database seeded to 500 records and confirm the dashboard loads under 1 second.
- [ ] **CORS configuration:** No browser errors in dev — but verify `allow_origins` is explicit (`["http://localhost:5173"]`), not `["*"]`, and that `allow_credentials=False`.
- [ ] **Unsaved changes guard:** Correction form has a save mechanism — but verify that React Router navigation away from a dirty form either triggers a confirmation dialog (`useBlocker`) or that auto-save-on-blur is active for all editable fields.
- [ ] **Event loop not blocked:** Report generation endpoint returns quickly — but verify with a concurrent request test: fire a report generation request and simultaneously fire 5 poliza list requests; all list requests should return within 200 ms.

---

## Recovery Strategies — v2.0 Additions

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| WeasyPrint GTK fails on Windows 11 | MEDIUM | Switch to `xhtml2pdf` (pure Python, no native deps) — API is similar; HTML templates need minor adjustments; 1-2 days rework at most |
| Corrections stored in-place, no history table | HIGH | Add `corrections` table via Alembic migration; original LLM values for corrected records are permanently lost for records edited before the migration; restore from golden fixtures where possible |
| "database is locked" under UI polling | LOW | Keep polling endpoints reading from in-memory `job_store` only; add `PRAGMA busy_timeout=5000` if not already set; restart app; no data loss |
| Auto-OCR fallback triggers universally | LOW | Add conditional char-count gate; deploy; processing time returns to baseline immediately; no data loss |
| PDF viewer freezes on large scanned policies | LOW | Switch to `<iframe src="...">` native viewer; remove PDF.js dependency; no data migration needed |
| Unsaved corrections lost during navigation | LOW | Implement auto-save-on-blur or `useBlocker`; no database migration needed; only in-flight user edits are unrecoverable |
| WeasyPrint blocks event loop during report generation | LOW | Wrap with `run_in_executor`; 10-minute fix; no data loss |

---

## Pitfall-to-Phase Mapping — v2.0 Additions

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| WeasyPrint GTK on Windows 11 | PDF report generation phase — first task | `python -c "import weasyprint; weasyprint.HTML(string='<p>ok</p>').write_pdf('t.pdf')"` succeeds without errors |
| CORS blocks frontend requests | Web UI foundation phase — first task | Browser DevTools shows no CORS errors; fetch from port 5173 to 8000 returns 200 |
| SQLite locked under UI polling + extraction | Web UI foundation phase (when polling is added) | Run concurrent extraction batch + UI polling for 60 seconds; zero `OperationalError` in logs |
| LLM field swaps not caught by validation | Extraction validation phase | Known-bad fixture from `v2-extraction-errors.md` triggers a validation failure; unit tests for cross-field invariants pass |
| Correction history not stored | Human review UI phase — schema design task | `corrections` table exists in Alembic migration history; API returns `original_value` and `corrected_value` per field |
| Auto-OCR fallback triggers universally | Extraction quality phase | Batch of 5 known-digital PDFs shows zero OCR triggers in logs; `Poliza 8650156226.pdf` shows OCR triggered and extraction succeeds |
| PDF viewer freezes on large scanned policy | Human review UI phase | Open review for 31-page scanned policy; browser tab memory stays below 200 MB; no freeze or crash |
| Unsaved corrections lost on navigation | Human review UI phase | Navigate away from a dirty correction form via React Router; confirmation dialog appears OR auto-save-on-blur prevents data loss |
| WeasyPrint blocks event loop | PDF report generation phase | Concurrent request test: 5 list requests return within 200 ms while a report is generating |

---

## Sources — v2.0

- FastAPI CORS official documentation: https://fastapi.tiangolo.com/tutorial/cors/
- CORS error in FastAPI from React frontend (Microsoft Q&A): https://learn.microsoft.com/en-us/answers/questions/2115649/cors-error-in-fastapi-backend-from-react-frontend
- WeasyPrint Windows 11 installation failure (GitHub Issue #2480): https://github.com/Kozea/WeasyPrint/issues/2480
- WeasyPrint GTK conflict with Tesseract (gpt-researcher issue #166): https://github.com/assafelovic/gpt-researcher/issues/166
- WeasyPrint first steps (official docs): https://doc.courtbouillon.org/weasyprint/stable/first_steps.html
- SQLite WAL mode (official docs): https://sqlite.org/wal.html
- SQLite concurrent writes and "database is locked" errors: https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/
- SQLAlchemy + FastAPI event loop blocking (GitHub Discussion #12089): https://github.com/fastapi/fastapi/discussions/12089
- Human-in-the-loop best practices and common pitfalls (Parseur): https://parseur.com/blog/hitl-best-practices
- Designing human-in-the-loop review for high-stakes scraped data (ScrapingAnt): https://scrapingant.com/blog/designing-human-in-the-loop-review-for-high-stakes-scraped
- Inline validation UX patterns: https://smart-interface-design-patterns.com/articles/inline-validation-ux/
- Smashing Magazine — complete guide to inline validation: https://www.smashingmagazine.com/2022/09/inline-validation-web-forms-ux/
- PDF.js in-browser rendering performance: https://joyfill.io/blog/optimizing-in-browser-pdf-rendering-viewing
- FastAPI static files (official docs): https://fastapi.tiangolo.com/tutorial/static-files/
- WeasyPrint vs ReportLab comparison: https://dev.to/claudeprime/generate-pdfs-in-python-weasyprint-vs-reportlab-ifi
- LLM financial table extraction challenges: https://daloopa.com/blog/analyst-best-practices/processing-tabular-financial-data-with-large-language-models
- Project-specific error patterns: `.planning/v2-extraction-errors.md`

---

## v1.1 Pitfalls (Existing — Remain Valid)

These pitfalls were identified during v1.1 research and addressed in the shipped system. They remain valid constraints for v2.0 development.

---

### Pitfall 1: UploadFile Closed Before Background Task Reads It

**What goes wrong:**
The FastAPI route handler returns a response, FastAPI/Starlette closes the `UploadFile` object, and then the background task tries to read from it — getting an empty or already-closed file. This is a deliberate behavioral change introduced in FastAPI >= 0.106.0. The extraction produces no content or raises `ValueError: I/O operation on closed file`. The background task runs to completion with empty data and writes nothing to the DB — the failure is silent unless logs are checked.

**Why it happens:**
The natural pattern is `background_tasks.add_task(process_pdf, file)` where `file` is the `UploadFile`. This worked in older FastAPI but is now broken by design. `UploadFile` wraps a temporary spooled file that Starlette owns and closes immediately after the response body is sent. The object reference passed to the background task points to a closed file descriptor.

**How to avoid:**
Read the full file bytes inside the route handler, before returning, and pass `bytes` (or a path to a saved temp file) to the background task. Never pass the `UploadFile` object itself.

```python
# WRONG — file is closed before process_pdf runs
@app.post("/upload")
async def upload(file: UploadFile, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_pdf, file)
    return {"status": "queued"}

# CORRECT — read bytes while the connection is still open
@app.post("/upload")
async def upload(file: UploadFile, background_tasks: BackgroundTasks):
    pdf_bytes = await file.read()
    original_name = file.filename
    background_tasks.add_task(process_pdf, pdf_bytes, original_name)
    return {"status": "queued", "filename": original_name}
```

**Warning signs:**
- Extraction runs but produces empty text or a `None` result
- `ValueError: I/O operation on closed file` in background task logs
- Works with small files (spooled entirely in memory) but fails with large PDFs
- Policy does not appear in DB after upload, but no 500 error is returned to client

**Phase to address:** PDF Upload API phase — first task that wires the upload endpoint to the extraction pipeline.

---

### Pitfall 2: SQLite "database is locked" Under Concurrent Background Tasks

**What goes wrong:**
Multiple background tasks each open their own SQLAlchemy session and try to write simultaneously. SQLite serializes all writes. Without WAL mode and a busy timeout, even a brief overlap produces `OperationalError: database is locked`. If exceptions in background tasks are not logged explicitly, these failures are silent — the policy is silently dropped.

**Why it happens:**
The current `database.py` creates the engine with no special pragmas:
```python
create_engine(f"sqlite:///{db_path}", echo=False)
```
This uses SQLite's default DELETE journal mode, which is the most restrictive for concurrency. The existing sync CLI never triggered this because batch processing was sequential. Async tasks break this assumption.

**How to avoid:**
Enable WAL mode and set a `busy_timeout` immediately on engine creation. WAL allows concurrent reads while a single writer holds the lock, and `busy_timeout` makes SQLite retry automatically instead of immediately raising.

```python
from sqlalchemy import event

engine = create_engine(f"sqlite:///{db_path}", echo=False)

@event.listens_for(engine, "connect")
def set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")  # 5-second retry window
    cursor.close()
```

WAL does not eliminate serialized writes — only one writer at a time is still the constraint. Keep the semaphore on concurrent extraction tasks at 3-5 workers maximum.

**Warning signs:**
- `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked` in logs
- Batch jobs that complete fine at low concurrency fail at 5+ concurrent tasks
- Silent policy drops when background task exceptions are swallowed

**Phase to address:** Async batch processing phase — before any concurrency is introduced, as the very first step.

---

### Pitfall 3: Alembic `stamp head` Skipped When Retrofitting — Schema Drift Forever

**What goes wrong:**
Developer adds Alembic, runs `alembic autogenerate`. The generated migration is empty because the tables already exist from `create_all()`. Developer concludes "nothing to migrate" and continues. The `alembic_version` table is never populated. Future migrations are generated correctly against the current schema, but `alembic upgrade head` on a fresh database tries to apply all migrations including the empty "initial" one — and the resulting schema is wrong or incomplete because the initial migration does not create the tables that `create_all()` previously created.

**Why it happens:**
Alembic and `create_all()` are parallel schema owners. When both coexist, there is no single source of truth about current state. Alembic's revision chain is disconnected from the live schema. The `alembic_version` table simply does not exist yet.

**How to avoid:**
Immediately after installing Alembic on this codebase:
1. Create an "initial baseline" revision — either empty or containing the full `CREATE TABLE` statements for the existing schema.
2. Run `alembic stamp head` against the existing database to declare "this DB is already at this revision."
3. From this point forward, all schema changes go exclusively through Alembic migrations.
4. Remove `Base.metadata.create_all()` from the production `on_startup` handler. Keep it only in tests that use in-memory SQLite.

**Warning signs:**
- `alembic current` returns nothing on the live database
- `alembic autogenerate` produces an empty migration on a DB that has tables
- New developer clones repo, runs `alembic upgrade head`, gets `OperationalError: table already exists`

**Phase to address:** Alembic migrations phase — `alembic stamp head` must be the very first action, before any other migration is created.

---

### Pitfall 4: SQLite Column Modification Requires `batch_alter_table`, Not Standard `ALTER COLUMN`

**What goes wrong:**
A migration that changes a column's type, adds a constraint, or renames a column uses standard Alembic `op.alter_column()`. SQLite does not support `ALTER COLUMN`. Alembic raises `NotImplementedError` at migration time, or (worse) silently ignores the change, leaving the schema in a partially applied state.

**Why it happens:**
Alembic autogenerate produces standard `op.alter_column()` calls that work on PostgreSQL and MySQL. Developers apply the generated migration without reviewing it for SQLite compatibility. The SQLite limitation is not obvious from the Alembic docs unless you specifically read the SQLite section.

**How to avoid:**
Any migration that modifies an existing column on SQLite must use `op.batch_alter_table()` — this is Alembic's built-in mechanism for SQLite's `ALTER TABLE` limitation (it creates a new table, copies data, and drops the old one).

```python
# WRONG — fails on SQLite
def upgrade():
    op.alter_column("polizas", "prima_total", nullable=False)

# CORRECT — works on SQLite
def upgrade():
    with op.batch_alter_table("polizas") as batch_op:
        batch_op.alter_column("prima_total", nullable=False)
```

Set `render_as_batch=True` in `alembic.ini` or `env.py` to make autogenerate produce batch-compatible migrations by default.

**Warning signs:**
- `NotImplementedError` during `alembic upgrade head`
- Migration completes without error but the column type did not change (check with `PRAGMA table_info(...)`)
- Autogenerated migration contains bare `op.alter_column()` calls

**Phase to address:** Alembic migrations phase — configure `render_as_batch=True` before generating any migration that touches existing columns.

---

### Pitfall 5: Anthropic Rate Limit Storm When Asyncio Batch Has No Backoff

**What goes wrong:**
`asyncio.gather()` launches N concurrent extractions simultaneously. Each sends an Anthropic API request. Anthropic enforces per-minute limits on requests (RPM), input tokens (ITPM), and output tokens (OTPM). Exceeding any dimension returns HTTP 429. Without a bounded semaphore and exponential backoff, all concurrent tasks receive 429 simultaneously and immediately retry — amplifying the rate limit storm. All tasks return `None` and the batch silently produces no results.

**Why it happens:**
The existing `extract_with_retry` catches `ValidationError` but not `anthropic.RateLimitError`. Moving to async without updating the retry logic means 429 errors surface as unhandled exceptions that return `None` — silently dropping the PDF from batch results.

**How to avoid:**
- Use `asyncio.Semaphore(3)` (configurable via `Settings`) to cap concurrent Anthropic calls.
- Use `anthropic.AsyncAnthropic` for true async; the sync `anthropic.Anthropic` blocks the event loop.
- Catch `anthropic.RateLimitError` explicitly and apply exponential backoff with jitter.
- Respect the `Retry-After` header if present.

```python
import asyncio, random
import anthropic

sem = asyncio.Semaphore(settings.MAX_CONCURRENT_EXTRACTIONS)  # default: 3

async def extract_async(client, text, file_hash, model, max_retries=5):
    async with sem:
        for attempt in range(max_retries):
            try:
                msg = await client.messages.create(...)
                return parse_and_validate(msg, file_hash)
            except anthropic.RateLimitError:
                wait = min(2 ** attempt + random.random(), 60)
                await asyncio.sleep(wait)
        return None
```

**Warning signs:**
- Batch of 10+ PDFs produces more `None` results than expected
- Logs show `RateLimitError` without any retry
- API dashboard shows usage that flatlines (throttled) in bursts

**Phase to address:** Async batch processing phase — implement semaphore and backoff before any concurrent extraction is tested.

---

### Pitfall 6: Sonnet Evaluator Costs Doubling Per-PDF Without a Trigger Boundary

**What goes wrong:**
The quality evaluator sends the Haiku extraction output plus the original PDF text to Sonnet for evaluation. Each PDF now costs two API calls: one Haiku extraction + one Sonnet evaluation. If the evaluator is wired into the default extraction path (inline in `extract_with_retry` or in the upload handler), every upload costs 2x more and takes 10-30 seconds longer. There is no opt-out.

**Why it happens:**
The evaluator feels like a natural quality gate to add at the end of the extraction pipeline. The path of least resistance is to call it inside the extraction function. This merges a debug/QA tool into the production hot path.

**How to avoid:**
The Sonnet evaluator is a separate, opt-in step with a defined trigger boundary:
- **Triggered by:** `poliza-extractor regression` CLI command, or `POST /upload?evaluate=true` API parameter.
- **Never triggered by:** default extraction, standard batch runs, or the upload endpoint without explicit opt-in.
- Track Sonnet token cost separately from Haiku extraction cost in logs.
- Set a hard budget ceiling per evaluation run (e.g., skip if batch > 50 PDFs without explicit confirmation).

**Warning signs:**
- API cost per PDF doubles after evaluator is added
- Upload endpoint latency increases by 10-30 seconds per PDF
- Evaluator is always triggered with no way to disable it

**Phase to address:** Sonnet evaluator phase — define the trigger boundary and opt-in mechanism before writing any evaluator code.

---

### Pitfall 7: Golden Dataset Fixtures Tied to Absolute File Paths

**What goes wrong:**
Golden dataset fixtures store absolute file paths (e.g., `C:\Users\josej\extractor_pdf_polizas\pdfs-to-test\axa_auto.pdf`). Tests pass on one machine and fail on another with `FileNotFoundError`. The existing `IngestionCache.file_path` column already stores absolute paths — copying this pattern into golden fixtures carries the same fragility.

**Why it happens:**
Developers copy the same convention from the cache table. Absolute paths feel stable during development on a single machine.

**How to avoid:**
- Golden dataset references use file hashes (SHA-256), not file paths. The hash is the stable, machine-independent identity.
- Store fixtures as `tests/golden/{sha256_hash}.json` files keyed by hash.
- The regression runner hashes the input PDF, looks up the expected output by hash, and compares field-by-field.
- PDFs used in golden tests live in `tests/fixtures/pdfs/` (checked into the repo if file size permits, or documented as downloads).
- Anonymize all golden fixtures before committing — replace real names, RFCs, CURPs, and phone numbers with synthetic values.

**Warning signs:**
- Tests fail on fresh clone with `FileNotFoundError`
- Fixture JSON contains any absolute path strings (catch with `grep -r "C:\\\\" tests/golden/`)
- Golden tests diverge in results between developer machines

**Phase to address:** Golden dataset phase — hash-keyed fixture design must be established before any fixture is created.

---

### Pitfall 8: Excel Export Decimal/Date Types Serialized as Text

**What goes wrong:**
`openpyxl` cannot serialize Python `Decimal` or `datetime.date` objects directly. The ORM models use `Numeric(precision=15, scale=2)` which returns `Decimal` objects, and `Date` columns return `datetime.date`. Passing them directly to a DataFrame produces `TypeError` during export, or silently writes string representations — breaking Excel SUM formulas, number formatting, and date sorting.

**Why it happens:**
The existing `orm_to_schema` already handles serialization correctly for the JSON API. But an Excel export path that reads ORM rows directly (for speed) bypasses this and hits the type incompatibility. Manual testing with small datasets looks correct because `str(Decimal("12500.00"))` renders as `12500.00`, but Excel receives a text cell, not a number cell.

**How to avoid:**
Route all Excel export through the same serialization layer used by the API:
1. Call `orm_to_schema(poliza)` to get a `PolicyExtraction` Pydantic model.
2. Call `.model_dump(mode="json")` to get JSON-serializable primitives (`float`, `str`, `None`).
3. Build the DataFrame from these dicts.

Write a dedicated `poliza_to_excel_row(poliza: Poliza) -> dict` function that controls the column mapping and handles the `Decimal` → `float` and `date` → `datetime` conversions explicitly.

**Warning signs:**
- Excel file opens but SUM formula on `prima_total` column returns 0 (stored as text)
- `TypeError: cannot convert Decimal to float` during DataFrame construction
- Date columns sort alphabetically instead of chronologically in Excel

**Phase to address:** Excel export phase — serialization handling must be the first task, before any column mapping is written.

---

### Pitfall 9: Background Task Provides No Job ID — Client Cannot Poll for Result

**What goes wrong:**
The upload endpoint returns `{"status": "queued"}` with no job ID. The client has no way to know when extraction is complete. They must poll `GET /polizas` and try to match the newly uploaded PDF to a newly created record — which is ambiguous when multiple uploads happen close together. If extraction fails, the client never finds out.

**Why it happens:**
BackgroundTasks in FastAPI is the simplest async pattern and returns immediately. Developers add it without thinking about the client's need to observe the task's outcome.

**How to avoid:**
Generate a UUID job ID at upload time and return it in the 202 response. Track job state (queued, processing, done, failed) in a lightweight in-memory dict (acceptable for single-process local deployment) or a `jobs` table in SQLite. Expose `GET /jobs/{job_id}` that returns current status and, on completion, the extracted policy ID.

```python
@app.post("/upload", status_code=202)
async def upload_pdf(file: UploadFile, background_tasks: BackgroundTasks):
    job_id = str(uuid4())
    pdf_bytes = await file.read()
    job_store[job_id] = {"status": "queued", "poliza_id": None}
    background_tasks.add_task(run_extraction, job_id, pdf_bytes, file.filename)
    return {"job_id": job_id, "status": "queued"}
```

**Warning signs:**
- Upload response contains no ID field
- Client must guess which newly-created policy corresponds to their upload
- Extraction failures are invisible to the client (no error reporting path)

**Phase to address:** PDF Upload API phase — job ID and polling endpoint are part of the API contract, not an afterthought.

---

## Technical Debt Patterns — v1.1

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `Base.metadata.create_all()` in `on_startup` after adding Alembic | No code change needed | Schema diverges silently; fresh-DB migrations produce wrong schema | Never — remove from production startup as soon as Alembic is stamped |
| Run extraction synchronously inside `async def` FastAPI route handler | Simpler code; reuse existing sync functions | Blocks entire event loop; concurrent uploads stall | Only if max 1 concurrent upload is guaranteed (it won't be) |
| Hardcode semaphore limit of 5 concurrent tasks | Fastest to ship | Overloads Anthropic rate limits for lower-tier accounts; breaks silently | Never hardcode — make it a `Settings` field with a safe default of 3 |
| Golden dataset as hand-curated JSON without source PDFs | Fast to create | Cannot re-run extraction to verify; becomes stale as prompt changes | Only if PDFs contain real PII that cannot be stored; document explicitly |
| Sonnet evaluator wired into default extraction pipeline | No separate CLI/API surface needed | Doubles cost and latency for every extraction; no opt-out | Never in the hot path |
| Excel export via `polizas` JSON dump → pandas → Excel (raw ORM objects) | Fast to implement | `Decimal`/`date` type issues; broken Excel formulas | Acceptable only if types are explicitly cast before DataFrame creation |
| In-memory `job_store` dict for background task state | No new DB table needed | State lost on server restart; no persistence across processes | Acceptable for single-user local deployment; document the limitation |

---

## Integration Gotchas — v1.1

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FastAPI `UploadFile` + `BackgroundTasks` | Passing `UploadFile` object to background task | Read `bytes` in handler, pass bytes to task |
| SQLAlchemy sync Session + asyncio | Using `SessionLocal()` directly in `async def` route without executor | Use `run_in_executor` for sync DB calls, or switch to `async_sessionmaker` + `aiosqlite` |
| Anthropic SDK in asyncio context | Using sync `anthropic.Anthropic` in `asyncio.gather` | Use `anthropic.AsyncAnthropic` for true async; sync in thread pool is a fallback only |
| Alembic + existing `create_all()` database | Forgetting `alembic stamp head` on existing DB | Stamp first, then all future schema changes go through migrations |
| Alembic autogenerate on SQLite | Applying generated `op.alter_column()` directly | Always use `op.batch_alter_table()`; set `render_as_batch=True` in `env.py` |
| openpyxl / pandas + SQLAlchemy ORM | Passing ORM model instances directly to DataFrame | Serialize through Pydantic `.model_dump(mode="json")` first |
| Sonnet evaluator + Haiku extraction | Calling Sonnet evaluator in the same function as Haiku extraction | Evaluator is a separate opt-in step; never embedded in the extraction function |

---

## Performance Traps — v1.1

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `asyncio.gather(*tasks)` with no semaphore | All tasks hit Anthropic at once; mass 429 errors; batch result is mostly `None` | `asyncio.Semaphore(3)` minimum | Any batch > 5 PDFs |
| SQLite WAL checkpoint blocked by active readers | WAL file grows indefinitely; disk usage climbs; checkpoint never completes | Monitor WAL file size; ensure idle periods between batch runs | Continuous 24/7 ingestion |
| `orm_to_schema` called N times in bulk export | O(N) Pydantic object creation; slow for 200+ policies | Build rows in a single query with `yield_per`; serialize once | 100+ policies in a single export |
| Sonnet evaluator triggered per-PDF in a large batch | Cost and latency multiplied; Sonnet OTPM exhausted faster than Haiku | Evaluator as separate post-batch pass with its own rate limiting | Any batch > 20 PDFs |
| Background task shares engine with request handler (no session isolation) | Deadlocks when request holds a read session and task tries to write | Each background task creates and closes its own session scope | Any concurrent upload |

---

## Security Mistakes — v1.1

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing uploaded PDF with original client filename on disk | Path traversal (`../../etc/passwd` in filename), filename collision between clients | Rename to `{uuid4()}.pdf` before saving; validate MIME type, not just file extension |
| No file size limit on `POST /upload` | 500 MB upload exhausts server memory or disk | Check `Content-Length` header and enforce `max_size` limit in a FastAPI dependency before reading bytes |
| No MIME type validation on upload | Non-PDF file crashes PyMuPDF or OCR pipeline | Check `file.content_type == "application/pdf"` and verify PDF magic bytes (`%PDF`) in first 4 bytes |
| Golden dataset contains real customer PII (RFC, CURP, nombres) | Data leak if repository is shared or made public | Anonymize all golden fixtures before committing; use synthetic names, hashed identifiers |
| Job store exposed without scoping | One client can poll or cancel another client's job (not relevant for local use) | Not a concern for single-user local deployment; document if API is ever exposed externally |

---

## UX Pitfalls — v1.1

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Upload API returns `{"status": "queued"}` with no job ID | Caller has no way to poll for result; must guess which new policy matches their upload | Return `{"job_id": "...", "status": "queued"}` with `202 Accepted` |
| Regression test failures reported as raw JSON diffs | Hard to read which fields regressed and by how much | Format failures as field-level diffs: `prima_total: expected 12500.00, got 12,500.00` |
| Excel export includes internal provenance fields | End users see `source_file_hash`, `model_id`, `prompt_version` — confusing to non-technical staff | Separate business fields from technical fields; default export omits technical columns |
| Sonnet evaluator score logged only to stdout | Cannot trend quality over time; no baseline to compare against | Persist evaluation scores to a `quality_evaluations` table with prompt version and timestamp |
| Batch progress shown only at completion | Large async batch feels frozen for minutes | Emit per-PDF progress via job status polling; show current count in CLI |

---

## "Looks Done But Isn't" Checklist — v1.1

- [ ] **PDF Upload API:** Endpoint returns 202 and a job ID — verify the background task runs to completion and the policy appears in `GET /polizas` with correct data
- [ ] **PDF Upload API:** Verify uploaded file is renamed to UUID on disk — original filename must not appear in the file system
- [ ] **PDF Upload API:** Verify `GET /jobs/{job_id}` returns `"status": "done"` (not perpetually `"processing"`) after extraction completes
- [ ] **Async batch:** `asyncio.gather` with semaphore in place — verify zero `OperationalError: database is locked` with 5 concurrent uploads
- [ ] **Async batch:** Run batch of 10 PDFs — verify zero `RateLimitError` dropped tasks at default semaphore setting
- [ ] **Alembic setup:** `alembic current` returns a revision on the live database — not empty (empty = stamp was skipped)
- [ ] **Alembic first migration:** `alembic upgrade head` on a fresh SQLite file creates all tables correctly — verify with `PRAGMA table_info`
- [ ] **Alembic column change:** Any migration modifying an existing column uses `batch_alter_table` — verify by grep for bare `op.alter_column` calls
- [ ] **Golden dataset:** All fixtures are keyed by SHA-256 hash, no absolute paths — verify `grep -r "C:\\\\" tests/golden/` returns nothing
- [ ] **Golden dataset:** All PII anonymized — verify no real RFC, CURP, or full name appears in fixture files
- [ ] **Sonnet evaluator:** Default extraction path does NOT trigger the evaluator — verify API call count is unchanged from v1.0 baseline for a standard upload
- [ ] **Excel export:** Numeric columns are numeric in Excel, not text — verify SUM formula on `prima_total` returns a number, not 0
- [ ] **Excel export:** Date columns sort chronologically in Excel — verify date column cell type is Date, not General/Text

---

## Recovery Strategies — v1.1

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| UploadFile closed in background task — extraction produced no data | LOW | Add `pdf_bytes = await file.read()` before returning; no data permanently lost if upload is retried |
| `database is locked` errors caused silent policy drops | MEDIUM | Enable WAL + busy_timeout; identify dropped PDFs from logs; re-submit failed uploads |
| Alembic stamp skipped — schema drift on fresh DB | HIGH | `alembic stamp head` on live DB; audit all pending migrations manually; test on a copy of DB before applying to production |
| Anthropic rate limit storm — batch returned all None | LOW | Re-submit batch with lower concurrency (`MAX_CONCURRENT_EXTRACTIONS=2`); implement backoff before next attempt |
| Golden dataset with absolute paths — CI failures | LOW | Replace paths with hashes; regenerate affected fixtures; 1-2 hours of work |
| Excel export with text-stored decimals — formulas broken | LOW | Fix serialization layer; re-export; no data loss in DB |
| Sonnet evaluator in hot path causing upload timeouts | MEDIUM | Move evaluator behind opt-in flag; rollback the route change; no data loss |

---

## Pitfall-to-Phase Mapping — v1.1

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| UploadFile closed before background task reads it | PDF Upload API | Upload 5 MB PDF; check background task logs for successful extraction; verify policy in DB |
| No job ID for polling | PDF Upload API | Upload response contains `job_id`; `GET /jobs/{job_id}` returns correct status |
| File stored with original filename (path traversal risk) | PDF Upload API | Inspect filesystem; all uploaded files named `{uuid4()}.pdf` |
| SQLite locked under concurrent background tasks | Async batch | Run 5 concurrent uploads; confirm zero `OperationalError` in logs |
| Anthropic rate limit storm without backoff | Async batch | Batch of 10 PDFs completes with zero 429 errors in logs |
| Alembic stamp skipped — schema drift | Alembic migrations (first task) | `alembic current` returns a revision; `alembic upgrade head` on fresh DB creates all tables |
| SQLite `ALTER COLUMN` without `batch_alter_table` | Alembic migrations | All column-modifying migrations use `batch_alter_table`; verified in migration review |
| Sonnet evaluator cost doubling per-PDF | Sonnet evaluator | API call count per upload unchanged from v1.0 baseline without explicit `?evaluate=true` |
| Golden dataset tied to absolute file paths | Golden dataset | `grep -r "Users" tests/golden/` returns nothing; tests pass on clean clone |
| Excel Decimal/Date serialization as text | Excel export | Export 10 policies; SUM on `prima_total` returns numeric result in Excel |

---

## Sources — v1.1

- [FastAPI: UploadFile + BackgroundTasks file-closed issue (GitHub Discussion #10936)](https://github.com/fastapi/fastapi/discussions/10936)
- [FastAPI: Reading file into background task (GitHub Discussion #11177)](https://github.com/fastapi/fastapi/discussions/11177)
- [Patching uploaded files for usage in FastAPI background tasks — dida.do](https://dida.do/blog/patching-uploaded-files-for-usage-in-fastapi-background-tasks)
- [FastAPI Background Tasks — official docs](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [SQLite Write-Ahead Logging — official docs](https://www.sqlite.org/wal.html)
- [SQLite concurrent writes and "database is locked" errors — tenthousandmeters.com](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/)
- [Alembic Autogenerate documentation](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [Alembic Cookbook — working with existing databases](https://alembic.sqlalchemy.org/en/latest/cookbook.html)
- [Alembic Tutorial — stamp command](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Anthropic Concurrency Limit Reached — drdroid.io](https://drdroid.io/integration-diagnosis-knowledge/anthropic-concurrency-limit-reached)
- [Managing API Token Limits in Concurrent LLM Applications — Medium](https://amusatomisin65.medium.com/designing-for-scale-managing-api-token-limits-in-concurrent-llm-applications-84e8ccbce0dc)
- [Building a Golden Dataset for AI Evaluation — getmaxim.ai](https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/)
- [Prompt regression testing: Preventing quality decay — statsig.com](https://www.statsig.com/perspectives/slug-prompt-regression-testing)
- [Understanding Pitfalls of Async Task Management in FastAPI — leapcell.io](https://leapcell.io/blog/understanding-pitfalls-of-async-task-management-in-fastapi-requests)

---

## v1.0 Pitfalls (Resolved — For Reference)

These pitfalls were identified during v1.0 research and are now addressed in the shipped system. They remain here to inform regression verification during v2.0 development.

| Pitfall | v1.0 Resolution | v2.0 Regression Risk |
|---------|----------------|----------------------|
| Scanned PDFs sent raw to LLM | OCR routing via classifier + ocrmypdf | Low — pipeline unchanged; auto-OCR fallback in v2 adds to this, not replaces it |
| No output schema validation | Pydantic + tool_use forced structured output | Low — extraction layer unchanged |
| Generic prompt failing minority layouts | Single-pass adaptive extraction (no templates) | Medium — prompt improvements in v2 could regress working cases; golden dataset regression suite guards this |
| Uncontrolled API costs from token bloat | Per-page assembly; Haiku default; cost tracking | Medium — web UI and auto-evaluation add new Claude API call surfaces; monitor spend |
| Date/currency format inconsistency | Canonical Pydantic schema with ISO 8601 dates | Low — schema unchanged |
| No provenance metadata | `source_file_hash`, `model_id`, `prompt_version` stored per record | Low — provenance fields intact |
| Model drift / no regression tests | Golden dataset shipped in v1.1 | Active concern in v2 — expanded golden dataset must cover all 10 insurers |
| Multi-insured flat schema | Separate `asegurados` and `coberturas` tables | Low — schema unchanged |

---
*Pitfalls research for: PDF extraction pipeline — v1.1 additions + v2.0 Web UI & Extraction Quality*
*Originally researched: 2026-03-18 | Updated: 2026-03-20*
