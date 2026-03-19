# Tests for extraction layer — expects extract_policy() from policy_extractor.extraction
"""Unit tests for extraction layer — EXT-01 through EXT-05, retry, hallucination, provenance.

All tests mock anthropic.Anthropic to avoid live API calls.
These tests are expected to FAIL until Plan 02 implements extract_policy().
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

from policy_extractor.schemas.ingestion import IngestionResult, PageResult


# ---------------------------------------------------------------------------
# Mock helpers for Anthropic API response simulation
# ---------------------------------------------------------------------------

class MockToolUseBlock:
    type = "tool_use"

    def __init__(self, input_data):
        self.input = input_data


class MockUsage:
    input_tokens = 1000
    output_tokens = 500


class MockMessage:
    def __init__(self, input_data, model="claude-haiku-4-5-20251001"):
        self.content = [MockToolUseBlock(input_data)]
        self.model = model
        self.stop_reason = "tool_use"
        self.usage = MockUsage()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ingestion_result():
    """IngestionResult with 2 pages of realistic Spanish insurance text."""
    pages = [
        PageResult(
            page_num=1,
            text=(
                "POLIZA DE SEGUROS DE AUTOMOVIL\n"
                "Aseguradora: GNP Seguros, S.A.\n"
                "Numero de Poliza: POL-2024-001234\n"
                "Contratante: Juan Garcia Lopez\n"
                "Fecha de Emision: 01/01/2024\n"
                "Inicio de Vigencia: 01/01/2024\n"
                "Fin de Vigencia: 31/12/2024\n"
                "Agente: Maria Rodriguez Hernandez\n"
                "Prima Total: $12,500.00 MXN\n"
                "Forma de Pago: Anual\n"
                "Frecuencia de Pago: Anual\n"
            ),
            classification="digital",
        ),
        PageResult(
            page_num=2,
            text=(
                "COBERTURAS\n"
                "Cobertura Amplia\n"
                "Suma Asegurada: $450,000.00 MXN\n"
                "Deducible: $15,000.00 MXN\n"
                "\n"
                "Responsabilidad Civil\n"
                "Suma Asegurada: $3,000,000.00 MXN\n"
                "Deducible: $0.00 MXN\n"
                "\n"
                "ASEGURADO\n"
                "Tipo: Bien - Vehiculo\n"
                "Marca: Nissan, Modelo: Sentra, Anio: 2022\n"
                "Placas: ABC-1234, VIN: 3N1AB7APXNY123456\n"
            ),
            classification="digital",
        ),
    ]
    return IngestionResult(
        file_hash="sha256abcdef1234567890abcdef1234567890abcdef1234567890abcdef12345678",
        file_path="/data/polizas/gnp_auto_2024.pdf",
        total_pages=2,
        pages=pages,
        file_size_bytes=204800,
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        ocr_applied=False,
    )


@pytest.fixture
def valid_extraction_data():
    """Dict as Claude would return via tool_use — all fields except provenance."""
    return {
        "numero_poliza": "POL-2024-001234",
        "aseguradora": "GNP Seguros",
        "tipo_seguro": "Automovil",
        "fecha_emision": "2024-01-01",
        "inicio_vigencia": "2024-01-01",
        "fin_vigencia": "2024-12-31",
        "nombre_contratante": "Juan Garcia Lopez",
        "nombre_agente": "Maria Rodriguez Hernandez",
        "prima_total": 12500.00,
        "moneda": "MXN",
        "forma_pago": "Anual",
        "frecuencia_pago": "Anual",
        "asegurados": [
            {
                "tipo": "bien",
                "nombre_descripcion": "Nissan Sentra 2022",
                "campos_adicionales": {
                    "tipo_bien": "vehiculo",
                    "marca": "Nissan",
                    "modelo": "Sentra",
                    "anio": 2022,
                    "placas": "ABC-1234",
                    "vin": "3N1AB7APXNY123456",
                },
            }
        ],
        "coberturas": [
            {
                "nombre_cobertura": "Cobertura Amplia",
                "suma_asegurada": 450000.00,
                "deducible": 15000.00,
                "moneda": "MXN",
                "campos_adicionales": {},
            },
            {
                "nombre_cobertura": "Responsabilidad Civil",
                "suma_asegurada": 3000000.00,
                "deducible": 0.00,
                "moneda": "MXN",
                "campos_adicionales": {},
            },
        ],
        "campos_adicionales": {},
        "confianza": {
            "numero_poliza": "high",
            "aseguradora": "high",
            "tipo_seguro": "high",
            "prima_total": "high",
            "nombre_contratante": "high",
            "nombre_agente": "medium",
            "forma_pago": "high",
            "inicio_vigencia": "high",
            "fin_vigencia": "high",
        },
    }


# ---------------------------------------------------------------------------
# Tests — EXT-01: Extract all available fields
# ---------------------------------------------------------------------------

def test_extract_all_fields(sample_ingestion_result, valid_extraction_data):
    """Mock API returns all fields. Assert PolicyExtraction is fully populated."""
    mock_response = MockMessage(valid_extraction_data)

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response

        from policy_extractor.extraction import extract_policy

        result, usage, _rl_retries = extract_policy(sample_ingestion_result)

    assert result.numero_poliza == "POL-2024-001234"
    assert result.aseguradora == "GNP Seguros"
    assert result.tipo_seguro == "Automovil"
    assert result.prima_total == Decimal("12500.00")
    assert len(result.asegurados) == 1
    assert len(result.coberturas) == 2


# ---------------------------------------------------------------------------
# Tests — EXT-02: Output validates against PolicyExtraction schema
# ---------------------------------------------------------------------------

def test_output_is_valid_schema(sample_ingestion_result, valid_extraction_data):
    """Mock API returns valid data. Assert result is PolicyExtraction instance."""
    mock_response = MockMessage(valid_extraction_data)

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response

        from policy_extractor.extraction import extract_policy

        result, usage, _rl_retries = extract_policy(sample_ingestion_result)

    from policy_extractor.schemas.poliza import PolicyExtraction
    assert isinstance(result, PolicyExtraction)
    # model_dump() must succeed without error
    dumped = result.model_dump()
    assert isinstance(dumped, dict)
    assert "numero_poliza" in dumped


# ---------------------------------------------------------------------------
# Tests — EXT-03: Insurer classification from context
# ---------------------------------------------------------------------------

def test_insurer_classification(sample_ingestion_result, valid_extraction_data):
    """Mock API returns aseguradora and tipo_seguro. Assert these come from response."""
    data = dict(valid_extraction_data)
    data["aseguradora"] = "GNP Seguros"
    data["tipo_seguro"] = "Automovil"
    mock_response = MockMessage(data)

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response

        from policy_extractor.extraction import extract_policy

        result, usage, _rl_retries = extract_policy(sample_ingestion_result)

    # Populated from Claude response, not hard-coded
    assert result.aseguradora == "GNP Seguros"
    assert result.tipo_seguro == "Automovil"


# ---------------------------------------------------------------------------
# Tests — EXT-04: Confidence per field
# ---------------------------------------------------------------------------

def test_confianza_populated(sample_ingestion_result, valid_extraction_data):
    """Mock API returns confianza dict. Assert result.confianza is non-empty."""
    mock_response = MockMessage(valid_extraction_data)

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response

        from policy_extractor.extraction import extract_policy

        result, usage, _rl_retries = extract_policy(sample_ingestion_result)

    assert isinstance(result.confianza, dict)
    assert len(result.confianza) > 0
    assert "numero_poliza" in result.confianza


# ---------------------------------------------------------------------------
# Tests — EXT-05: Spanish and English documents
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang,page_text,expected_aseguradora", [
    (
        "spanish",
        "Poliza de Vida\nAseguradora: Metlife Mexico\nNumero de Poliza: MET-9999\nPrima Total: 5000.00 MXN",
        "Metlife Mexico",
    ),
    (
        "english",
        "Life Insurance Policy\nInsurance Company: Metlife USA\nPolicy Number: MET-9999\nTotal Premium: 500.00 USD",
        "Metlife USA",
    ),
])
def test_spanish_and_english(lang, page_text, expected_aseguradora, valid_extraction_data):
    """Both Spanish and English page texts produce valid PolicyExtraction."""
    ingestion = IngestionResult(
        file_hash=f"hash_{lang}",
        file_path=f"/data/{lang}_policy.pdf",
        total_pages=1,
        pages=[PageResult(page_num=1, text=page_text, classification="digital")],
        file_size_bytes=1024,
        created_at=datetime.now(timezone.utc),
        ocr_applied=False,
    )

    data = dict(valid_extraction_data)
    data["aseguradora"] = expected_aseguradora
    data["numero_poliza"] = "MET-9999"
    data["moneda"] = "USD" if lang == "english" else "MXN"
    mock_response = MockMessage(data)

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response

        from policy_extractor.extraction import extract_policy

        from policy_extractor.schemas.poliza import PolicyExtraction
        result, usage, _rl_retries = extract_policy(ingestion)

    assert isinstance(result, PolicyExtraction)
    assert result.aseguradora == expected_aseguradora


# ---------------------------------------------------------------------------
# Tests — Retry on validation error
# ---------------------------------------------------------------------------

def test_retry_on_validation_error(sample_ingestion_result, valid_extraction_data):
    """First call returns invalid data (no numero_poliza). Second call returns valid data."""
    invalid_data = dict(valid_extraction_data)
    del invalid_data["numero_poliza"]  # Remove required field to trigger ValidationError

    valid_data = dict(valid_extraction_data)

    first_response = MockMessage(invalid_data)
    second_response = MockMessage(valid_data)

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [first_response, second_response]

        from policy_extractor.extraction import extract_policy

        result, usage, _rl_retries = extract_policy(sample_ingestion_result)

    # Retry worked — result is valid
    assert result.numero_poliza == "POL-2024-001234"
    # API was called exactly twice
    assert instance.messages.create.call_count == 2


# ---------------------------------------------------------------------------
# Tests — Hallucination verification
# ---------------------------------------------------------------------------

def test_hallucination_verification(sample_ingestion_result, valid_extraction_data):
    """numero_poliza not in source text — confianza should be downgraded to 'low'."""
    data = dict(valid_extraction_data)
    # Return a policy number that does NOT appear in the sample page text
    data["numero_poliza"] = "POL-999-INVENTED"
    data["confianza"] = dict(valid_extraction_data["confianza"])
    data["confianza"]["numero_poliza"] = "high"  # Claude says high, but it's wrong

    mock_response = MockMessage(data)

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response

        from policy_extractor.extraction import extract_policy

        result, usage, _rl_retries = extract_policy(sample_ingestion_result)

    # Post-hoc verification should downgrade confidence for fields not found in source
    assert result.confianza.get("numero_poliza") == "low"


# ---------------------------------------------------------------------------
# Tests — Provenance fields set programmatically
# ---------------------------------------------------------------------------

def test_provenance_fields_set(sample_ingestion_result, valid_extraction_data):
    """Assert result has source_file_hash, model_id, prompt_version, extracted_at set."""
    mock_response = MockMessage(valid_extraction_data, model="claude-haiku-4-5-20251001")

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response

        from policy_extractor.extraction import extract_policy

        result, usage, _rl_retries = extract_policy(sample_ingestion_result)

    assert result.source_file_hash == sample_ingestion_result.file_hash
    assert result.model_id is not None
    assert result.prompt_version is not None
    assert result.extracted_at is not None


# ---------------------------------------------------------------------------
# Tests — Raw response stored alongside PolicyExtraction
# ---------------------------------------------------------------------------

def test_raw_response_stored(sample_ingestion_result, valid_extraction_data):
    """extract_policy returns raw API response dict alongside the PolicyExtraction."""
    mock_response = MockMessage(valid_extraction_data)

    with patch("anthropic.Anthropic") as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_response

        from policy_extractor.extraction import extract_policy

        # extract_policy now returns a 3-tuple: (PolicyExtraction, Usage, rl_retries)
        # Raw response is stored in campos_adicionales["_raw_response"]
        result, usage, _rl_retries = extract_policy(sample_ingestion_result)

    from policy_extractor.schemas.poliza import PolicyExtraction

    assert isinstance(result, PolicyExtraction)
    # Raw response stored in campos_adicionales for auditing
    has_raw = (
        "_raw_response" in result.campos_adicionales
        or hasattr(result, "_raw_response")
    )
    assert has_raw, "Raw API response not stored on result"
    # Usage is returned alongside the policy
    assert usage is not None
