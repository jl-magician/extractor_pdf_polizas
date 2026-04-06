"""Build simplified JSON schema for the Claude extraction tool (Phase 3).

Removes provenance fields (set programmatically) and simplifies Decimal
field schemas to avoid regex pattern noise in the tool definition.
"""

from policy_extractor.schemas.poliza import PolicyExtraction

TOOL_NAME = "extract_policy"

# Provenance fields are set programmatically after extraction — Claude must not set them.
_PROVENANCE_FIELDS = {"source_file_hash", "model_id", "prompt_version", "extracted_at"}


def _simplify_decimal_property(prop: dict, title: str) -> dict:
    """Replace a Pydantic Decimal property with a clean number/null schema."""
    return {
        "anyOf": [{"type": "number"}, {"type": "null"}],
        "default": None,
        "title": title,
    }


def build_extraction_schema() -> dict:
    """Build a simplified JSON schema for PolicyExtraction suitable for Claude tool use.

    Transformations applied:
    - Remove provenance fields (source_file_hash, model_id, prompt_version, extracted_at)
    - Simplify top-level prima_total to number/null (avoids Decimal regex noise)
    - Simplify CoberturaExtraction.suma_asegurada and .deducible to number/null
    - Ensure confianza has a clear description and additionalProperties constraint

    Returns:
        dict: Cleaned JSON schema dict for use as input_schema in a Claude tool.
    """
    schema = PolicyExtraction.model_json_schema()

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # 1. Remove provenance fields from properties and required
    for field in _PROVENANCE_FIELDS:
        properties.pop(field, None)
        if field in required:
            required.remove(field)

    # 2. Simplify top-level Decimal fields
    _DECIMAL_FIELDS = [
        "prima_total", "prima_neta", "derecho_poliza", "recargo",
        "descuento", "iva", "otros_cargos", "primer_pago", "pago_subsecuente",
    ]
    for field_name in _DECIMAL_FIELDS:
        if field_name in properties:
            title = properties[field_name].get("title", field_name.replace("_", " ").title())
            properties[field_name] = _simplify_decimal_property(properties[field_name], title)

    # 3. Simplify Decimal fields inside CoberturaExtraction definition
    defs = schema.get("$defs", {})
    cobertura_def = defs.get("CoberturaExtraction", {})
    cobertura_props = cobertura_def.get("properties", {})

    for field_name in ("suma_asegurada", "deducible"):
        if field_name in cobertura_props:
            title = cobertura_props[field_name].get("title", field_name.replace("_", " ").title())
            cobertura_props[field_name] = _simplify_decimal_property(
                cobertura_props[field_name], title
            )

    # 4. Ensure confianza has a clear description and additionalProperties
    if "confianza" in properties:
        properties["confianza"]["description"] = (
            "Confidence level per field: 'high' | 'medium' | 'low'"
        )
        properties["confianza"]["additionalProperties"] = {"type": "string"}

    schema["properties"] = properties
    if required:
        schema["required"] = required
    elif "required" in schema:
        del schema["required"]

    return schema


def build_extraction_tool() -> dict:
    """Build the complete Claude tool definition for insurance policy extraction.

    Returns:
        dict: Tool definition with name, description, and input_schema.
    """
    return {
        "name": TOOL_NAME,
        "description": "Extract all available fields from an insurance policy document.",
        "input_schema": build_extraction_schema(),
    }
