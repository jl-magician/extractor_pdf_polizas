# Feature Research

**Domain:** Insurance policy PDF data extraction (AI-powered, local CLI, agency use)
**Researched:** 2026-03-17
**Confidence:** HIGH (corroborated across InsurGrid, KlearStack, Docsumo, GroupBWT, AltexSoft, AWS IDP documentation)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that an insurance agency expects to exist. Missing any of these = the system doesn't do its job.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Digital PDF text extraction | Modern PDFs have selectable text; not extracting it directly is a regression | LOW | Use PyMuPDF or pdfplumber; fast, no AI cost |
| Scanned PDF / image OCR | Many Mexican insurance policies are scanned; non-negotiable for this office | MEDIUM | OCR layer (e.g., Tesseract, pytesseract) before LLM; quality directly impacts accuracy |
| LLM-powered field extraction | Template-based parsers fail across 50-70 structures; AI is the only scalable path | MEDIUM | Claude API; structured JSON output via tool_use or response schema |
| Core field extraction: policy number, insurer, validity dates, premium | These are the first fields any agent asks about when looking up a policy | LOW | Validated across all competitor products as baseline |
| Insured party extraction (people and assets) | Every policy names at least one insured; multiple insured parties per policy is common | MEDIUM | Must handle both person entities and asset entities (vehicle, property, etc.) |
| Contractor / policyholder extraction | The contractor (contratante) is often different from the insured; critical for billing | LOW | Standard field in Mexican insurance documentation |
| Coverage extraction (type, amount, deductible) | Agencies compare coverage across carriers; without this the tool has no analytical value | HIGH | Nested/structured data; coverages vary widely by policy type; must handle lists |
| Payment information extraction | Installment schedules, payment method, total premium — needed for billing workflows | MEDIUM | Includes fractional premiums, payment frequency |
| Agent / producer extraction | Agencies need to know which agent is associated with each policy | LOW | Often a simple named field but sometimes embedded in header |
| Spanish and English language support | The document set is explicitly mixed-language | MEDIUM | Claude handles this natively; OCR layer needs multilingual mode |
| Structured JSON output | Downstream use (DB storage, future API, future web UI) requires structured data | LOW | Define a canonical schema; nest coverages and insured parties as arrays |
| Local database storage | 200+ policies/month requires searchable persistence, not just files | MEDIUM | SQLite is sufficient for v1; schema must accommodate variable fields per policy type |
| CLI for single and batch processing | The stated interface requirement; agents must process both individual and folder batches | LOW | Python CLI with argparse or Typer; batch reads a directory, processes all PDFs |
| Idempotent re-processing | Running the same PDF twice must not create duplicate records | LOW | Hash PDF content (SHA-256) as primary key before extraction |
| Processing status / progress feedback | Batch runs of 50+ PDFs need visible progress; blind processing is unusable | LOW | tqdm or simple print counters; structured status per-file output |
| Basic error reporting | When extraction fails or a file is corrupt, the user needs to know which file and why | LOW | Per-file error log; do not let one bad PDF abort the entire batch |

### Differentiators (Competitive Advantage)

Features that go beyond what the market baseline provides and create real value for this specific use case.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Confidence scoring per field | Tells the operator which extracted values are uncertain and need human review; reduces silent errors that become billing problems | MEDIUM | Claude can return a confidence flag per field alongside the value; enables human-in-the-loop triage |
| Extraction provenance / audit trail | Records which PDF produced which data, when, and with which model version; enables error tracing and re-extraction | MEDIUM | Store source_file, extraction_timestamp, model_version, raw_llm_output alongside structured data |
| Dynamic schema per policy type | Different insurers and policy types have different fields (auto vs. vida vs. GMM); forcing all into one rigid schema loses data | HIGH | Use a core schema + JSONB blob for extra fields; allows querying core fields while preserving everything |
| Multiple insured entities per policy | Policies can cover fleets (multiple vehicles) or families (multiple people); losing these is a functional failure | HIGH | Extract as an array; each entity has its own type, name, attributes |
| Raw LLM output storage | Storing the unprocessed LLM response enables re-parsing without re-calling the API when the schema evolves | LOW | Simple text column alongside structured fields; nearly zero cost |
| Insurer auto-detection | Identifying which of the 10 insurers issued a policy unlocks insurer-specific post-processing or field mapping | MEDIUM | Can be done with LLM as a classification step or rule-based on extracted company name |
| Extraction dry-run / preview mode | Shows what would be extracted before committing to DB; useful for validating new insurer formats | LOW | Print-to-console mode without DB write; easily implemented |
| JSON export per policy or batch | Enables downstream integrations without waiting for the future web API | LOW | Already follows from JSON output; add a --export flag |
| Re-extraction on schema change | When the data model evolves, re-run extraction on existing PDFs without paying re-OCR cost | MEDIUM | Separate OCR/text-extraction step (cached) from LLM-extraction step; only re-call LLM |
| Extraction quality report | After a batch run, summarize: N extracted OK, N with low-confidence fields, N failed | LOW | Aggregate the per-file status into a summary printed at end of run |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem desirable but introduce complexity, maintenance burden, or misaligned scope for v1.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Hard-coded per-insurer templates | Fast and accurate for known formats | Collapses under format changes; requires maintenance for every new insurer version; 50-70 structures makes this O(n) maintenance forever | Let Claude handle variation; use dynamic prompting with examples rather than rigid templates |
| Real-time processing webhook / streaming | "Extract as soon as a PDF lands" sounds fast | Adds infrastructure complexity (file watchers, queues, retry logic) not needed for 200/month at manual workflow pace | Batch CLI is sufficient; agents process in batches already |
| Web UI for data review and editing in v1 | Agents want to see and correct data visually | Web UI is a separate product scope; building it before validating extraction accuracy wastes effort | v1: CLI + JSON output. Flag low-confidence fields in output. Web UI is explicitly v2+ |
| ML model fine-tuning / local model | "Own the model" for cost or privacy | Fine-tuning requires labeled training data (not yet available), GPU infrastructure, and ongoing retraining; Claude API delivers far better accuracy with zero infrastructure | Use Claude API; costs ~$0.001-0.003 per policy at current pricing; entirely affordable at 200/month |
| Real-time confidence recalibration | Adaptive thresholds that learn from corrections | Requires labeled feedback loop, labeled corrections storage, and retraining pipeline — a full ML system, not an extraction tool | Set a fixed confidence threshold (e.g., flag fields below 0.80); adjust threshold manually after observing real error patterns |
| Direct insurer system integration | "Pull policies automatically from insurer portals" | Each insurer has different authentication, APIs, or lacks them entirely; legal and contractual concerns | Agents continue uploading PDFs; extraction is the automation win, not ingestion |
| Excel/CSV export in v1 | Agents are used to Excel | Export is trivially built on top of the database later; building it now before schema is validated wastes effort | Explicitly deferred to v2; JSON covers integration needs in v1 |
| Automatic policy renewal detection | "Flag policies expiring soon" | Requires date comparison logic, scheduler, and notification system — premature before core extraction is validated | Validity dates are extracted; agents can query/filter from the database themselves |

---

## Feature Dependencies

```
[OCR Pipeline (Tesseract/pytesseract)]
    └──required-by──> [LLM Extraction (Claude API)]
                          └──required-by──> [Structured JSON Output]
                                                └──required-by──> [Database Storage]
                                                └──required-by──> [JSON Export]

[PDF Ingestion (file read)]
    └──required-by──> [Digital Text Extraction (pdfplumber)]
    └──required-by──> [OCR Pipeline]

[PDF Hash Fingerprinting]
    └──required-by──> [Idempotent Re-processing]
    └──enables──> [Re-extraction on Schema Change (skip OCR, re-run LLM)]

[Database Storage]
    └──required-by──> [Extraction Quality Report]
    └──required-by──> [JSON Export (batch)]
    └──required-by──> [Future Web UI (v2+)]

[Confidence Scoring per Field]
    └──enhances──> [Extraction Quality Report]
    └──enhances──> [Human-in-the-Loop Review]

[Dynamic Schema]
    └──conflicts-with──> [Hard-Coded Per-Insurer Templates]
    └──required-by──> [Multiple Insured Entities per Policy]

[Raw LLM Output Storage]
    └──enables──> [Re-extraction on Schema Change]
```

### Dependency Notes

- **OCR Pipeline required by LLM Extraction:** Claude cannot read image-only PDFs; text must be materialized first via OCR before being passed in the prompt.
- **PDF Hash required by Idempotent Re-processing:** Without a fingerprint, the system cannot detect if the same PDF was already processed, causing duplicate records.
- **PDF Hash enables Re-extraction:** Cached OCR text (keyed by hash) means schema changes only require re-calling the LLM, not re-running OCR — saves time and cost.
- **Raw LLM Output Storage enables Re-extraction:** If the structured schema changes, the raw response can be re-parsed without an API call (if the new schema asks for a subset of already-extracted data).
- **Dynamic Schema required by Multiple Insured Entities:** A flat schema cannot represent a one-to-many relationship between a policy and its insured entities; the schema must support arrays/nested objects.
- **Confidence Scoring enhances Quality Report:** The quality report only becomes meaningful when it can summarize which fields had low confidence, not just which files errored.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — validates that the extraction approach works and produces usable structured data.

- [ ] Digital PDF text extraction (pdfplumber / PyMuPDF) — direct path for non-scanned PDFs; fast and accurate
- [ ] OCR pipeline for scanned PDFs (pytesseract + preprocessing) — required for the office's document mix
- [ ] Claude API extraction with structured JSON output — the core value proposition
- [ ] Core schema: policy number, insurer/company, contractor, insured parties (array), validity dates, premium, payment info, agent, coverages (array with type/amount/deductible), raw_llm_output
- [ ] PDF SHA-256 fingerprinting for idempotency — prevents duplicate records on re-run
- [ ] Local SQLite database storage — persistence for 200+/month
- [ ] CLI: single-file and batch-folder processing modes — stated project requirement
- [ ] Spanish and English language support — document set is mixed
- [ ] Per-file error handling and basic error log — batch runs must not abort on one bad file
- [ ] Progress feedback during batch runs — operator sanity for large batches
- [ ] Extraction status output: OK / low-confidence fields / failed — minimum visibility into extraction quality

### Add After Validation (v1.x)

Add once core extraction is working and schema has stabilized.

- [ ] Confidence scoring per field — add once we know which fields are reliably extracted and which are not; requires a few weeks of real data
- [ ] Extraction provenance logging (source_file, timestamp, model_version) — adds traceability; low complexity once schema is stable
- [ ] JSON export per policy or batch (--export flag) — useful for agent manual review; trivial add-on
- [ ] Dry-run / preview mode — useful for validating new insurers without committing to DB
- [ ] Insurer auto-detection as a discrete classification step — enables insurer-specific quality metrics
- [ ] Extraction quality summary report at end of batch — aggregate view of confidence/errors

### Future Consideration (v2+)

Defer until core extraction is validated and product-market fit is established.

- [ ] Web UI for data review and editing — explicitly out of scope per PROJECT.md; build on validated DB
- [ ] Excel / CSV export — trivial once DB is stable; deferred per PROJECT.md
- [ ] Re-extraction pipeline for schema migrations — needed when schema changes in v2; complexity not justified in v1
- [ ] Policy comparison features (side-by-side coverage analysis) — high value but requires stable schema and v2 UI
- [ ] Renewal / expiry alerting — requires scheduler; deferred until agents have validated the extracted dates
- [ ] Full REST API — v2+ per PROJECT.md; JSON CLI export covers v1 integration needs

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Digital text extraction | HIGH | LOW | P1 |
| OCR for scanned PDFs | HIGH | MEDIUM | P1 |
| Claude API extraction + JSON output | HIGH | MEDIUM | P1 |
| Core schema extraction (all required fields) | HIGH | MEDIUM | P1 |
| CLI batch + single processing | HIGH | LOW | P1 |
| SQLite database storage | HIGH | LOW | P1 |
| PDF hash idempotency | HIGH | LOW | P1 |
| Error handling + per-file status | HIGH | LOW | P1 |
| Spanish/English support | HIGH | LOW | P1 |
| Confidence scoring per field | HIGH | MEDIUM | P2 |
| Extraction provenance logging | MEDIUM | LOW | P2 |
| JSON export flag | MEDIUM | LOW | P2 |
| Dry-run / preview mode | MEDIUM | LOW | P2 |
| Extraction quality summary report | MEDIUM | LOW | P2 |
| Insurer auto-detection | MEDIUM | MEDIUM | P2 |
| Dynamic schema (JSONB extra fields) | MEDIUM | MEDIUM | P2 |
| Re-extraction pipeline (schema migration) | MEDIUM | HIGH | P3 |
| Web UI data review | HIGH | HIGH | P3 |
| Policy comparison / analytics | HIGH | HIGH | P3 |
| Renewal / expiry alerts | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch — without these, the system does not work
- P2: Should have — adds reliability and operator visibility; add when P1 is solid
- P3: Nice to have — deferred to v2+; builds on validated foundation

---

## Competitor Feature Analysis

| Feature | InsurGrid | KlearStack | Our Approach |
|---------|-----------|------------|--------------|
| Core field extraction | Yes, declaration pages only | Yes, all insurance docs | Same via Claude; broader document scope |
| Scanned PDF / OCR | Yes | Yes (multi-format) | Tesseract preprocessing + Claude |
| Multi-language | English-focused | 50+ languages | Claude handles Spanish/English natively |
| Template-free extraction | Yes (ML-trained) | Yes (AI/NLP) | Yes (Claude prompt-based, no templates) |
| Confidence scoring | Yes (real-time validation) | Implicit (99% accuracy claim) | Per-field confidence flag in LLM response |
| Human review workflow | Yes (portal review) | Yes (dashboard correction) | v1: low-confidence flags in CLI output; v2: UI |
| Structured JSON output | Yes (REST API) | Yes (REST API) | Yes (file + DB; future REST API v2) |
| Batch processing | Yes | Yes | Yes (CLI batch mode) |
| Carrier/insurer detection | Yes (350+ carriers) | Generic | Via extracted company name + optional classification |
| Multiple insured parties | Partial (decl pages) | Not specified | Explicit array in schema |
| Local/on-premise deployment | No (cloud SaaS) | No (cloud SaaS) | Yes (local-first, Windows) |
| Cost model | Per-user SaaS subscription | Per-page SaaS | Per-API-call (Claude); ~$0.001-0.003/policy |
| Mexican insurer support | Unknown (US-focused) | Generic | Native; prompt in Spanish supported |

**Key differentiation:** InsurGrid and KlearStack are cloud SaaS products with per-user pricing. This system is local-first, single-tenant, uses Claude API (pay-per-use at ~$0.001-0.003/policy at 200/month = ~$0.20-0.60/month in API costs), and is purpose-built for a Mexican agency's specific 10-insurer set with Spanish-primary documents.

---

## Sources

- [InsurGrid Policy Data Extraction](https://www.insurgrid.com/policy-data-extraction) — competitor feature baseline
- [InsurGrid AI Features](https://insurgrid.com/insurgrid-ai) — carrier detection, accuracy claims
- [KlearStack Insurance Data Extraction](https://klearstack.com/insurance-data-extraction) — competitor feature baseline
- [Insurance Data Extraction in 2026: Scaling AI Workflows & ROI](https://groupbwt.com/blog/data-extraction-insurance/) — governance requirements, workflow patterns
- [How to Extract Data from Insurance Policies in 2025](https://klearstack.com/insurance-data-extraction) — IDP pipeline overview
- [Intelligent Document Processing for Insurance - AltexSoft](https://www.altexsoft.com/blog/idp-intelligent-document-processing-insurance/) — IDP feature taxonomy
- [AI and Human-in-the-Loop - Applied Systems](https://www.insurancebusinessmag.com/us/news/technology/ai-and-humanintheloop-applied-systems-smarter-model-for-insurance-data-accuracy-558623.aspx) — confidence scoring and routing patterns
- [Best OCR for Insurance Document Processing 2025](https://unstract.com/blog/best-ocr-for-insurance-document-processing-automation/) — OCR considerations for mixed-quality PDFs
- [Intelligent Document Processing - Indico Data](https://indicodata.ai/intelligent-document-processing-for-property-and-casualty-insurance/) — IDP table stakes
- [Insurance Data Extraction - Docsumo](https://www.docsumo.com/blogs/data-extraction/insurance-industry) — field extraction standards

---
*Feature research for: Insurance PDF data extraction system (extractor_pdf_polizas)*
*Researched: 2026-03-17*
