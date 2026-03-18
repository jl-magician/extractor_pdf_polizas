# Pitfalls Research

**Domain:** Insurance PDF data extraction with LLMs (Claude API)
**Researched:** 2026-03-17
**Confidence:** HIGH (multiple verified sources, official docs, post-mortems)

---

## Critical Pitfalls

### Pitfall 1: Sending Scanned PDFs Directly to Claude Without OCR Pre-Processing

**What goes wrong:**
Claude receives a scanned PDF as a vision input and either silently misreads characters — especially numbers, dates, and currency amounts — or returns hallucinated values with no indication of uncertainty. Numerical fields (policy limits, premiums, deductibles) are the highest-risk category. The LLM outputs whatever "seems plausible" for illegible characters without flagging the guess.

**Why it happens:**
Developers conflate Claude's vision/PDF reading capability with a hardened OCR system. Claude can read documents, but it does not preprocess, deskew, or enhance images the way dedicated OCR engines do. Low-resolution scans (under 150 DPI), skewed pages, or poor contrast amplify this. Claude's API also does not expose confidence scores, so bad reads are silent.

**How to avoid:**
Use a dedicated OCR engine (Tesseract, AWS Textract, or Azure Form Recognizer) as the first stage for any scanned PDF. Feed the corrected text to Claude, not the raw image. For digital PDFs (selectable text), extract text directly with a library like `pdfplumber` or `pymupdf` — bypass vision entirely. Build a routing step: detect whether the PDF is digital or scanned before choosing the extraction path.

**Warning signs:**
- Premiums or sums insured extracted as wrong magnitudes (e.g., 10,000 instead of 100,000)
- Dates returning impossible values (day 31 in February, year 0025 instead of 2025)
- Policy numbers with transposed digits
- Fields that are correct 95% of the time but randomly wrong on certain insurers' scanned documents

**Phase to address:**
Phase 1 (PDF ingestion and pre-processing) — must classify digital vs. scanned and route accordingly before any LLM call is made.

---

### Pitfall 2: No Output Schema Validation — Silent Wrong Extractions Stored in DB

**What goes wrong:**
Claude returns JSON that looks valid but has wrong field names, wrong types, missing required fields, or hallucinated values for fields that were blank in the original document. Because there is no validation layer, these bad records are stored in the database as if they were correct. Downstream reports and queries produce wrong results that are hard to trace back to specific extractions.

**Why it happens:**
Early prototypes work well on clean documents, creating false confidence. In production, edge cases — blank fields, unusual layouts, multi-page tables — cause the model to invent plausible-sounding values rather than return null. Without a schema contract, the code that receives the JSON also silently accepts wrong data types (e.g., a string "N/A" in a decimal field for `premium`).

**How to avoid:**
Define a strict Pydantic schema for every document type. Use Claude's native structured outputs (tool_use / JSON mode) to constrain the response format. Validate every response against the schema before writing to the database. For fields that are genuinely optional, explicitly instruct Claude to return `null` rather than inventing a value. Implement a "low confidence" flag for any field where the source text was ambiguous.

**Warning signs:**
- Fields returning "N/A", "unknown", or empty string where the schema expects a number
- Inconsistent field names across batches (e.g., `suma_asegurada` vs `sumaAsegurada` vs `coverage_amount`)
- Records in the DB with default or zero values for required financial fields
- Tests pass on sample PDFs but production shows sporadic bad data

**Phase to address:**
Phase 1 (data model and schema definition) and Phase 2 (LLM extraction layer) — schema must be defined before the first prompt is written; validation must be built into the extraction function, not added later.

---

### Pitfall 3: Treating 50-70 PDF Structures as One Generic Extraction Problem

**What goes wrong:**
A single generic prompt is used for all insurers and policy types. It works adequately for the most common structure but fails silently for the rest. Some insurers use multi-column layouts where coverage tables span two columns; others encode policy limits inside scanned checkbox grids. The generic prompt either skips these fields or confuses them with other fields.

**Why it happens:**
The appeal of "no templates" (a stated requirement) is interpreted as "one prompt for everything." In reality, the LLM still benefits from document-class-specific hints. The difference is that hints are soft guidance in the prompt, not rigid positional templates — which is sustainable across 50-70 structures.

**How to avoid:**
Implement a two-pass strategy: (1) a classification pass that identifies the insurer and policy type from the first page, then (2) a targeted extraction prompt that includes insurer-specific guidance (known field names, known layout quirks). Maintain a lightweight registry of per-insurer prompt modifiers — not full templates, just notes. Start with the 3-4 highest-volume insurers and expand incrementally.

**Warning signs:**
- One insurer's policies consistently have lower extraction completeness than others
- Coverage amounts extracted correctly for auto policies but missing for vida (life) policies
- Fields like `agente` or `clave_agente` present in raw text but missing from extraction output

**Phase to address:**
Phase 2 (LLM extraction layer) — classification routing must be built before generic extraction is considered "done."

---

### Pitfall 4: Uncontrolled API Costs From Token Bloat

**What goes wrong:**
A 20-page insurance policy PDF converted to text and sent in full to Claude consumes 30,000-60,000 input tokens per call. At 200+ policies per month, costs are manageable at first, but if batch reprocessing is ever triggered (bug fix, schema change, new fields added), the entire corpus must be re-extracted, multiplying costs by 10-50x unexpectedly.

**Why it happens:**
Developers send the entire PDF text to Claude without chunking or relevance filtering. Insurance PDFs contain extensive boilerplate legal text (terms, conditions, exclusions) that is irrelevant to field extraction and consumes tokens unnecessarily. The actual data fields often appear in the first 3-5 pages.

**How to avoid:**
Pre-process PDFs to extract only the data-dense sections (policy summary, schedule of coverage, insured details) before sending to Claude. Claude's PDF API uses 1,500-3,000 tokens per page — a 20-page PDF costs as much as 60,000 tokens per call. Use `claude-3-5-haiku` for initial classification and simple single-page documents; reserve `claude-3-5-sonnet` or `claude-opus` only for complex multi-page extractions. Estimate monthly token budget before launch and add a hard limit alert.

**Warning signs:**
- Average tokens per extraction call exceeding 20,000 for typical policies
- No `max_tokens` limit set on API calls
- Reprocessing a backlog takes 10x the expected cost
- API invoices growing month over month with no new volume

**Phase to address:**
Phase 2 (LLM extraction layer) — token optimization must be designed in, not retrofitted. Define a per-policy token budget before writing the first production prompt.

---

### Pitfall 5: Date and Currency Format Inconsistency Across Insurers

**What goes wrong:**
Mexican insurers use DD/MM/YYYY date formats; some bilingual policies use MM/DD/YYYY or YYYY-MM-DD. Currency values appear as "1,500,000.00", "1.500.000,00" (European notation), "$1,500,000 MXN", and "MXN 1500000". When stored inconsistently in the database, queries and comparisons silently return wrong results (e.g., a policy with `vigencia_inicio` of "01/02/2025" is ambiguous — is it January 2 or February 1?).

**Why it happens:**
The LLM extracts values exactly as they appear in the document without normalizing them. No normalization layer exists in the pipeline. This is not a model failure — it is an architecture gap.

**How to avoid:**
Define canonical formats in the Pydantic schema: dates as ISO 8601 (`YYYY-MM-DD`), currencies as decimal numbers with a separate currency code field. Instruct Claude explicitly in the system prompt to normalize all dates and amounts to these canonical formats. Add a post-extraction normalization step that validates and re-normalizes using Python's `datetime` and `decimal` libraries as a safety net.

**Warning signs:**
- Date fields in the database with mixed format strings
- Premium or suma_asegurada fields stored as strings rather than numbers
- Queries for policies expiring in a date range returning incomplete results

**Phase to address:**
Phase 1 (data model definition) — canonical formats must be defined in the schema before any extraction is built.

---

### Pitfall 6: No Reprocessing Strategy — Extractions Cannot Be Re-Run Reliably

**What goes wrong:**
The system has no record of which Claude model version or prompt version was used to extract each policy. When a bug is found (wrong field mapping, missing coverage data) or the schema is extended (new fields added), there is no way to identify which records are affected or re-extract them consistently. Manual fixes accumulate in the database, diverging from what automated re-extraction would produce.

**Why it happens:**
Early development focuses on making extraction work, not on making it reproducible. Provenance metadata (source file hash, model ID, prompt version, extraction timestamp) is not stored alongside extracted data.

**How to avoid:**
Store an extraction audit record with every policy: `source_file_path`, `source_file_hash` (sha256), `model_id` (e.g., `claude-3-5-sonnet-20241022`), `prompt_version`, `extracted_at`, `extraction_status`. Keep original PDF files on disk, referenced by hash. This enables targeted re-extraction of any subset of records when needed.

**Warning signs:**
- No `model_version` or `prompt_version` column in the database
- Uncertainty about whether a specific record was extracted with the current or a previous prompt
- Manual edits to extracted records with no audit trail

**Phase to address:**
Phase 1 (data model and database design) — provenance columns must be in the initial schema migration.

---

### Pitfall 7: Model Drift Silently Degrades Extraction Quality

**What goes wrong:**
A prompt that extracts fields correctly today begins returning different (worse) results after Anthropic updates Claude. Field names change, null handling changes, or previously reliable structures are no longer recognized. Because there is no regression test suite, degradation is only noticed when a user reports a wrong value weeks later.

**Why it happens:**
LLM providers update models continuously, even "pinned" model IDs can exhibit behavioral changes. A 2025 LLMOps study found that models left unchanged for 6+ months see error rates increase 35% on new data patterns. Without a golden dataset and automated regression tests, there is no early warning system.

**How to avoid:**
Build a golden dataset of 20-30 sample PDFs (covering all major insurers and policy types) with manually verified expected extraction outputs. Run this test suite after any model or prompt change. Pin Claude model IDs to specific dated versions (e.g., `claude-3-5-sonnet-20241022`) rather than `claude-3-5-sonnet-latest`. Monitor extraction completeness rate (fields extracted / fields expected) in production on a weekly basis.

**Warning signs:**
- No regression test suite for extraction quality
- Using `latest` model alias instead of a pinned version
- No monitoring of extraction completeness over time
- Users reporting "it used to extract X but now it doesn't"

**Phase to address:**
Phase 2 (LLM extraction layer) and ongoing — golden dataset should be built alongside the first extraction implementation.

---

### Pitfall 8: Multiple Insured Persons/Assets Stored in a Flat Schema

**What goes wrong:**
Insurance policies can cover multiple insured persons (vida, gastos médicos) or multiple vehicles/assets (flotilla). A flat database schema with `insured_name`, `insured_dob` columns can only hold one insured per policy. When a policy covers a family of four, the extraction either picks one person arbitrarily, concatenates names into a string, or fails entirely.

**Why it happens:**
The schema is designed around the simplest case (one insured) and the multi-insured case is deferred. By the time real multi-insured policies are encountered in production, data is already in the DB in a format that cannot be migrated cleanly.

**How to avoid:**
Design the database with a separate `insured_persons` table (one row per person, foreign key to policy) and a separate `insured_assets` table from day one. The extraction schema should return these as arrays. This is explicitly called out in the project requirements ("Manejo de múltiples asegurados") — implement it in Phase 1, not as a later addition.

**Warning signs:**
- `insured_name` field stored as a single string with comma-separated names
- Only one vehicle found extracted from a multi-vehicle policy
- Schema has `insured_1_name`, `insured_2_name` columns instead of a related table

**Phase to address:**
Phase 1 (data model) — one-to-many relationships must be in the initial schema. This cannot be retrofitted without a full migration.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Single generic prompt for all policy types | Faster initial build | 20-30% lower extraction completeness on minority layouts | Never in production; acceptable in spike/prototype only |
| Storing extracted dates as strings | No normalization code needed | Broken date range queries, ambiguous DD/MM vs MM/DD | Never |
| Skipping OCR pre-processing for scanned PDFs | Simpler architecture | Silent numerical errors on scanned documents | Never for financial fields |
| No schema validation on LLM output | Faster first iteration | Corrupt DB records that are invisible until queried | Prototype only, must be fixed before first real data ingestion |
| Using `claude-3-5-sonnet-latest` alias | No version pinning needed | Unexpected behavior changes after Anthropic updates | Never in production |
| Sending full PDF text to LLM | Simpler code | Token costs 3-5x higher than necessary | Acceptable while building; must optimize before scale |
| Skipping provenance metadata | Faster schema | Cannot re-extract specific records after bugs | Never; 2 extra columns at schema creation time |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Claude API — PDF vision | Sending all pages as vision for digital PDFs | Extract text with pdfplumber first; use vision only for scanned pages |
| Claude API — structured output | Parsing `response.content[0].text` as JSON with `json.loads()` | Use `tool_use` / JSON mode which guarantees parseable output; still validate with Pydantic |
| Claude API — batch processing | Submitting 200 policies in one batch job and waiting 24h for results | Use the Message Batches API for large batches; results return within 1h for most; include `custom_id` matching source file hash |
| Claude API — rate limits | No retry logic; first 429 crashes the pipeline | Implement exponential backoff with the `retry-after` header; distinguish 429 (rate limit) from 529 (server overload) |
| pdfplumber / pymupdf — text extraction | Treating extracted text as clean prose | Multi-column layouts extract columns sequentially, not left-to-right per line; validate with spot checks |
| SQLite — dynamic fields | Using EAV (entity-attribute-value) tables for all policy fields | Use a hybrid: fixed columns for common fields, a single `extra_fields JSONB` column for insurer-specific extras |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous extraction — one PDF at a time | CLI takes 45+ minutes for a 200-policy monthly batch | Implement concurrent extraction with asyncio + semaphore to limit parallel API calls | At 50+ policies per batch |
| No deduplication check | Re-processing the same PDF file twice creates duplicate records | Hash the source file (sha256) and check against DB before extracting | Immediately in production when users re-submit files |
| Storing full PDF binary in DB | Database grows 50MB+ per month; backup time increases | Store only the file path and hash in DB; keep PDFs in a designated local folder | At 6-12 months of operation |
| Re-extracting all records on schema change | Adding one new field triggers re-extraction of entire history | Design extraction to be incremental: extract missing fields only for records that lack them | First time a schema change is needed |
| No pagination on JSON API output | API returns all 2,000+ policies in one response | Add limit/offset pagination and field selection from day one | When the corpus exceeds ~500 policies |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing Claude API key in source code or `.env` committed to git | API key exposure; billing liability | Use OS keyring or environment variable; add `.env` to `.gitignore` before first commit |
| Logging full PDF text content in debug logs | PII exposure (names, RFCs, dates of birth) in log files | Log metadata only (file hash, page count, insurer name); never log extracted field values |
| No input validation on CLI file path argument | Path traversal if the CLI is ever exposed as an API endpoint | Validate that the provided path is within the expected input directory |
| Exposing the full DB via the JSON API with no auth | All policy data accessible to anyone on the local network | Add API key auth from the start, even for local use; this is PII-heavy insurance data |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| CLI returns no progress feedback during batch processing | User cancels thinking it is frozen; duplicate processing | Show a progress bar (tqdm) with current/total and current file name |
| Extraction errors crash the whole batch | One bad PDF stops 199 others from processing | Catch per-file errors, log them, continue the batch; report a summary at the end |
| No way to see what was extracted vs. what was missed | Users cannot validate extraction quality | Output a per-policy extraction report showing which fields were populated, which were null |
| CLI requires exact field names for querying | Non-technical staff cannot use the tool | Provide a `query` subcommand with human-readable aliases; defer this to v2 if needed |

---

## "Looks Done But Isn't" Checklist

- [ ] **Scanned PDF support:** Demo works on one clean scan — verify on a low-DPI, skewed scan from each insurer
- [ ] **Multi-insured extraction:** Works for single-insured — verify on a life policy with 4 family members
- [ ] **Currency normalization:** MXN amounts extracted correctly — verify on a policy with European decimal notation (period as thousands separator, comma as decimal)
- [ ] **Date normalization:** Dates stored correctly — verify a policy where both DD/MM/YYYY and YYYY-MM-DD appear on the same document
- [ ] **Null fields:** Required fields are populated — verify that optional fields return `null`, not an empty string or invented placeholder
- [ ] **Batch error handling:** One bad PDF does not stop the batch — intentionally feed a password-protected PDF into the batch
- [ ] **Provenance stored:** Extracted data is in DB — verify that `model_id`, `prompt_version`, and `source_file_hash` are also stored
- [ ] **Duplicate guard:** First extraction succeeds — re-submit the same file and verify no duplicate record is created
- [ ] **Token logging:** Extraction works — verify that token usage per call is being logged for cost monitoring

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong extractions stored without validation | HIGH | (1) Build validation layer; (2) identify affected records by checking null/string values in numeric fields; (3) re-extract from original PDFs; (4) diff old vs new and reconcile manually |
| Flat schema for multi-insured, needs migration | HIGH | (1) Create new related tables; (2) migrate existing single-insured records; (3) re-extract multi-insured policies; (4) update all queries and API responses |
| No provenance — cannot identify which records need re-extraction | MEDIUM | (1) Add provenance columns with a default "unknown" marker; (2) re-extract all records to populate provenance going forward; (3) manually audit records created before provenance was added |
| Dates stored as mixed-format strings | MEDIUM | (1) Parse all existing date strings with a lenient multi-format parser; (2) re-store as ISO 8601; (3) flag records where format was ambiguous for manual review |
| API key exposed in git history | HIGH | (1) Immediately rotate the API key in Anthropic console; (2) use `git filter-repo` to remove from history; (3) force-push; (4) audit API usage logs for unauthorized calls |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Scanned PDFs sent raw to LLM | Phase 1 — PDF ingestion routing | Spot-check 5 scanned policies from different insurers; numerical fields must match source |
| No output schema validation | Phase 1 (schema) + Phase 2 (extraction) | All extraction responses validated with Pydantic; no raw `json.loads()` calls |
| Generic prompt fails on minority layouts | Phase 2 — classification + targeted prompts | Run golden dataset test suite; completeness >= 90% across all insurer types |
| Uncontrolled API costs | Phase 2 — token budget design | Log average tokens per call; assert < 25,000 tokens for standard policy |
| Date/currency format inconsistency | Phase 1 — canonical schema definition | Query DB for all date formats; assert 100% ISO 8601 |
| No provenance metadata | Phase 1 — database schema | Every record in DB has non-null `model_id`, `prompt_version`, `source_file_hash` |
| Model drift / no regression tests | Phase 2 — golden dataset | Automated test suite runs on 20-30 sample PDFs; completeness metric reported |
| Multi-insured flat schema | Phase 1 — database schema | Test with a gastos médicos family policy; verify 4 separate insured rows created |

---

## Sources

- [LLMs for Structured Data Extraction from PDFs in 2026 — Unstract](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/)
- [Extracting PDF Data for LLM Processing — Datavise](https://www.datavise.ai/blog/extracting-pdf-data-for-llm-processing-tools-techniques-and-intelligent-routing)
- [PDF Hell and Practical RAG Applications — Unstract](https://unstract.com/blog/pdf-hell-and-practical-rag-applications/)
- [Don't Use LLMs as OCR: Lessons Learned — Medium (Marta Fernandez)](https://medium.com/@martia_es/dont-use-llms-as-ocr-lessons-learned-from-extracting-complex-documents-db2d1fafcdfb)
- [Using LLMs for OCR and PDF Parsing — Cradl AI](https://www.cradl.ai/posts/llm-ocr)
- [Best OCR for Insurance Document Processing in 2025 — Unstract](https://unstract.com/blog/best-ocr-for-insurance-document-processing-automation/)
- [Real-Time Error Detection for LLM Structured Outputs — Cleanlab](https://cleanlab.ai/blog/tlm-structured-outputs-benchmark/)
- [Confidence Signals: LLM Alternative to Confidence Scores — Sensible](https://www.sensible.so/blog/confidence-signals)
- [Why PDF to Markdown Fails for LLM-Based Document Extraction — Unstract](https://unstract.com/blog/why-pdf-to-markdown-ocr-fails-for-ai-document-processing/)
- [PDF Support — Claude Official Docs](https://platform.claude.com/docs/en/build-with-claude/pdf-support)
- [Batch Processing — Claude Official Docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Rate Limits — Claude Official Docs](https://platform.claude.com/docs/en/api/rate-limits)
- [Prompt Drift: What It Is and How to Detect It — Agenta](https://agenta.ai/blog/prompt-drift)
- [LLM Model Drift: Detect, Prevent, and Mitigate Failures — By AI Team](https://byaiteam.com/blog/2025/12/30/llm-model-drift-detect-prevent-and-mitigate-failures/)
- [The State of PDF Parsing: 800+ Documents and 7 Frontier LLMs — Applied AI](https://www.applied-ai.com/briefings/pdf-parsing-benchmark/)
- [LLM API Cost Pitfalls — AI Accelerator Institute](https://www.aiacceleratorinstitute.com/llm-economics-how-to-avoid-costly-pitfalls/)
- [Taming LLM API Costs in Production — Medium (Ajay Verma)](https://medium.com/@ajayverma23/taming-the-beast-cost-optimization-strategies-for-llm-api-calls-in-production-11f16dbe2c39)
- [How to Extract Data from Insurance Policies — Klearstack](https://klearstack.com/insurance-data-extraction)
- [Data Extraction in Insurance: Best Practices — Docsumo](https://www.docsumo.com/blogs/data-extraction/insurance-industry)

---
*Pitfalls research for: Insurance PDF extraction system with Claude API*
*Researched: 2026-03-17*
