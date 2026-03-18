"""Prompt templates and text assembly for Claude extraction (Phase 3)."""

from policy_extractor.schemas.ingestion import IngestionResult

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
