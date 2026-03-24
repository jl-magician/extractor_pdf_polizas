# Phase 16: PDF Reports & Auto-Evaluation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 16-pdf-reports-auto-evaluation
**Areas discussed:** PDF generation approach, Report content & layout, Auto-evaluation trigger, Campo swap detection

---

## PDF Generation Approach

### PDF Library

| Option | Description | Selected |
|--------|-------------|----------|
| WeasyPrint (Recommended) | Renders HTML->PDF. Jinja2 templates styled with CSS. ~50MB dep. | ✓ |
| FPDF2 | Lightweight pure-Python. Manual coordinate positioning. ~2MB. | |
| ReportLab | Industry-standard. Platypus flowables, canvas drawing. Heaviest. | |

**User's choice:** WeasyPrint
**Notes:** Reuses existing Jinja2 skills, professional output.

### Download Button Location

| Option | Description | Selected |
|--------|-------------|----------|
| Detail page only (Recommended) | Button on detail page header next to exports. | |
| Detail + list page | Button on detail AND download icon on list rows. | |
| Detail + review page | Available on both detail and review pages. | ✓ |

**User's choice:** Detail + review page
**Notes:** Reviewers can download after corrections.

### Data Source for Report

| Option | Description | Selected |
|--------|-------------|----------|
| Corrected values (Recommended) | Report shows latest corrected data from polizas table. | ✓ |
| Both with indicators | Show corrected values but mark corrected fields. | |

**User's choice:** Corrected values

### Generation Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| On-the-fly (Recommended) | Generate each click. Always latest data. No disk storage. | ✓ |
| Cache on disk | Generate once, cache. Faster repeat but stale after corrections. | |

**User's choice:** On-the-fly

### Paper Size

| Option | Description | Selected |
|--------|-------------|----------|
| Letter (Recommended) | 8.5x11 inches. Standard in Mexico. | ✓ |
| A4 | ISO standard. Slightly taller/narrower. | |

**User's choice:** Letter

### Filename Format

| Option | Description | Selected |
|--------|-------------|----------|
| poliza_{numero}_{aseguradora}.pdf (Recommended) | Easy to identify when downloading multiple. | ✓ |
| reporte_{numero}.pdf | Shorter, insurer info inside document. | |

**User's choice:** poliza_{numero}_{aseguradora}.pdf

---

## Report Content & Layout

### Report Sections

| Option | Description | Selected |
|--------|-------------|----------|
| Header with insurer branding | Aseguradora name, logo area, poliza number, date. | ✓ |
| General info block | Contratante, agente, tipo seguro, vigencia, forma pago. | ✓ |
| Financial summary | Prima total, desglose, moneda, frecuencia. | ✓ |
| Coverage table | All coberturas as table with concepto, suma, deducible, etc. | ✓ |

**User's choice:** All four sections selected.

### Asegurados in Report

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, as a table (Recommended) | Full table: nombre, parentesco, fecha_nacimiento, RFC. | ✓ |
| Only count | Just 'N asegurados' without details. | |
| Skip | Omit asegurados entirely. | |

**User's choice:** Yes, as a table

### Per-Insurer Differentiation

| Option | Description | Selected |
|--------|-------------|----------|
| Color scheme + field order (Recommended) | Config file per insurer with brand color, field order, toggles. | ✓ |
| Fully separate templates | One complete template per insurer. Max flexibility, more maintenance. | |
| Color scheme only | Same layout, just different header color. Minimal differentiation. | |

**User's choice:** Color scheme + field order

### Campos Adicionales in Report

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, as key-value list (Recommended) | Simple key: value list at end of report. | ✓ |
| Only if non-empty | Same but omit section when null/empty. | |
| Skip | Omit campos_adicionales entirely. | |

**User's choice:** Yes, as key-value list

### Config File Location

| Option | Description | Selected |
|--------|-------------|----------|
| policy_extractor/reports/configs/ (Recommended) | Inside package, version-controlled. YAML files. | ✓ |
| data/report_configs/ | Outside package, user-editable, not version-controlled. | |

**User's choice:** policy_extractor/reports/configs/

---

## Auto-Evaluation Trigger

### When to Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| After batch completes, 10+ polizas (Recommended) | Matches SC-3. Auto-evaluate sample when batch >= 10. | |
| After any extraction | Auto-evaluate when recent extractions reach >= 10. Broader. | ✓ |
| Scheduled cron-like | Run evaluation periodically on unevaluated records. | |

**User's choice:** After any extraction (when threshold met)
**Notes:** Broader than SC-3 minimum — includes single-file uploads accumulating to threshold.

### Default Sample Percentage

| Option | Description | Selected |
|--------|-------------|----------|
| 10% (Recommended) | Matches SC-3 default. | |
| 20% | Higher coverage, more cost. | ✓ |
| 100% | Evaluate all records. Most thorough, highest cost. | |

**User's choice:** 20%
**Notes:** User prefers higher quality coverage over cost savings.

### UI Display of Scores

| Option | Description | Selected |
|--------|-------------|----------|
| Score badge in poliza list + detail (Recommended) | Colored badge on list rows and detail header. | |
| Dashboard only | Aggregate stats on dashboard, individual on detail click. | |
| Both list + dashboard | Badge on list rows AND aggregate stats on dashboard. | ✓ |

**User's choice:** Both list + dashboard

### Threading Model

| Option | Description | Selected |
|--------|-------------|----------|
| Same thread (Recommended) | Runs after extraction in same thread. Adds ~3-5s per record. | ✓ |
| Separate background thread | Fire-and-forget. Non-blocking but more complex. | |

**User's choice:** Same thread

---

## Campo Swap Detection

### Detection Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Extended evaluation prompt (Recommended) | Add swap criteria to existing eval prompt. One API call. | ✓ |
| Separate dedicated pass | Second Sonnet call focused on campos_adicionales. Doubles cost. | |
| Post-processing heuristic first | Pattern-matching before Sonnet fallback. Cheapest, less accurate. | |

**User's choice:** Extended evaluation prompt

### Warning Storage

| Option | Description | Selected |
|--------|-------------|----------|
| validation_warnings column (Recommended) | Append to existing JSON array. Consistent with Phase 13 pattern. | ✓ |
| Separate swap_warnings column | New column, needs migration. Cleaner separation. | |
| In evaluation_json only | Store in eval data. Less visible to UI. | |

**User's choice:** validation_warnings column

### Action on Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Warn only (Recommended) | Add warning, human reviews via HITL. Safer. | |
| Warn + suggest correction | Warning includes suggested field reassignment. Human applies fix. | ✓ |
| Auto-correct + log | Auto-swap fields, log in corrections. Risky without human review. | |

**User's choice:** Warn + suggest correction
**Notes:** Warning text should describe suspected swap and recommend target field. Human applies via HITL review.

---

## Claude's Discretion

- WeasyPrint CSS print stylesheet design
- Exact color schemes per insurer
- Evaluation sampling algorithm
- Score badge color thresholds
- Dashboard aggregate stats layout
- Swap detection prompt engineering

## Deferred Ideas

None — discussion stayed within phase scope
