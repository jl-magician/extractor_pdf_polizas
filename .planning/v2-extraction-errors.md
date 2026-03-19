# v2 Extraction Errors — Real PDF Testing

**Documented:** 2026-03-19
**Source PDF:** 112234653_Poliza.pdf (Zurich, Seguro de Automovil)
**Model:** claude-haiku-4-5-20251001, prompt v1.0.0

## Purpose

These errors were found during real-world testing of v1.0 with actual insurance PDFs. They should inform:
1. Prompt tuning in v2 (more specific instructions for campos_adicionales)
2. Golden dataset creation (QAL-01) — this PDF becomes a test case with expected values
3. Human-in-the-loop review (QAL-03) — correction UI for the agency team
4. UAT with real documents — v2 UAT should test against actual PDFs, not just mocked responses

## Errors Found

### 1. clave_vehiculo — wrong value
- **Extracted:** "L 4P 3OCU"
- **Expected:** "057U1127"
- **Type:** Value confusion — Claude picked the vehicle class code instead of the actual plate/key

### 2. direccion — extra character in address
- **Extracted:** "AVENIDA DEL PARQUE 56 E, COLONIA NAPOLES, BENITO JUAREZ, CIUDAD DE MEXICO, 03810"
- **Expected:** "AVENIDA DEL PARQUE 56, COLONIA NAPOLES, BENITO JUAREZ, CIUDAD DE MEXICO, 03810"
- **Type:** Hallucination — added "E" that doesn't exist in the original

### 3. financiamiento — wrong value
- **Extracted:** 808.2
- **Expected:** 0.0
- **Type:** Value swap with otros_servicios_contratados

### 4. otros_servicios_contratados — wrong value
- **Extracted:** 0
- **Expected:** 808.2
- **Type:** Value swap with financiamiento (fields swapped)

### 5. subsecuentes — wrong value
- **Extracted:** 29956.04
- **Expected:** 0.0
- **Type:** Incorrect value — likely copied from primer_pago

### 6. folio — wrong value
- **Extracted:** "75534"
- **Expected:** null
- **Type:** Value that belongs in clave, not folio

### 7. clave — wrong value
- **Extracted:** "995"
- **Expected:** "75534"
- **Type:** Value swap with folio

### 8. agencia_responsable — should not exist
- **Extracted:** "Unidad Especializada"
- **Expected:** (field should not be extracted)
- **Type:** Irrelevant field — not useful for agency operations

## Patterns Observed

1. **Value swaps** (errors 3-4, 6-7): Claude confuses adjacent fields in tables/layouts, especially financial breakdowns. This is the most common error type.
2. **Hallucination** (error 2): Minor text fabrication in address — added a character.
3. **Wrong source** (errors 1, 5): Claude picks a value from the wrong location in the PDF.
4. **Irrelevant extraction** (error 8): Claude extracts fields that aren't useful.

## Recommendations for v2

- **Prompt improvement:** Add examples of financial breakdown tables showing correct field mapping (primer_pago, subsecuentes, financiamiento, etc.)
- **Golden dataset:** Use this PDF as test case #1 with expected values documented above
- **Post-extraction validation:** Cross-check financial fields (primer_pago + subsecuentes should relate logically to prima_total)
- **Field exclusion list:** Allow configuring fields to never extract (like agencia_responsable)
- **Sonnet review:** For campos_adicionales financial fields, a Sonnet pass could catch these swaps

---

## Batch Test Results (8 PDFs, 2026-03-19)

| File | Insurer | Result | Notes |
|------|---------|--------|-------|
| 112234653_Poliza.pdf | Zurich | OK (skipped - cached) | Value swap errors in campos_adicionales (see above) |
| 112234440_Poliza.pdf | Zurich | OK | Auto policy |
| 112234526_Poliza.pdf | Zurich | OK | Auto policy |
| 150262064802.pdf | AXA | OK | Auto policy |
| 4102500042929_3.pdf | MAPFRE | OK | Auto policy |
| danPol00112212110End00000ZJZHCL.Pdf | Zurich | OK | Home policy (31 pages) |
| Poliza - 001_LGS-RCGRA_07013104_01_0.pdf | ? | FAILED | OCR error: `ocr() missing positional argument` — scanned PDF, ocrmypdf call bug |
| Poliza 8650156226.pdf | ? | HALLUCINATION | All fields null/UNKNOWN — PDF has 0 extractable text despite being classified as "digital" |

**Cost:** $0.13 USD for 7 PDFs processed (~$0.02/policy on Haiku)

---

## Additional Issues from Batch

### 9. Zero-text digital PDF (Poliza 8650156226.pdf)
- **Problem:** 3-page PDF classified as "digital" but `get_text()` returns 0 chars on all pages
- **Root cause:** Text is likely rendered as vector paths or small image tiles that don't trigger the 80% image coverage threshold
- **Impact:** Claude gets empty text, returns all nulls with `<UNKNOWN>` for required fields
- **Fix for v2:** Add minimum text length check after classification — if digital page has <10 chars, reclassify as "scanned" and OCR it

### 10. OCR call failure (Poliza - 001_LGS-RCGRA_07013104_01_0.pdf)
- **Problem:** `ocr() missing 1 required positional argument: 'input_file_or_options'`
- **Root cause:** Scanned PDF triggered OCR path but ocrmypdf.ocr() was called with wrong arguments (possibly API change or path issue)
- **Impact:** Entire PDF extraction skipped
- **Fix for v2:** Debug ocrmypdf call with this specific file; may need path quoting fix for filenames with spaces/special chars

---

## v2 Feature Request: Human Review UI

**User request (2026-03-19):** Build an easier UI for the user to:
1. Review each extraction side-by-side with the source PDF
2. Approve correct fields
3. Edit/correct wrong fields inline
4. Mark fields as "null" (not present in PDF)
5. Have the system learn from corrections to improve future extractions

This maps to:
- QAL-03 (human-in-the-loop review)
- New: Correction storage and feedback loop for prompt improvement
- New: Side-by-side PDF viewer + extraction editor UI
