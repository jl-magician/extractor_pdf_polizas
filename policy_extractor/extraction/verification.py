"""Post-hoc hallucination verification for extracted policy fields (Phase 3)."""

from loguru import logger

from policy_extractor.schemas.poliza import PolicyExtraction


def verify_no_hallucination(
    policy: PolicyExtraction,
    source_text: str,
) -> PolicyExtraction:
    """Downgrade confianza to 'low' for key fields not found in source text.

    Checks numero_poliza and aseguradora against the assembled source text.
    If a field value cannot be found in the source, its confidence is set to
    'low' regardless of what Claude originally reported.

    Args:
        policy: PolicyExtraction as returned by the API call.
        source_text: Full assembled text from all PDF pages.

    Returns:
        New PolicyExtraction with updated confianza dict.
    """
    confianza = dict(policy.confianza)

    key_fields = [
        ("numero_poliza", policy.numero_poliza),
        ("aseguradora", policy.aseguradora),
    ]

    for field_name, value in key_fields:
        if value is not None and value.lower() not in source_text.lower():
            confianza[field_name] = "low"
            logger.warning(
                f"Possible hallucination: {field_name}='{value}' not found in source text"
            )

    return policy.model_copy(update={"confianza": confianza})
