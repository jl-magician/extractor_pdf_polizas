"""Sonnet-powered quality evaluator for Haiku extractions (Phase 10).

Exports:
    evaluate_policy(ingestion_result, policy, model) -> EvaluationResult | None
    build_evaluation_tool() -> dict
    build_swap_warnings(evaluation_json) -> list[str]
    call_evaluation_api(client, assembled_text, extraction_json, model, max_tokens) -> Message
    EvaluationResult
    EVAL_MODEL_ID
    EVAL_TOOL_NAME
    LOW_SCORE_THRESHOLD
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import anthropic
from loguru import logger

from policy_extractor.config import settings
from policy_extractor.schemas.ingestion import IngestionResult
from policy_extractor.schemas.poliza import PolicyExtraction

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVAL_TOOL_NAME = "evaluate_policy"
EVAL_MODEL_ID = "claude-sonnet-4-5-20250514"
LOW_SCORE_THRESHOLD = 0.7

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

EVAL_SYSTEM_PROMPT = """Eres un auditor experto en calidad de extraccion de datos de polizas de seguros.
Tu tarea es evaluar la calidad de la extraccion que hizo un modelo de IA comparandola contra el texto original del PDF.

## Instrucciones

Llama a la herramienta `evaluate_policy` con tus evaluaciones. No produzcas otra salida — solo llama a la herramienta.

## Criterios de evaluacion

1. **completeness (0.0 - 1.0)**: Fraccion de campos visibles en el PDF que fueron capturados en la extraccion.
   - 1.0 = todos los campos visibles fueron extraidos
   - 0.0 = ningun campo fue extraido

2. **accuracy (0.0 - 1.0)**: Plausibilidad y correctitud de los valores extraidos.
   - Compara los valores extraidos contra el texto del PDF caracter por caracter para campos clave: numero_poliza, prima_total, fechas, nombre_contratante
   - 1.0 = todos los valores coinciden exactamente con el texto fuente
   - 0.0 = los valores son completamente incorrectos

3. **hallucination_risk (0.0 - 1.0)**: Fraccion de campos con datos inventados que NO aparecen en el PDF.
   - Marca cualquier valor que no aparezca verbatim o calculablemente en el texto fuente
   - 0.0 = ningun campo tiene datos inventados (deseable)
   - 1.0 = todos los campos tienen datos inventados

4. **flags**: Lista de problemas especificos encontrados, con el nombre del campo y una descripcion del problema.
   Escribe las descripciones de problemas en espanol ya que los terminos del dominio son en espanol.

5. **summary**: Resumen breve de la calidad general de la extraccion en espanol.

## Proceso de revision

1. Lee el texto del PDF con atencion
2. Verifica cada campo extraido contra el texto fuente
3. Identifica campos del PDF que no fueron capturados (afecta completeness)
4. Identifica valores que no corresponden al texto fuente (afecta accuracy y hallucination_risk)
5. Asigna puntajes objetivos basados en la evidencia

## Deteccion de intercambio de campos (campos_adicionales)

Revisa cada par clave-valor en campos_adicionales y evalua si el valor parece pertenecer a una clave diferente.

Indicadores de intercambio:
- Un valor numerico (como un monto o porcentaje) asignado a una clave que espera texto descriptivo
- Un nombre o descripcion asignado a una clave que espera un numero
- Un valor que coincide semanticamente mejor con otra clave presente en campos_adicionales
- Valores que parecen estar rotados entre claves adyacentes en una tabla

Para cada intercambio sospechado, reporta:
- source_key: la clave donde el valor esta actualmente
- target_key: la clave donde el valor deberia estar
- suspicious_value: el valor sospechoso
- reason: explicacion breve en espanol de por que sospechas el intercambio
"""

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class EvaluationResult:
    """Result from a Sonnet evaluation of a Haiku extraction."""
    score: float           # (completeness + accuracy + (1 - hallucination_risk)) / 3
    evaluation_json: str   # JSON string for TEXT column (completeness, accuracy, hallucination_risk, flags, summary)
    evaluated_at: datetime
    model_id: str
    usage: anthropic.types.Usage


# ---------------------------------------------------------------------------
# Tool builder
# ---------------------------------------------------------------------------

def build_evaluation_tool() -> dict:
    """Build the Claude tool definition for evaluation scoring.

    Mirrors build_extraction_tool() pattern from schema_builder.py.

    Returns:
        dict: Tool definition with name, description, and input_schema.
    """
    return {
        "name": EVAL_TOOL_NAME,
        "description": (
            "Evaluate the quality of an insurance policy extraction by comparing "
            "extracted fields against the original PDF text. Score completeness, "
            "accuracy, and hallucination risk on a 0.0-1.0 scale."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "completeness": {
                    "type": "number",
                    "description": (
                        "Fraction of fields visible in the PDF that were captured (0.0-1.0). "
                        "1.0 means all visible fields were extracted."
                    ),
                },
                "accuracy": {
                    "type": "number",
                    "description": (
                        "Plausibility and correctness of extracted values (0.0-1.0). "
                        "Compare against source text character by character for key fields."
                    ),
                },
                "hallucination_risk": {
                    "type": "number",
                    "description": (
                        "Fraction of fields with invented data not present in the PDF (0.0-1.0). "
                        "0.0 = no hallucinations (desirable). 1.0 = all fields hallucinated."
                    ),
                },
                "flags": {
                    "type": "array",
                    "description": "List of specific field-level issues found.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string", "description": "Field name with the issue"},
                            "issue": {"type": "string", "description": "Description of the issue in Spanish"},
                        },
                        "required": ["field", "issue"],
                    },
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of overall extraction quality in Spanish.",
                },
                "campos_swap_suggestions": {
                    "type": "array",
                    "description": (
                        "Lista de intercambios sospechados en campos_adicionales. "
                        "Un intercambio es cuando un valor claramente pertenece a una clave diferente. "
                        "Array vacio si no se detectan intercambios."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_key": {
                                "type": "string",
                                "description": "Clave donde el valor esta actualmente",
                            },
                            "target_key": {
                                "type": "string",
                                "description": "Clave donde el valor deberia estar",
                            },
                            "suspicious_value": {
                                "type": "string",
                                "description": "El valor sospechoso de estar intercambiado",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Explicacion breve del intercambio sospechado",
                            },
                        },
                        "required": ["source_key", "target_key", "suspicious_value", "reason"],
                    },
                },
            },
            "required": ["completeness", "accuracy", "hallucination_risk", "flags", "summary", "campos_swap_suggestions"],
        },
    }


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_evaluation_api(
    client: anthropic.Anthropic,
    assembled_text: str,
    extraction_json: str,
    model: str = EVAL_MODEL_ID,
    max_tokens: int = 1024,
) -> anthropic.types.Message:
    """Call the Anthropic API to evaluate an extraction.

    Mirrors call_extraction_api() with forced tool_use to guarantee structured output.

    Args:
        client: Authenticated Anthropic client.
        assembled_text: Assembled text from all PDF pages.
        extraction_json: JSON string of the extracted policy data.
        model: Claude model ID (defaults to EVAL_MODEL_ID).
        max_tokens: Maximum tokens in the response.

    Returns:
        Raw Message object from the Anthropic API.
    """
    user_message = f"PDF TEXT:\n{assembled_text}\n\nEXTRACTED DATA:\n{extraction_json}"

    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=EVAL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        tools=[build_evaluation_tool()],
        tool_choice={"type": "tool", "name": EVAL_TOOL_NAME},
    )


# ---------------------------------------------------------------------------
# Internal parser
# ---------------------------------------------------------------------------

def _parse_evaluation(message: anthropic.types.Message) -> EvaluationResult:
    """Parse a tool_use evaluation message into EvaluationResult.

    Args:
        message: Raw Message with tool_use content block.

    Returns:
        EvaluationResult with score, evaluation_json, evaluated_at, model_id, usage.
    """
    raw_input: dict = dict(message.content[0].input)

    # Clamp each score to [0.0, 1.0]
    completeness = max(0.0, min(1.0, float(raw_input["completeness"])))
    accuracy = max(0.0, min(1.0, float(raw_input["accuracy"])))
    hallucination_risk = max(0.0, min(1.0, float(raw_input["hallucination_risk"])))

    # Overall score formula: (completeness + accuracy + (1 - hallucination_risk)) / 3
    score = (completeness + accuracy + (1.0 - hallucination_risk)) / 3.0

    # Extract swap suggestions for validation_warnings (D-17)
    swap_suggestions = raw_input.get("campos_swap_suggestions", [])

    # Build evaluation dict with clamped values
    eval_dict = {
        "completeness": completeness,
        "accuracy": accuracy,
        "hallucination_risk": hallucination_risk,
        "flags": raw_input.get("flags", []),
        "summary": raw_input.get("summary", ""),
        "campos_swap_suggestions": swap_suggestions,
    }

    # Serialize to JSON string — use json.dumps so null not None, true not True
    evaluation_json = json.dumps(eval_dict, ensure_ascii=False)

    return EvaluationResult(
        score=score,
        evaluation_json=evaluation_json,
        evaluated_at=datetime.now(timezone.utc),
        model_id=message.model,
        usage=message.usage,
    )


# ---------------------------------------------------------------------------
# Swap warning builder
# ---------------------------------------------------------------------------


def build_swap_warnings(evaluation_json: str) -> list[str]:
    """Build validation warning strings from swap suggestions in evaluation JSON.

    Returns list of warning strings like:
    'SWAP: campos_adicionales.{source_key} = "{value}" parece pertenecer a "{target_key}". Razon: {reason}'
    """
    try:
        data = json.loads(evaluation_json)
        suggestions = data.get("campos_swap_suggestions", [])
        warnings = []
        for s in suggestions:
            warnings.append(
                f"SWAP: campos_adicionales.{s['source_key']} = \"{s['suspicious_value']}\" "
                f"parece pertenecer a \"{s['target_key']}\". "
                f"Razon: {s['reason']}"
            )
        return warnings
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def evaluate_policy(
    ingestion_result: IngestionResult,
    policy: PolicyExtraction,
    model: str = EVAL_MODEL_ID,
) -> EvaluationResult | None:
    """Evaluate the quality of a Haiku extraction using Sonnet.

    Assembles the original PDF text, serializes the extraction to JSON, and
    calls the Sonnet API with forced tool_use to obtain completeness, accuracy,
    and hallucination_risk scores.

    Args:
        ingestion_result: IngestionResult from the ingestion layer.
        policy: PolicyExtraction produced by Haiku to evaluate.
        model: Claude model ID for evaluation (defaults to EVAL_MODEL_ID).

    Returns:
        EvaluationResult on success, or None if the API call fails.
    """
    try:
        # Lazy import to avoid circular dependency — extraction.prompt imports models
        from policy_extractor.extraction.prompt import assemble_text

        assembled_text = assemble_text(ingestion_result)
        extraction_json = policy.model_dump_json(indent=2)

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = call_evaluation_api(client, assembled_text, extraction_json, model)
        return _parse_evaluation(message)

    except Exception as exc:
        logger.error(f"Evaluation failed: {exc}")
        return None
