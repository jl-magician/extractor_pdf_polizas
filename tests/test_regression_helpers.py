"""Unit tests for PiiRedactor and FieldDiffer regression helpers.

These are regular unit tests — NOT marked with @pytest.mark.regression.
They run in the default suite: pytest tests/test_regression_helpers.py
"""
import pytest
from decimal import Decimal

# ---------------------------------------------------------------------------
# PiiRedactor tests
# ---------------------------------------------------------------------------

from policy_extractor.regression.pii_redactor import PiiRedactor, PII_FIELDS


class TestPiiRedactor:
    """Tests 1-5: PiiRedactor.redact() behaviour."""

    def _make_policy(self) -> dict:
        """Minimal policy dict with all PII fields present."""
        return {
            "numero_poliza": "POL-001",
            "aseguradora": "AXA",
            "nombre_contratante": "Juan García",
            "prima_total": "1500.00",
            "asegurados": [
                {
                    "tipo": "persona",
                    "nombre_descripcion": "María López",
                    "rfc": "LOPJ800101ABC",
                    "curp": "LOPJ800101HDFXXX00",
                    "direccion": "Calle 5 No. 10",
                    "parentesco": "cónyuge",
                    "campos_adicionales": {},
                }
            ],
            "coberturas": [
                {
                    "nombre_cobertura": "Daños a terceros",
                    "suma_asegurada": "500000.00",
                    "campos_adicionales": {"_raw_response": {"raw": "big dict"}},
                }
            ],
            "campos_adicionales": {"_raw_response": {"key": "value"}, "otro": "dato"},
            "confianza": {"numero_poliza": 0.99},
        }

    def test_1_redacts_all_six_pii_fields(self):
        """PiiRedactor.redact() replaces all 6 PII fields with '[REDACTED]'."""
        policy = self._make_policy()
        redactor = PiiRedactor()
        result = redactor.redact(policy)

        assert result["nombre_contratante"] == "[REDACTED]"
        asegurado = result["asegurados"][0]
        assert asegurado["nombre_descripcion"] == "[REDACTED]"
        assert asegurado["rfc"] == "[REDACTED]"
        assert asegurado["curp"] == "[REDACTED]"
        assert asegurado["direccion"] == "[REDACTED]"
        assert asegurado["parentesco"] == "[REDACTED]"

    def test_2_redact_works_recursively_into_nested_asegurados(self):
        """redact() replaces PII fields inside nested asegurados list."""
        policy = {
            "numero_poliza": "X",
            "aseguradora": "GNP",
            "nombre_contratante": "Pedro Ramírez",
            "asegurados": [
                {"nombre_descripcion": "Ana Flores", "rfc": "FLOA900101DEF"},
                {"nombre_descripcion": "Luis Torres", "curp": "TORL850101HXXXXX00"},
            ],
            "campos_adicionales": {},
        }
        result = PiiRedactor().redact(policy)

        assert result["nombre_contratante"] == "[REDACTED]"
        assert result["asegurados"][0]["nombre_descripcion"] == "[REDACTED]"
        assert result["asegurados"][0]["rfc"] == "[REDACTED]"
        assert result["asegurados"][1]["nombre_descripcion"] == "[REDACTED]"
        assert result["asegurados"][1]["curp"] == "[REDACTED]"

    def test_3_redact_strips_raw_response_from_campos_adicionales(self):
        """redact() removes '_raw_response' key from campos_adicionales."""
        policy = {
            "numero_poliza": "X",
            "aseguradora": "HDI",
            "nombre_contratante": "Test User",
            "campos_adicionales": {
                "_raw_response": {"model": "claude", "tokens": 100},
                "vigencia_especial": "anual",
            },
            "asegurados": [],
            "coberturas": [],
        }
        result = PiiRedactor().redact(policy)

        assert "_raw_response" not in result["campos_adicionales"]
        assert result["campos_adicionales"]["vigencia_especial"] == "anual"

    def test_4_redact_does_not_modify_non_pii_fields(self):
        """redact() leaves non-PII fields (numero_poliza, aseguradora, prima_total) unchanged."""
        policy = self._make_policy()
        result = PiiRedactor().redact(policy)

        assert result["numero_poliza"] == "POL-001"
        assert result["aseguradora"] == "AXA"
        assert result["prima_total"] == "1500.00"

    def test_5_redact_returns_deep_copy(self):
        """redact() returns a deep copy — the original dict is unchanged."""
        policy = self._make_policy()
        original_nombre = policy["nombre_contratante"]
        original_asegurado_nombre = policy["asegurados"][0]["nombre_descripcion"]

        result = PiiRedactor().redact(policy)

        # Original should be untouched
        assert policy["nombre_contratante"] == original_nombre
        assert policy["asegurados"][0]["nombre_descripcion"] == original_asegurado_nombre
        # Result should be redacted
        assert result["nombre_contratante"] == "[REDACTED]"
        assert result is not policy


# ---------------------------------------------------------------------------
# FieldDiffer tests
# ---------------------------------------------------------------------------

from policy_extractor.regression.field_differ import FieldDiffer, DriftReport


class TestFieldDiffer:
    """Tests 6-15: FieldDiffer.compare() and DriftReport behaviour."""

    def _base_policy(self) -> dict:
        """Minimal policy dict for diffing tests (already redacted)."""
        return {
            "numero_poliza": "POL-100",
            "aseguradora": "AXA",
            "tipo_seguro": "auto",
            "nombre_contratante": "[REDACTED]",
            "prima_total": "2000.00",
            "moneda": "MXN",
            "asegurados": [],
            "coberturas": [],
            "campos_adicionales": {"clave_agente": "AG001"},
            "confianza": {"numero_poliza": 0.99},
            "source_file_hash": "abc123",
            "model_id": "claude-haiku",
            "prompt_version": "v1.0",
            "extracted_at": "2026-01-01T00:00:00",
        }

    def test_6_identical_dicts_produce_no_failures(self):
        """Identical expected and actual dicts produce DriftReport with has_failures=False."""
        expected = self._base_policy()
        actual = self._base_policy()

        drift = FieldDiffer(expected, actual).compare()

        assert isinstance(drift, DriftReport)
        assert drift.has_failures is False

    def test_7_differing_scalar_field_produces_fail_row(self):
        """A differing scalar field produces a FAIL row with correct field, expected, actual."""
        expected = self._base_policy()
        actual = self._base_policy()
        actual["tipo_seguro"] = "vida"

        drift = FieldDiffer(expected, actual).compare()

        assert drift.has_failures is True
        fail_rows = [r for r in drift.rows if r[3] == "FAIL"]
        assert len(fail_rows) == 1
        field, exp_val, act_val, status = fail_rows[0]
        assert field == "tipo_seguro"
        assert exp_val == "auto"
        assert act_val == "vida"
        assert status == "FAIL"

    def test_8_redacted_field_in_expected_is_skipped(self):
        """Fields with '[REDACTED]' in expected are not included in the report."""
        expected = self._base_policy()  # nombre_contratante is "[REDACTED]"
        actual = self._base_policy()
        actual["nombre_contratante"] = "Real Name"  # differs, but should be skipped

        drift = FieldDiffer(expected, actual).compare()

        field_names = [r[0] for r in drift.rows]
        assert "nombre_contratante" not in field_names

    def test_9_campos_adicionales_missing_key_fail_extra_key_pass(self):
        """Missing key in actual campos_adicionales = FAIL; extra key = ignored (PASS)."""
        expected = self._base_policy()
        expected["campos_adicionales"] = {"clave_agente": "AG001", "region": "norte"}

        actual = self._base_policy()
        actual["campos_adicionales"] = {
            "clave_agente": "AG001",
            # "region" is MISSING — should FAIL
            "extra_nuevo": "data",  # extra key — should be ignored
        }

        drift = FieldDiffer(expected, actual).compare()

        fail_rows = [r for r in drift.rows if r[3] == "FAIL"]
        assert any("region" in r[0] for r in fail_rows), f"Expected FAIL for 'region', rows: {drift.rows}"
        # Extra key should not appear as FAIL
        fail_fields = {r[0] for r in fail_rows}
        assert "campos_adicionales.extra_nuevo" not in fail_fields

    def test_10_asegurados_matched_by_nombre_descripcion_order_independent(self):
        """Asegurados matched by nombre_descripcion (order-independent); field diff within pair."""
        expected = self._base_policy()
        expected["asegurados"] = [
            {"nombre_descripcion": "[REDACTED]", "tipo": "persona", "rfc": "[REDACTED]"},
            {"nombre_descripcion": "Cobertura Bien", "tipo": "bien", "rfc": None},
        ]
        actual = self._base_policy()
        actual["asegurados"] = [
            {"nombre_descripcion": "Cobertura Bien", "tipo": "bien", "rfc": "WRONG-RFC"},
            {"nombre_descripcion": "[REDACTED]", "tipo": "persona", "rfc": "[REDACTED]"},
        ]

        drift = FieldDiffer(expected, actual).compare()

        # "Cobertura Bien" asegurado has rfc mismatch (None vs "WRONG-RFC") — should FAIL
        assert drift.has_failures is True
        fail_rows = [r for r in drift.rows if r[3] == "FAIL"]
        assert any("rfc" in r[0] for r in fail_rows), f"Expected RFC FAIL, rows: {drift.rows}"

    def test_11_coberturas_matched_by_nombre_cobertura_missing_cobertura_fail(self):
        """Coberturas matched by nombre_cobertura; missing cobertura in actual = FAIL."""
        expected = self._base_policy()
        expected["coberturas"] = [
            {"nombre_cobertura": "Daños a terceros", "suma_asegurada": "500000.00"},
            {"nombre_cobertura": "Robo total", "suma_asegurada": "200000.00"},
        ]
        actual = self._base_policy()
        actual["coberturas"] = [
            # "Robo total" is MISSING
            {"nombre_cobertura": "Daños a terceros", "suma_asegurada": "500000.00"},
        ]

        drift = FieldDiffer(expected, actual).compare()

        assert drift.has_failures is True
        fail_rows = [r for r in drift.rows if r[3] == "FAIL"]
        assert any("Robo total" in str(r) for r in fail_rows), f"Expected FAIL for missing cobertura, rows: {drift.rows}"

    def test_12_provenance_fields_are_skipped(self):
        """confianza, source_file_hash, model_id, prompt_version, extracted_at are all skipped."""
        expected = self._base_policy()
        actual = self._base_policy()

        # Make all provenance fields differ
        actual["confianza"] = {"numero_poliza": 0.5}
        actual["source_file_hash"] = "different_hash"
        actual["model_id"] = "claude-sonnet"
        actual["prompt_version"] = "v2.0"
        actual["extracted_at"] = "2099-01-01T00:00:00"

        drift = FieldDiffer(expected, actual).compare()

        # No failures — provenance fields should be skipped
        assert drift.has_failures is False
        all_fields = {r[0] for r in drift.rows}
        for skip_field in ("confianza", "source_file_hash", "model_id", "prompt_version", "extracted_at"):
            assert skip_field not in all_fields, f"Field '{skip_field}' should be skipped but appeared in rows"

    def test_13_format_table_contains_header(self):
        """format_table() output contains 'Field | Expected | Actual | Status' header."""
        expected = self._base_policy()
        actual = self._base_policy()
        actual["tipo_seguro"] = "vida"

        drift = FieldDiffer(expected, actual).compare()
        table = drift.format_table()

        assert "Field" in table
        assert "Expected" in table
        assert "Actual" in table
        assert "Status" in table

    def test_14_asegurados_count_mismatch_fewer_actual_fail(self):
        """Asegurados count mismatch (fewer in actual) = FAIL."""
        expected = self._base_policy()
        expected["asegurados"] = [
            {"nombre_descripcion": "Ana Flores", "tipo": "persona"},
            {"nombre_descripcion": "Luis Torres", "tipo": "persona"},
        ]
        actual = self._base_policy()
        actual["asegurados"] = [
            {"nombre_descripcion": "Ana Flores", "tipo": "persona"},
            # "Luis Torres" is MISSING
        ]

        drift = FieldDiffer(expected, actual).compare()

        assert drift.has_failures is True
        fail_rows = [r for r in drift.rows if r[3] == "FAIL"]
        assert any("Luis Torres" in str(r) for r in fail_rows), f"Expected FAIL for missing asegurado, rows: {drift.rows}"

    def test_15_coberturas_count_mismatch_fail(self):
        """Coberturas count mismatch (more in expected than actual) = FAIL."""
        expected = self._base_policy()
        expected["coberturas"] = [
            {"nombre_cobertura": "Cobertura A", "suma_asegurada": "100000.00"},
            {"nombre_cobertura": "Cobertura B", "suma_asegurada": "200000.00"},
            {"nombre_cobertura": "Cobertura C", "suma_asegurada": "300000.00"},
        ]
        actual = self._base_policy()
        actual["coberturas"] = [
            {"nombre_cobertura": "Cobertura A", "suma_asegurada": "100000.00"},
        ]

        drift = FieldDiffer(expected, actual).compare()

        assert drift.has_failures is True
        fail_rows = [r for r in drift.rows if r[3] == "FAIL"]
        missing_names = [r for r in fail_rows if "Cobertura B" in str(r) or "Cobertura C" in str(r)]
        assert len(missing_names) >= 2, f"Expected FAILs for Cobertura B and C, rows: {drift.rows}"

    # ------------------------------------------------------------------
    # Tests 16-20: Decimal/float serialization roundtrip safety
    # ------------------------------------------------------------------

    def test_16_float_prima_total_equal_produces_no_fail(self):
        """FieldDiffer with expected prima_total=1500.0 (float) and actual=1500.0 produces no FAIL."""
        expected = self._base_policy()
        expected["prima_total"] = 1500.0  # float from JSON roundtrip
        actual = self._base_policy()
        actual["prima_total"] = 1500.0

        drift = FieldDiffer(expected, actual).compare()

        assert drift.has_failures is False, f"Expected no failures, got: {drift.rows}"

    def test_17_string_vs_float_prima_total_produces_fail(self):
        """FieldDiffer with expected prima_total='1500.00' (string) and actual=1500.0 (float) produces FAIL."""
        expected = self._base_policy()
        expected["prima_total"] = "1500.00"  # string — not a Decimal roundtrip, different type
        actual = self._base_policy()
        actual["prima_total"] = 1500.0  # float

        drift = FieldDiffer(expected, actual).compare()

        assert drift.has_failures is True, f"Expected FAIL for string vs float mismatch, rows: {drift.rows}"
        fail_rows = [r for r in drift.rows if r[3] == "FAIL"]
        assert any("prima_total" in r[0] for r in fail_rows), f"Expected prima_total FAIL, rows: {drift.rows}"

    def test_18_float_suma_asegurada_in_coberturas_produces_no_fail(self):
        """FieldDiffer with expected suma_asegurada=500000.0 and actual=500000.0 in coberturas produces no FAIL."""
        expected = self._base_policy()
        expected["coberturas"] = [
            {"nombre_cobertura": "Daños a terceros", "suma_asegurada": 500000.0},
        ]
        actual = self._base_policy()
        actual["coberturas"] = [
            {"nombre_cobertura": "Daños a terceros", "suma_asegurada": 500000.0},
        ]

        drift = FieldDiffer(expected, actual).compare()

        assert drift.has_failures is False, f"Expected no failures, got: {drift.rows}"

    def test_19_decimal_vs_float_prima_total_produces_no_fail(self):
        """FieldDiffer with Decimal('1500.00') vs float 1500.0 produces no spurious FAIL (core roundtrip case)."""
        expected = self._base_policy()
        expected["prima_total"] = Decimal("1500.00")  # Decimal — as extracted before model_dump
        actual = self._base_policy()
        actual["prima_total"] = 1500.0  # float — result of model_dump(mode='json') roundtrip

        drift = FieldDiffer(expected, actual).compare()

        assert drift.has_failures is False, f"Expected no FAIL for Decimal vs float roundtrip, rows: {drift.rows}"

    def test_20_truly_different_monetary_values_still_fail(self):
        """FieldDiffer with truly different monetary values (1500.0 vs 1600.0) still produces FAIL."""
        expected = self._base_policy()
        expected["prima_total"] = 1500.0
        actual = self._base_policy()
        actual["prima_total"] = 1600.0

        drift = FieldDiffer(expected, actual).compare()

        assert drift.has_failures is True, f"Expected FAIL for 1500.0 vs 1600.0, rows: {drift.rows}"
        fail_rows = [r for r in drift.rows if r[3] == "FAIL"]
        assert any("prima_total" in r[0] for r in fail_rows), f"Expected prima_total FAIL, rows: {drift.rows}"
