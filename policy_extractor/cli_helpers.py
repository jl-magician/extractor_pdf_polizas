"""CLI helper utilities for idempotency checking and cost estimation (Phase 4)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from policy_extractor.storage.models import Poliza

# Pricing in USD per 1,000,000 tokens (input/output separately)
PRICING = {
    "haiku": {"input": 1.00, "output": 5.00},
    "sonnet": {"input": 3.00, "output": 15.00},
}


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate estimated USD cost from token counts using hardcoded pricing.

    Args:
        model_id: Claude model ID string (e.g., "claude-haiku-4-5-20251001").
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens used.

    Returns:
        Estimated cost in USD as a float.
    """
    pricing_key = "sonnet" if "sonnet" in model_id.lower() else "haiku"
    rates = PRICING[pricing_key]
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


def is_already_extracted(session: Session, file_hash: str) -> bool:
    """Check if a source file has already been extracted with the current prompt.

    Returns True only if a poliza exists for this file hash AND its
    prompt_version matches the current PROMPT_VERSION_V2. If the prompt
    has been updated since the last extraction, returns False so the
    file gets re-extracted with the new prompt.

    Args:
        session: Active SQLAlchemy session.
        file_hash: SHA-256 hex digest of the source PDF file.

    Returns:
        True if an up-to-date extraction record exists, False otherwise.
    """
    from policy_extractor.extraction.prompt import PROMPT_VERSION_V2

    row = session.execute(
        select(Poliza.id, Poliza.prompt_version)
        .where(Poliza.source_file_hash == file_hash)
        .limit(1)
    ).first()
    if row is None:
        return False
    return row.prompt_version == PROMPT_VERSION_V2
