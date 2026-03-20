"""Extraction layer — Claude API calls and structured output parsing (Phase 3)."""

from __future__ import annotations

import anthropic
from loguru import logger

from policy_extractor.config import settings
from policy_extractor.extraction.prompt import assemble_text_v2, PROMPT_VERSION_V2
from policy_extractor.extraction.schema_builder import TOOL_NAME
from policy_extractor.extraction.client import extract_with_retry
from policy_extractor.extraction.verification import verify_no_hallucination
from policy_extractor.schemas.ingestion import IngestionResult
from policy_extractor.schemas.poliza import PolicyExtraction

__all__ = ["extract_policy", "PROMPT_VERSION_V2", "TOOL_NAME"]


def extract_policy(
    ingestion_result: IngestionResult, model: str | None = None
) -> tuple[PolicyExtraction | None, anthropic.types.Usage | None, int]:
    """Extract structured policy data from an IngestionResult using Claude.

    Assembles text from all PDF pages, calls the Anthropic API with forced
    tool_use, validates the response against PolicyExtraction, runs post-hoc
    hallucination verification, and returns the final PolicyExtraction along
    with the API usage data and the number of rate limit retries used.

    The raw API response dict is stored in
    ``result.campos_adicionales["_raw_response"]`` for auditing.

    Args:
        ingestion_result: IngestionResult produced by the ingestion layer.
        model: Optional Claude model ID override. Defaults to settings.EXTRACTION_MODEL.

    Returns:
        3-tuple of (PolicyExtraction, Usage, rl_retries) on success,
        or (None, None, 0) on failure.
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    assembled_text = assemble_text_v2(ingestion_result)
    effective_model = model or settings.EXTRACTION_MODEL

    outcome = extract_with_retry(
        client,
        assembled_text,
        ingestion_result.file_hash,
        effective_model,
        settings.EXTRACTION_MAX_RETRIES,
    )

    if outcome is None:
        logger.error(
            f"Extraction failed for {ingestion_result.file_path} "
            f"(hash={ingestion_result.file_hash})"
        )
        return (None, None, 0)

    policy, raw_response, usage, rl_retries = outcome

    # Run post-hoc hallucination verification
    verified_policy = verify_no_hallucination(policy, assembled_text)

    # Store raw API response for auditing
    campos = dict(verified_policy.campos_adicionales)
    campos["_raw_response"] = raw_response
    verified_policy = verified_policy.model_copy(update={"campos_adicionales": campos})

    return (verified_policy, usage, rl_retries)
