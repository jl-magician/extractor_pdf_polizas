"""Field-level diff helper for regression fixture comparison.

Usage::

    from policy_extractor.regression.field_differ import FieldDiffer

    differ = FieldDiffer(fixture_dict, actual_dict)
    drift = differ.compare()
    assert not drift.has_failures, drift.format_table()

``FieldDiffer`` operates on plain dicts (i.e. ``model_dump(mode='json')`` output).
It produces a ``DriftReport`` containing (field, expected, actual, status) rows.
"""
import math
from dataclasses import dataclass, field
from decimal import Decimal

def _values_equal(expected, actual) -> bool:
    """Compare two field values for equality, handling Decimal/float serialization artifacts.

    When a Decimal field (e.g. prima_total, suma_asegurada) passes through
    ``model_dump(mode='json')``, it becomes a float. Comparing the original
    Decimal against the float roundtrip result with ``==`` works for simple
    values (Decimal("1500.00") == 1500.0 is True in Python), but arithmetic
    results like Decimal("0.3") vs 0.30000000000000004 would cause spurious
    FAILs. ``math.isclose`` with a very tight tolerance (rel_tol=1e-9) forgives
    only representation artifacts — truly different values like 1500.0 vs 1600.0
    still FAIL.

    For non-numeric types, strict equality (``==``) is used, preserving the
    user's "exact match" intent for all other fields.
    """
    _numeric = (int, float, Decimal)
    if isinstance(expected, _numeric) and isinstance(actual, _numeric):
        return math.isclose(float(expected), float(actual), rel_tol=1e-9)
    return expected == actual


# Fields skipped entirely — provenance and quality signals that change per run
SKIP_FIELDS: frozenset[str] = frozenset(
    {
        "confianza",
        "source_file_hash",
        "model_id",
        "prompt_version",
        "extracted_at",
        "_source_pdf",
    }
)

# List fields and the key used to match items order-independently
LIST_MATCH_KEYS: dict[str, str] = {
    "asegurados": "nombre_descripcion",
    "coberturas": "nombre_cobertura",
}

_REDACTED = "[REDACTED]"
_TRUNCATE = 50


@dataclass
class DriftReport:
    """Structured output from :class:`FieldDiffer`.

    Attributes:
        rows: List of (field_path, expected_value, actual_value, status) tuples.
              ``status`` is either ``"FAIL"`` or ``"PASS"``.
    """

    rows: list[tuple[str, str, str, str]] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        """True if any row has status ``'FAIL'``."""
        return any(r[3] == "FAIL" for r in self.rows)

    def format_table(self) -> str:
        """Return a plain-text drift table for pytest assertion output.

        Format::

            Field | Expected | Actual | Status
            ------------------------------------------------------------
            tipo_seguro | 'auto' | 'vida' | FAIL

        Values are truncated to 50 characters for readability.
        """
        lines = ["\nField | Expected | Actual | Status"]
        lines.append("-" * 60)
        for f, exp, act, status in self.rows:
            exp_repr = repr(exp)[:_TRUNCATE]
            act_repr = repr(act)[:_TRUNCATE]
            lines.append(f"{f} | {exp_repr} | {act_repr} | {status}")
        return "\n".join(lines)


class FieldDiffer:
    """Compare two policy dicts field-by-field and return a :class:`DriftReport`.

    Rules:
    - Skip fields in :data:`SKIP_FIELDS` (provenance + quality signals).
    - Skip any field whose *expected* value is ``'[REDACTED]'``.
    - ``campos_adicionales``: FAIL for missing keys; extra keys in actual = ignored.
    - ``asegurados``: matched by ``nombre_descripcion`` (order-independent).
    - ``coberturas``: matched by ``nombre_cobertura`` (order-independent).
    """

    def __init__(self, expected: dict, actual: dict) -> None:
        self._expected = expected
        self._actual = actual

    def compare(self) -> DriftReport:
        """Run the comparison and return a :class:`DriftReport`."""
        report = DriftReport()

        for key, exp_val in self._expected.items():
            if key in SKIP_FIELDS:
                continue
            if exp_val == _REDACTED:
                continue

            if key == "campos_adicionales":
                self._compare_campos_adicionales(
                    exp_val,
                    self._actual.get("campos_adicionales", {}),
                    report,
                )
            elif key in LIST_MATCH_KEYS:
                match_key = LIST_MATCH_KEYS[key]
                act_list = self._actual.get(key, [])
                self._compare_list(key, exp_val, act_list, match_key, report)
            else:
                act_val = self._actual.get(key)
                if not _values_equal(exp_val, act_val):
                    report.rows.append((key, exp_val, act_val, "FAIL"))

        return report

    # ------------------------------------------------------------------
    # Private comparison helpers
    # ------------------------------------------------------------------

    def _compare_campos_adicionales(
        self,
        expected: dict,
        actual: dict,
        report: DriftReport,
    ) -> None:
        """Compare campos_adicionales key-by-key.

        Missing keys in actual = FAIL.
        Extra keys in actual = ignored (acceptable improvement).
        """
        if not isinstance(expected, dict):
            return
        if not isinstance(actual, dict):
            actual = {}

        for k, exp_val in expected.items():
            if exp_val == _REDACTED:
                continue
            act_val = actual.get(k)
            field_path = f"campos_adicionales.{k}"
            if k not in actual:
                report.rows.append((field_path, exp_val, None, "FAIL"))
            elif not _values_equal(exp_val, act_val):
                report.rows.append((field_path, exp_val, act_val, "FAIL"))

    def _compare_list(
        self,
        list_field: str,
        expected_items: list,
        actual_items: list,
        match_key: str,
        report: DriftReport,
    ) -> None:
        """Match expected list items to actual list items by *match_key*.

        Unmatched expected items (not found in actual by match_key) = FAIL.
        Count mismatch where actual has fewer items also = FAIL.
        """
        if not isinstance(expected_items, list):
            return
        if not isinstance(actual_items, list):
            actual_items = []

        # Build index of actual items by match_key value
        actual_index: dict[str, dict] = {}
        for item in actual_items:
            if isinstance(item, dict):
                mk_val = item.get(match_key)
                if mk_val is not None and mk_val != _REDACTED:
                    actual_index[mk_val] = item

        for exp_item in expected_items:
            if not isinstance(exp_item, dict):
                continue
            match_val = exp_item.get(match_key)

            # If the match key itself is REDACTED, skip this item entirely
            if match_val == _REDACTED or match_val is None:
                continue

            if match_val not in actual_index:
                # The item is missing in actual
                report.rows.append(
                    (
                        f"{list_field}[{match_val}]",
                        f"present ({match_key}={match_val!r})",
                        "missing",
                        "FAIL",
                    )
                )
                continue

            act_item = actual_index[match_val]
            prefix = f"{list_field}[{match_val}]"

            # Compare non-REDACTED, non-SKIP fields within the matched pair
            for sub_key, exp_sub_val in exp_item.items():
                if sub_key in SKIP_FIELDS:
                    continue
                if exp_sub_val == _REDACTED:
                    continue
                if sub_key == "campos_adicionales":
                    self._compare_campos_adicionales(
                        exp_sub_val,
                        act_item.get("campos_adicionales", {}),
                        report,
                    )
                    continue
                act_sub_val = act_item.get(sub_key)
                if not _values_equal(exp_sub_val, act_sub_val):
                    report.rows.append(
                        (f"{prefix}.{sub_key}", exp_sub_val, act_sub_val, "FAIL")
                    )
