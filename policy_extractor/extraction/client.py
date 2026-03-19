"""Anthropic API client with retry logic for policy extraction (Phase 3)."""

import random
import time
from datetime import datetime, timezone

import anthropic
from loguru import logger
from pydantic import ValidationError

from policy_extractor.schemas.poliza import PolicyExtraction
from policy_extractor.extraction.prompt import SYSTEM_PROMPT_V1, PROMPT_VERSION_V1
from policy_extractor.extraction.schema_builder import build_extraction_tool, TOOL_NAME

_RATE_LIMIT_MAX_RETRIES = 3
_RATE_LIMIT_BACKOFF = [2, 4, 8]  # seconds per retry attempt (0-indexed)


def call_extraction_api(
    client: anthropic.Anthropic,
    assembled_text: str,
    model: str,
    max_tokens: int = 4096,
) -> anthropic.types.Message:
    """Call the Anthropic API with forced tool_use to guarantee structured JSON output.

    Args:
        client: Authenticated Anthropic client.
        assembled_text: Assembled text from all PDF pages.
        model: Claude model ID to use (e.g., "claude-haiku-4-5-20251001").
        max_tokens: Maximum tokens in the response.

    Returns:
        Raw Message object from the Anthropic API.
    """
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT_V1,
        messages=[{"role": "user", "content": assembled_text}],
        tools=[build_extraction_tool()],
        tool_choice={"type": "tool", "name": TOOL_NAME},
    )


def parse_and_validate(
    message: anthropic.types.Message,
    ingestion_file_hash: str,
) -> tuple[PolicyExtraction, dict]:
    """Parse a tool_use message and validate as PolicyExtraction.

    Injects provenance fields (source_file_hash, model_id, prompt_version,
    extracted_at) into the extracted data before Pydantic validation.

    Args:
        message: Raw Message object from the Anthropic API.
        ingestion_file_hash: SHA-256 hash of the source PDF file.

    Returns:
        Tuple of (PolicyExtraction, raw_input_dict).

    Raises:
        ValueError: If message content is not a tool_use block.
        ValidationError: If the extracted data fails Pydantic validation.
    """
    if not message.content or message.content[0].type != "tool_use":
        raise ValueError(
            f"Expected tool_use response, got: "
            f"{message.content[0].type if message.content else 'empty content'}"
        )

    raw_input: dict = dict(message.content[0].input)

    # Inject provenance fields programmatically — Claude must not set these
    raw_input["source_file_hash"] = ingestion_file_hash
    raw_input["model_id"] = message.model
    raw_input["prompt_version"] = PROMPT_VERSION_V1
    raw_input["extracted_at"] = datetime.now(timezone.utc)

    policy = PolicyExtraction(**raw_input)
    return (policy, raw_input)


def extract_with_retry(
    client: anthropic.Anthropic,
    assembled_text: str,
    ingestion_file_hash: str,
    model: str,
    max_retries: int = 1,
    max_rate_limit_retries: int = 3,
) -> tuple[PolicyExtraction, dict, anthropic.types.Usage, int] | None:
    """Call the Anthropic API with one retry on ValidationError and rate limit retry.

    On the first ValidationError, appends the error details to the prompt
    and retries once. On a second failure (or any other exception), logs
    the error and returns None so batch processing can continue.

    Rate limit errors (RateLimitError, InternalServerError, APIConnectionError) are
    retried up to max_rate_limit_retries times with exponential backoff (2s, 4s, 8s)
    plus random jitter (0-1s) before the validation retry loop is attempted.

    Args:
        client: Authenticated Anthropic client.
        assembled_text: Assembled text from all PDF pages.
        ingestion_file_hash: SHA-256 hash of the source PDF file.
        model: Claude model ID to use.
        max_retries: Number of retries on validation failure (default 1).
        max_rate_limit_retries: Max retries for transient API errors (default 3).

    Returns:
        4-tuple of (PolicyExtraction, raw_response_dict, usage, rl_retries) on success,
        or None on failure.
    """
    current_text = assembled_text
    attempts = max_retries + 1  # total attempts = retries + 1
    rl_retries = 0

    for attempt in range(attempts):
        try:
            # --- Rate limit retry loop wrapping call_extraction_api ---
            message = None
            for rl_attempt in range(max_rate_limit_retries + 1):
                try:
                    message = call_extraction_api(client, current_text, model)
                    break  # API call succeeded
                except (
                    anthropic.RateLimitError,
                    anthropic.InternalServerError,
                    anthropic.APIConnectionError,
                ) as exc:
                    if rl_attempt >= max_rate_limit_retries:
                        raise  # exhausted retries, caught by outer except Exception
                    wait = _RATE_LIMIT_BACKOFF[rl_attempt] + random.uniform(0, 1)
                    rl_retries += 1
                    logger.warning(
                        "[RETRY] Rate limit/transient error (attempt %d/%d, waiting %.1fs): %s",
                        rl_attempt + 2,
                        max_rate_limit_retries + 1,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
            # ----------------------------------------------------------

            policy, raw_response = parse_and_validate(message, ingestion_file_hash)
            return (policy, raw_response, message.usage, rl_retries)
        except ValidationError as exc:
            logger.warning(
                f"Extraction attempt {attempt + 1}/{attempts} failed validation: {exc}"
            )
            if attempt < max_retries:
                # Append validation error to prompt and retry
                current_text = (
                    f"{current_text}\n\nIMPORTANT: Your previous response failed validation:\n"
                    f"{exc}\nPlease correct the fields and respond again."
                )
            else:
                logger.error(
                    f"Extraction failed after {attempts} attempt(s) — "
                    f"returning None. Final error: {exc}"
                )
                return None
        except Exception as exc:
            logger.error(
                f"Extraction attempt {attempt + 1}/{attempts} raised unexpected error: {exc}"
            )
            return None

    return None
