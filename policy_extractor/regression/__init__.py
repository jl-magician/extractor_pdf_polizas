"""Regression testing infrastructure for the policy extractor.

Provides:
    PiiRedactor  -- replaces PII fields with '[REDACTED]' before fixture serialization
    FieldDiffer  -- field-level comparison of two policy dicts
    DriftReport  -- structured output from FieldDiffer with FAIL/PASS rows
"""
from .pii_redactor import PiiRedactor, PII_FIELDS, SKIP_CAMPOS_KEYS
from .field_differ import FieldDiffer, DriftReport

__all__ = [
    "PiiRedactor",
    "PII_FIELDS",
    "SKIP_CAMPOS_KEYS",
    "FieldDiffer",
    "DriftReport",
]
