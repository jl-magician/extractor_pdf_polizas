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

PROMPT_VERSION_V2 = "v2.0.0"

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

When extracting values from financial breakdown tables, map each row to its correct field by reading the ROW LABEL, not by position or proximity. Common confused pairs:

| Field Name | What It Is | What It Is NOT |
|---|---|---|
| financiamiento | Financing charge (often 0.0 when no financing plan) | NOT otros_servicios |
| otros_servicios_contratados | Additional contracted services charge | NOT financiamiento |
| primer_pago | First payment amount | NOT subsecuentes |
| subsecuentes | Subsequent payment amount (0.0 for annual/single payment) | NOT primer_pago |
| prima_total | Total premium amount | NOT prima_neta or recargo |
| prima_neta | Net premium before surcharges | NOT prima_total |
| folio | Folio identifier (may be null) | NOT clave |
| clave | Agent/branch code (typically 5-digit numeric like "75534") | NOT folio |
| numero_poliza | The policy number on the document | NOT numero_cotizacion (quote number) |

When a page is tagged with [FINANCIAL BREAKDOWN TABLE BELOW], pay extra attention to column headers and row labels in that page's table structure.

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

- `financiamiento`: The financing charge row. Value is 0.0 when no financing plan is active. Do NOT confuse with otros_servicios_contratados.
- `otros_servicios_contratados`: Additional contracted services charge. This is the row labeled "Otros Servicios Contratados" or similar. NOT the same as financiamiento.
- `folio`: The folio identifier (typically null for standard auto policies). Do NOT populate with clave values.
- `clave`: The clave identifier (typically a 5-digit numeric code like "75534"). This is the agent/branch code. NOT the same as folio.
- `subsecuentes`: Subsequent payment amount. Returns 0.0 when payment is annual (single payment). Do NOT copy primer_pago value into subsecuentes.
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
    """Return SYSTEM_PROMPT_V2 with insurer-specific overlay appended if detected.

    Args:
        assembled_text: Full assembled text from all PDF pages (used for insurer detection).

    Returns:
        SYSTEM_PROMPT_V2 + overlay if detected, or just SYSTEM_PROMPT_V2 if not.
    """
    insurer = detect_insurer(assembled_text)
    if insurer and insurer in _INSURER_OVERLAYS:
        return SYSTEM_PROMPT_V2 + "\n\n" + _INSURER_OVERLAYS[insurer]
    return SYSTEM_PROMPT_V2


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


def assemble_text_v2(ingestion: IngestionResult) -> str:
    """Assemble all pages with financial breakdown table hints (D-05).

    Each page is preceded by a separator line. Pages containing financial
    keywords get a [FINANCIAL BREAKDOWN TABLE BELOW] hint to guide Claude's
    column-to-field mapping in breakdown tables.

    Args:
        ingestion: IngestionResult containing list of PageResult objects.

    Returns:
        Concatenated text of all pages with page markers and optional financial hints.
    """
    parts = []
    for page in ingestion.pages:
        text_lower = page.text.lower()
        has_financial = any(kw in text_lower for kw in _FINANCIAL_KEYWORDS)
        parts.append(f"--- Page {page.page_num} ---")
        if has_financial:
            parts.append("[FINANCIAL BREAKDOWN TABLE BELOW]")
        parts.append(page.text)
    return "\n\n".join(parts)
