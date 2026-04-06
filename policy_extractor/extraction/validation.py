"""Post-extraction validation — annotate-only warning system (D-08).

Validators are registered via @register decorator. Each receives a PolicyExtraction
and returns a list of warning dicts with keys: field, message, severity.

Usage:
    from policy_extractor.extraction.validation import validate_extraction
    warnings = validate_extraction(policy)  # list[dict]
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Callable

from policy_extractor.schemas.poliza import PolicyExtraction

# Type alias: validator takes a PolicyExtraction, returns list of warning dicts
ValidatorFn = Callable[[PolicyExtraction], list[dict]]

# Registry — append new validators here via @register
_VALIDATORS: list[ValidatorFn] = []


def register(fn: ValidatorFn) -> ValidatorFn:
    """Decorator: register a validator function."""
    _VALIDATORS.append(fn)
    return fn


def validate_extraction(policy: PolicyExtraction) -> list[dict]:
    """Run all registered validators, return combined warnings list."""
    warnings = []
    for fn in _VALIDATORS:
        warnings.extend(fn(policy))
    return warnings


@register
def check_financial_invariant(policy: PolicyExtraction) -> list[dict]:
    """primer_pago + pago_subsecuente must be within 1% of prima_total (D-09)."""
    prima_total = policy.prima_total

    primer_pago = policy.primer_pago
    subsecuentes = policy.pago_subsecuente

    if prima_total is None or primer_pago is None or subsecuentes is None:
        return []  # Cannot validate — missing data, not an error

    try:
        total = Decimal(str(prima_total))
        pago = Decimal(str(primer_pago)) + Decimal(str(subsecuentes))
        if total == 0:
            return []
        diff_pct = abs(total - pago) / total
        if diff_pct > Decimal("0.01"):  # 1% tolerance (D-09)
            return [{
                "field": "prima_total",
                "message": (
                    f"Financial invariant violated: primer_pago ({primer_pago}) + "
                    f"subsecuentes ({subsecuentes}) = {float(pago)}, "
                    f"but prima_total = {float(total)} "
                    f"(difference: {float(diff_pct) * 100:.2f}%)"
                ),
                "severity": "warning",
            }]
    except (TypeError, ValueError, InvalidOperation):
        pass  # Non-numeric values — skip silently

    return []


@register
def check_date_logic(policy: PolicyExtraction) -> list[dict]:
    """Date sanity checks: inicio_vigencia < fin_vigencia and fecha_emision <= inicio_vigencia."""
    warnings = []

    if policy.inicio_vigencia is not None and policy.fin_vigencia is not None:
        if policy.fin_vigencia <= policy.inicio_vigencia:
            warnings.append({
                "field": "fin_vigencia",
                "message": (
                    f"Date logic error: fin_vigencia ({policy.fin_vigencia}) "
                    f"<= inicio_vigencia ({policy.inicio_vigencia})"
                ),
                "severity": "warning",
            })

    if policy.fecha_emision is not None and policy.inicio_vigencia is not None:
        if policy.fecha_emision > policy.inicio_vigencia:
            warnings.append({
                "field": "fecha_emision",
                "message": (
                    f"Date logic error: fecha_emision ({policy.fecha_emision}) "
                    f"> inicio_vigencia ({policy.inicio_vigencia})"
                ),
                "severity": "warning",
            })

    return warnings
