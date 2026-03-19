"""PII redaction helper for golden fixture creation.

Usage::

    from policy_extractor.regression.pii_redactor import PiiRedactor

    redacted = PiiRedactor().redact(policy.model_dump(mode="json"))

The returned dict is a deep copy with all PII fields replaced by '[REDACTED]'
and with ``_raw_response`` removed from any ``campos_adicionales`` dict found
in the top-level policy, asegurados, or coberturas.
"""
import copy

PII_FIELDS: frozenset[str] = frozenset(
    {
        "nombre_contratante",
        "nombre_descripcion",  # on AseguradoExtraction
        "rfc",
        "curp",
        "direccion",
        "parentesco",
    }
)

SKIP_CAMPOS_KEYS: frozenset[str] = frozenset({"_raw_response"})


class PiiRedactor:
    """Replace PII fields in a policy dict with ``'[REDACTED]'``.

    Also strips ``_raw_response`` (and other keys in ``SKIP_CAMPOS_KEYS``) from
    every ``campos_adicionales`` dict found at the top level and within each
    asegurado / cobertura sub-dict.
    """

    def redact(self, data: dict) -> dict:
        """Return a deep copy of *data* with PII and audit keys removed.

        Args:
            data: A ``dict`` produced by ``PolicyExtraction.model_dump(mode='json')``.

        Returns:
            A new dict safe for committing as a golden fixture.
        """
        result = copy.deepcopy(data)

        # Strip SKIP_CAMPOS_KEYS from top-level campos_adicionales
        self._strip_skip_keys(result)

        # Strip from nested asegurados and coberturas
        for item in result.get("asegurados", []):
            if isinstance(item, dict):
                self._strip_skip_keys(item)
        for item in result.get("coberturas", []):
            if isinstance(item, dict):
                self._strip_skip_keys(item)

        # Replace PII field values recursively
        self._redact_recursive(result)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _strip_skip_keys(self, node: dict) -> None:
        """Remove SKIP_CAMPOS_KEYS from ``node['campos_adicionales']`` in-place."""
        campos = node.get("campos_adicionales")
        if isinstance(campos, dict):
            for key in SKIP_CAMPOS_KEYS:
                campos.pop(key, None)

    def _redact_recursive(self, node: object) -> None:
        """Walk *node* (dict or list) and replace PII field values in-place."""
        if isinstance(node, dict):
            for k in list(node.keys()):
                if k.lower() in PII_FIELDS:
                    node[k] = "[REDACTED]"
                else:
                    self._redact_recursive(node[k])
        elif isinstance(node, list):
            for item in node:
                self._redact_recursive(item)
