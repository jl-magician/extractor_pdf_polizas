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

## Milestone: v1.1 — API & Quality

**Shipped:** 2026-03-19
**Phases:** 7 | **Plans:** 14 | **Commits:** 80

### What Was Built
- Alembic schema versioning with auto-migrate on startup and backup
- Excel/CSV export with multi-sheet workbooks, correct date/number types, Spanish filter flags
- PDF Upload API with async job system (POST → 202 → poll → result)
- Concurrent batch processing (ThreadPoolExecutor, --concurrency flag, rate limit retry)
- Sonnet quality evaluator (opt-in --evaluate, 3-dimension scoring, DB persistence)
- Golden regression suite (PII-safe fixtures, field-by-field drift reporting, @pytest.mark.regression)
- Milestone polish (FieldDiffer Decimal/float safety, VALIDATION/SUMMARY frontmatter fixes)

### What Worked
- **TDD in execution agents** — tests written before implementation caught integration issues early
- **Wave-based parallel execution** — Phase 12 ran both plans simultaneously, saving wall-clock time
- **Plan checker revision loop** — Phase 9's checker caught a real blocker (retry count always 0) before execution, saving a full re-execution
- **Per-phase discuss → plan → execute cycle** — each phase got exactly the right context
- **Existing test infrastructure reuse** — conftest.py, TestClient, mock patterns from v1.0 reused extensively

### What Was Inefficient
- **VALIDATION.md nyquist_compliant never auto-flipped** — all 6 phases needed manual fix in Phase 12. Executor workflow should update this.
- **SUMMARY frontmatter requirements_completed inconsistently populated** — some executors filled it, some didn't. Should be enforced.
- **Audit flagged REG-02 for an intentional decision** — user chose "Exact match" but audit called it a gap. Audit should check CONTEXT.md decisions.

### Patterns Established
- Lazy imports inside CLI commands (prevents heavy deps from slowing startup)
- Per-thread SessionLocal() for SQLite thread safety
- 3-tuple return from extract_policy() (policy, usage, rl_retries)
- PII redaction in fixtures with `[REDACTED]` sentinel

### Key Lessons
1. Plan checker saves execution cost — catching bugs in planning is cheaper than re-executing phases
2. Cosmetic tracking gaps compound — small frontmatter issues across 6 phases needed a dedicated cleanup phase
3. User decisions should override audit heuristics — explicit choices shouldn't be flagged as gaps

### Cost Observations
- Model mix: opus for planning, sonnet for research/execution/verification
- 7 phases completed in one extended session
- Notable: parallel execution in Phase 12 cut execution time in half

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Timeline | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | 2 days | 5 | Initial process — discuss → research → plan → execute → verify |
| v1.1 | 2 days | 7 | Added plan checker revision loop, parallel wave execution, milestone audit |

### Cumulative Quality

| Milestone | Tests | Verification | Gap Closure |
|-----------|-------|-------------|-------------|
| v1.0 | 153 | 5/5 phases passed | 0 cycles |
| v1.1 | 263 (+110) | 7/7 phases passed | 1 cycle (Phase 12 polish) |

### Top Lessons (Verified Across Milestones)

1. Non-retrofittable contracts first — data model decisions cascade through every subsequent phase
2. TDD with mocked external APIs gives full coverage without runtime costs
3. Plan checker catches real bugs before execution — saves full re-execution cost
4. Cosmetic tracking gaps compound — enforce frontmatter updates in executor workflow
