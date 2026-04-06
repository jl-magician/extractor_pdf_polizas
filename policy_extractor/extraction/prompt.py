"""Prompt templates and text assembly for Claude extraction.

Version history:
  v1.0.0 — original prompt (Phase 3)
  v2.0.0 — explicit field-mapping rules, Zurich overlay, financial page tagging (Phase 13)
"""

from policy_extractor.schemas.ingestion import IngestionResult

# ---------------------------------------------------------------------------
# v1.0.0 — kept for historical reference and existing tests
# ---------------------------------------------------------------------------

PROMPT_VERSION_V1 = "v1.0.0"

SYSTEM_PROMPT_V1 = """You are an expert insurance data extractor. Your task is to extract all available structured data from insurance policy documents.

## Instructions

Call the `extract_policy` tool with all fields you can extract from the provided policy text. Do not produce any other output — only call the tool.

## Extraction Rules

1. **Extract only what is explicitly stated**: Return null for any field that is absent or cannot be determined from the document. Do not guess.
2. **NEVER invent, guess, or hallucinate values**: A null value is always better than an incorrect value. If you are uncertain, return null.
3. **Handle both Spanish and English documents**: The same field may appear with different labels depending on the language of the document.
4. **Classify aseguradora and tipo_seguro**: Identify the insurance company name and the type of insurance from context clues (logos, headers, policy type mentions) even if not explicitly labeled.
5. **Report confidence per field**: For every field you populate, add an entry to the `confianza` dict with the field name as key and one of the following values:
   - `"high"`: The value is clearly and unambiguously stated in the document.
   - `"medium"`: The value was inferred from context, partially stated, or reconstructed from related information.
   - `"low"`: The value is ambiguous, reconstructed from incomplete information, or based on uncertain interpretation.

## Spanish Insurance Terminology Glossary

Use these mappings when reading Spanish-language documents:

| Spanish Term | Field |
|---|---|
| Póliza / Número de Póliza / No. de Póliza | numero_poliza |
| Prima Total / Prima Neta / Costo Total | prima_total |
| Vigencia / Período de Vigencia | inicio_vigencia + fin_vigencia |
| Inicio de Vigencia / Desde | inicio_vigencia |
| Fin de Vigencia / Hasta | fin_vigencia |
| Fecha de Emisión / Fecha de Expedición | fecha_emision |
| Deducible | deducible |
| Suma Asegurada / Suma Máxima Asegurada | suma_asegurada |
| Contratante / Titular / Tomador | nombre_contratante |
| Asegurado / Beneficiario | asegurados entries |
| Agente / Promotor / Ejecutivo | nombre_agente |
| Forma de Pago / Modalidad de Pago | forma_pago |
| Periodicidad de Pago / Frecuencia de Pago | frecuencia_pago |
| Moneda / Divisa | moneda |
| Cobertura / Beneficio | coberturas entries |
| Aseguradora / Compañía Aseguradora | aseguradora |
| Tipo de Seguro / Ramo / Producto | tipo_seguro |

## Additional Instructions

- For `asegurados`, capture all insured persons and assets listed in the policy.
- For `coberturas`, capture each coverage line with its limits and deductibles.
- For `campos_adicionales`, include any other policy-specific fields not captured by the schema.
- Dates should be in ISO 8601 format (YYYY-MM-DD) when possible, but also accept DD/MM/YYYY or MM/DD/YYYY as they appear in the document.
- Monetary values should be numeric (no currency symbols or commas).
"""


def assemble_text(ingestion: IngestionResult) -> str:
    """Assemble all pages from an IngestionResult into a single text block.

    Each page is preceded by a separator line indicating the page number.
    Pages are joined with double newlines.

    Args:
        ingestion: IngestionResult containing list of PageResult objects.

    Returns:
        Concatenated text of all pages with page markers.
    """
    parts = []
    for page in ingestion.pages:
        parts.append(f"--- Page {page.page_num} ---")
        parts.append(page.text)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# v2.0.0 — explicit field-mapping rules, Zurich overlay, financial page tagging
# ---------------------------------------------------------------------------

PROMPT_VERSION_V2 = "v2.2.0"

SYSTEM_PROMPT_V2 = """You are an expert insurance data extractor. Your task is to extract all available structured data from insurance policy documents.

## Instructions

Call the `extract_policy` tool with all fields you can extract from the provided policy text. Do not produce any other output — only call the tool.

## Extraction Rules

1. **Extract only what is explicitly stated**: Return null for any field that is absent or cannot be determined from the document. Do not guess.
2. **NEVER invent, guess, or hallucinate values**: A null value is always better than an incorrect value. If you are uncertain, return null.
3. **Handle both Spanish and English documents**: The same field may appear with different labels depending on the language of the document.
4. **Classify aseguradora and tipo_seguro**: Identify the insurance company name and the type of insurance from context clues (logos, headers, policy type mentions) even if not explicitly labeled.
5. **Report confidence per field**: For every field you populate, add an entry to the `confianza` dict with the field name as key and one of the following values:
   - `"high"`: The value is clearly and unambiguously stated in the document.
   - `"medium"`: The value was inferred from context, partially stated, or reconstructed from related information.
   - `"low"`: The value is ambiguous, reconstructed from incomplete information, or based on uncertain interpretation.

## Financial Breakdown Field Mapping (CRITICAL)

The tool has DEDICATED top-level fields for the financial breakdown. You MUST use these fields — do NOT put financial values in campos_adicionales.

Map each financial row from the PDF to the correct top-level field by reading the ROW LABEL:

| PDF Label (any of these) | Tool Field | Description |
|---|---|---|
| Prima Neta, Prima Neta de Riesgo | **prima_neta** | Net premium before taxes/surcharges |
| Prima Total, Costo Total, Total a Pagar | **prima_total** | Total premium (sum of all charges) |
| Gastos de Expedición, Gasto de Expedición, Derecho de Póliza, Derechos | **derecho_poliza** | Policy issuance fee |
| Recargo, Recargo por Pago Fraccionado, Financiamiento, Recargos | **recargo** | Financing surcharge |
| Descuento, Bonificación, Descuentos | **descuento** | Discount (always positive number) |
| IVA, I.V.A., Impuesto al Valor Agregado | **iva** | Tax amount |
| Otros Servicios Contratados, Otros Cargos, Servicios Adicionales | **otros_cargos** | Additional contracted services charge |
| Primer Pago, Pago Inicial, 1er Pago | **primer_pago** | First payment amount |
| Pagos Subsecuentes, Subsecuentes, Pago Subsecuente | **pago_subsecuente** | Subsequent payment amount |

**IMPORTANT**: These are TOP-LEVEL fields in the tool schema. Do NOT create alternative names like "gasto_expedicion", "recargo_pago_fraccionado", "porcentaje_iva", etc. in campos_adicionales. Always use the exact field names from the table above.

When a page is tagged with [FINANCIAL BREAKDOWN TABLE BELOW], pay extra attention to column headers and row labels in that page's table structure.

Other field disambiguation:

| Field Name | What It Is | What It Is NOT |
|---|---|---|
| folio | Folio identifier (may be null) | NOT clave |
| clave | Agent/branch code (typically 5-digit numeric like "75534") | NOT folio |
| numero_poliza | The policy number on the document | NOT numero_cotizacion (quote number) |

## Vehicle Identification Fields

- `numero_serie`: Use the VEHICLE IDENTIFICATION NUMBER (VIN/NIV) from the vehicle data section, NOT the engine serial number.
- `modelo`: Use the exact model name as printed in the document (e.g., "Jetta", "Sentra"). Do NOT guess or infer from other context.

## Spanish Insurance Terminology Glossary

Use these mappings when reading Spanish-language documents:

| Spanish Term | Field |
|---|---|
| Poliza / Numero de Poliza / No. de Poliza | numero_poliza |
| Prima Total / Costo Total | prima_total |
| Prima Neta | prima_neta (NOT prima_total) |
| Derecho de Poliza / Gastos de Expedicion / Derechos | derecho_poliza |
| Recargo / Financiamiento / Recargo por Pago Fraccionado | recargo |
| Descuento / Bonificacion | descuento |
| IVA / Impuesto al Valor Agregado | iva |
| Otros Servicios Contratados / Otros Cargos | otros_cargos |
| Primer Pago / Pago Inicial | primer_pago |
| Pagos Subsecuentes / Subsecuentes | pago_subsecuente |
| Vigencia / Periodo de Vigencia | inicio_vigencia + fin_vigencia |
| Inicio de Vigencia / Desde | inicio_vigencia |
| Fin de Vigencia / Hasta | fin_vigencia |
| Fecha de Emision / Fecha de Expedicion | fecha_emision |
| Deducible | deducible |
| Suma Asegurada / Suma Maxima Asegurada | suma_asegurada |
| Contratante / Titular / Tomador | nombre_contratante |
| Asegurado / Beneficiario | asegurados entries |
| Agente / Promotor / Ejecutivo | nombre_agente |
| Forma de Pago / Modalidad de Pago | forma_pago |
| Periodicidad de Pago / Frecuencia de Pago | frecuencia_pago |
| Moneda / Divisa | moneda |
| Cobertura / Beneficio | coberturas entries |
| Aseguradora / Compania Aseguradora | aseguradora |
| Tipo de Seguro / Ramo / Producto | tipo_seguro |

## Additional Instructions

- For `asegurados`, capture all insured persons and assets listed in the policy.
- For `coberturas`, capture each coverage line with its limits and deductibles.
- For `campos_adicionales`, include only policy-specific fields that carry meaningful data. Omit generic labels, section headers, and decorative text.
- Dates should be in ISO 8601 format (YYYY-MM-DD) when possible, but also accept DD/MM/YYYY or MM/DD/YYYY as they appear in the document.
- Monetary values should be numeric (no currency symbols or commas).
"""

ZURICH_OVERLAY = """
## Zurich-Specific Extraction Rules

The following field pairs are commonly confused in Zurich auto policy breakdown tables.
Map them precisely by column position and ROW LABEL, not by proximity to adjacent values:

- `recargo`: The financing/surcharge row. In Zurich policies this is labeled "Financiamiento". Value is 0.0 when no financing plan is active. Do NOT confuse with otros_cargos.
- `otros_cargos`: The "Otros Servicios Contratados" row. This is a SEPARATE charge from recargo/financiamiento. Map it to the `otros_cargos` field, NOT to `recargo`.
- `folio`: The folio identifier (typically null for standard auto policies). Do NOT populate with clave values.
- `clave`: The clave identifier (typically a 5-digit numeric code like "75534"). This is the agent/branch code. NOT the same as folio.
- `pago_subsecuente`: Subsequent payment amount. Returns 0.0 when payment is annual (single payment). Do NOT copy primer_pago value into pago_subsecuente.
- `numero_serie`: Use the VIN/NIV from the vehicle data section. Do NOT use the engine serial number ("No. de Motor").
"""

# Insurer name patterns for overlay detection
_INSURER_OVERLAYS: dict[str, str] = {
    "zurich": ZURICH_OVERLAY,
}


def detect_insurer(assembled_text: str) -> str | None:
    """Lightweight first-pass insurer detection from assembled PDF text.

    Checks for insurer name patterns in the text (case-insensitive).
    Returns the insurer key if found, None otherwise.

    Args:
        assembled_text: Full assembled text from all PDF pages.

    Returns:
        Lowercase insurer key (e.g., "zurich") if detected, None otherwise.
    """
    text_lower = assembled_text.lower()
    for insurer_key in _INSURER_OVERLAYS:
        if insurer_key in text_lower:
            return insurer_key
    return None


def get_system_prompt(assembled_text: str) -> str:
    """Return SYSTEM_PROMPT_V2 with insurer overlay and learned rules appended.

    Args:
        assembled_text: Full assembled text from all PDF pages (used for insurer detection).

    Returns:
        SYSTEM_PROMPT_V2 + overlay (if detected) + learned rules (if any).
    """
    from policy_extractor.extraction.rules import get_rules_prompt

    prompt = SYSTEM_PROMPT_V2
    insurer = detect_insurer(assembled_text)
    if insurer and insurer in _INSURER_OVERLAYS:
        prompt += "\n\n" + _INSURER_OVERLAYS[insurer]
    rules_section = get_rules_prompt()
    if rules_section:
        prompt += rules_section
    return prompt


# Financial page detection keywords for [FINANCIAL BREAKDOWN TABLE BELOW] tagging
_FINANCIAL_KEYWORDS = [
    "prima",
    "pago",
    "financiamiento",
    "desglose",
    "breakdown",
    "importe",
    "subtotal",
    "recargo",
    "derecho de poliza",
]


def _restructure_financial_table(text: str) -> str:
    """Detect and restructure multi-column financial tables that get scrambled by PDF text extraction.

    Zurich (and similar insurers) use a 3-column financial summary table where
    PyMuPDF's get_text() reads labels column-by-column then values separately,
    producing incorrect label-value associations.

    This function detects the known label pattern and re-emits structured
    label: value lines using positional matching.
    """
    import re

    # Known 3-column Zurich financial table labels (row-major order)
    # Row 1: Prima Neta | Otros Serv. Contratados | Cesión de Comisión
    # Row 2: Financiamiento | Gastos Expedición | I.V.A.
    # Row 3: Prima Total | 1er. Pago | Subsecuentes
    _ROW_LABELS = [
        ["Prima Neta", "Otros Serv. Contratados", r"Cesi[oó]n de Comisi[oó]n"],
        ["Financiamiento", r"Gastos Expedici[oó]n", r"I\.V\.A\."],
        ["Prima Total", r"1er\. Pago", "Subsecuentes"],
    ]

    # Check if this page has the Zurich financial table pattern
    text_lower = text.lower()
    markers = ["prima neta", "financiamiento", "otros serv", "gastos expedic"]
    if not all(m in text_lower for m in markers):
        return text

    # Extract all dollar amounts from the text (in order of appearance)
    amounts = re.findall(r'[\d,]+\.\d{2}', text)
    if len(amounts) < 9:
        return text  # Not enough values to restructure

    # Build restructured table: labels in row-major order, values in column-major order
    # PDF values appear column-major: col1_row1, col2_row1, col3_row1, col1_row2, ...
    # which is actually row-major since text reads left-to-right per row
    friendly_labels = [
        "Prima Neta", "Otros Serv. Contratados", "Cesion de Comision",
        "Financiamiento", "Gastos Expedicion", "I.V.A.",
        "Prima Total", "1er. Pago", "Subsecuentes",
    ]

    restructured = "\n[FINANCIAL SUMMARY - RESTRUCTURED FROM MULTI-COLUMN TABLE]\n"
    for i, label in enumerate(friendly_labels):
        if i < len(amounts):
            restructured += f"  {label}: ${amounts[i]}\n"

    # Remove the original scrambled financial section and append the restructured version
    # Find the region between "Resumen de Valores" (or "Prima Neta") and "Coberturas Amparadas"
    start_match = re.search(r'(?:Resumen de Valores|Prima Neta)', text)
    end_match = re.search(r'Coberturas Amparadas', text)

    if start_match and end_match:
        before = text[:start_match.start()]
        after = text[end_match.start():]
        return before + restructured + "\n" + after

    return text + "\n" + restructured


def assemble_text_v2(ingestion: IngestionResult) -> str:
    """Assemble all pages with financial breakdown table hints (D-05).

    Each page is preceded by a separator line. Pages containing financial
    keywords get a [FINANCIAL BREAKDOWN TABLE BELOW] hint to guide Claude's
    column-to-field mapping in breakdown tables.

    Multi-column financial tables (e.g. Zurich) are restructured into
    clear label: value lines to prevent column-swap errors.

    Args:
        ingestion: IngestionResult containing list of PageResult objects.

    Returns:
        Concatenated text of all pages with page markers and optional financial hints.
    """
    parts = []
    for page in ingestion.pages:
        text = page.text
        text_lower = text.lower()
        has_financial = any(kw in text_lower for kw in _FINANCIAL_KEYWORDS)
        parts.append(f"--- Page {page.page_num} ---")
        if has_financial:
            text = _restructure_financial_table(text)
            parts.append("[FINANCIAL BREAKDOWN TABLE BELOW]")
        parts.append(text)
    return "\n\n".join(parts)
