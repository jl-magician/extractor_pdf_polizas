# Phase 17: Golden Dataset Expansion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 17-golden-dataset-expansion
**Areas discussed:** Fixture creation workflow, Insurer coverage strategy, Fixture naming & organization, Regression test improvements

---

## Fixture Creation Workflow

### PDF Availability

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, I have PDFs ready | Real policy PDFs from multiple insurers available. | ✓ |
| I can gather them | Need to collect PDFs from agency files. | |
| Some available, need more | Partial coverage. | |

**User's choice:** Yes, I have PDFs ready

### Creation Method

| Option | Description | Selected |
|--------|-------------|----------|
| Batch script (Recommended) | Processes all PDFs, extracts, redacts PII, writes fixtures. | ✓ |
| One-by-one via CLI | Manual create-fixture for each PDF. | |
| Semi-automated with review | Batch extract then HITL review each. | |

**User's choice:** Batch script

### Review Process

| Option | Description | Selected |
|--------|-------------|----------|
| Raw fixtures first, review later (Recommended) | Two-step: create raw, then review/correct in HITL UI. | ✓ |
| Raw fixtures are final | Trust extraction output as-is. | |

**User's choice:** Raw fixtures first, review later

---

## Insurer Coverage Strategy

### Fixtures Per Insurer

| Option | Description | Selected |
|--------|-------------|----------|
| 2 per insurer (Recommended) | 20 total. One auto + one other type per insurer. | ✓ |
| Minimum 1, extras for complex ones | 1 baseline + extras for unusual formats. | |
| 3+ per insurer | 30+ total. Broader but more work. | |

**User's choice:** 2 per insurer (20 total)

### Insurer List

| Option | Description | Selected |
|--------|-------------|----------|
| I'll provide the list | User provides the 10 insurer names. | ✓ |
| You decide from extractions | Use whatever insurers appear in PDFs. | |

**User's choice:** I'll provide the list
**Notes:** 10 insurers: Zurich, Qualitas, Mapfre, AXA, GNP, Chubb, Ana, HDI, Plan Seguro, Prudential

### Policy Types

| Option | Description | Selected |
|--------|-------------|----------|
| Auto + one other (Recommended) | 1 auto + 1 other type per insurer. | |
| Most common types per insurer | 2 most common types per insurer. May vary. | ✓ |
| You decide | Claude picks representative types from PDFs. | |

**User's choice:** Most common types per insurer

---

## Fixture Naming & Organization

### Naming Convention

| Option | Description | Selected |
|--------|-------------|----------|
| {insurer}_{type}_{seq}.json (Recommended) | e.g., zurich_auto_001.json. Clear, sortable. | ✓ |
| {insurer}_{poliza_number}.json | Ties to actual policy number. | |
| {seq}_{insurer}_{type}.json | Numbered first for ordered display. | |

**User's choice:** {insurer}_{type}_{seq}.json

### Metadata

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal metadata (Recommended) | _source_pdf, _insurer, _tipo_seguro, _created_at. | ✓ |
| Rich metadata | Add _prompt_version, _model_id, _extraction_time, _reviewed. | |
| No extra metadata | Only _source_pdf (required by tests). | |

**User's choice:** Minimal metadata

---

## Regression Test Improvements

### New Field Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Ignore new fields (Recommended) | Only check fixture fields. FieldDiffer already supports. | ✓ |
| Warn but don't fail | Log new fields as warnings. | |
| Fail on new fields | Strictest, requires updates with prompt changes. | |

**User's choice:** Ignore new fields

### Coverage Report

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, coverage matrix (Recommended) | Print insurer x type matrix with pass/fail/skip counts. | ✓ |
| Standard pytest output | Default pytest output only. | |
| JSON report file | Machine-readable regression_report.json. | |

**User's choice:** Yes, coverage matrix

### Self-Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, self-test after creation (Recommended) | Run pytest -m regression after creating all fixtures. | ✓ |
| No, manual testing later | Create fixtures only, test separately. | |

**User's choice:** Yes, self-test after creation

---

## Claude's Discretion

- Batch script implementation approach
- Coverage matrix formatting
- Failed extraction handling in batch
- FieldDiffer tolerance thresholds
- Optional --update-fixtures flag

## Deferred Ideas

None — discussion stayed within phase scope
