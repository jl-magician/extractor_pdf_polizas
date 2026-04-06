"""Unit tests for prompt v2.0.0 — EXT-01 field-mapping rules, Zurich overlay, insurer detection, financial tagging."""
import pytest
from unittest.mock import MagicMock

from policy_extractor.schemas.ingestion import IngestionResult, PageResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ingestion(pages: list[tuple[int, str]]) -> IngestionResult:
    """Create a minimal IngestionResult from (page_num, text) pairs."""
    from datetime import datetime, timezone
    page_results = [
        PageResult(page_num=num, text=text, classification="digital")
        for num, text in pages
    ]
    return IngestionResult(
        file_hash="testhash123",
        file_path="/data/test.pdf",
        total_pages=len(pages),
        pages=page_results,
        file_size_bytes=1024,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ocr_applied=False,
    )


# ---------------------------------------------------------------------------
# Tests — PROMPT_VERSION_V2
# ---------------------------------------------------------------------------

def test_prompt_version_v2_value():
    """PROMPT_VERSION_V2 must be a v2.x.x version string."""
    from policy_extractor.extraction.prompt import PROMPT_VERSION_V2
    assert PROMPT_VERSION_V2.startswith("v2.")


# ---------------------------------------------------------------------------
# Tests — SYSTEM_PROMPT_V2 content
# ---------------------------------------------------------------------------

def test_system_prompt_v2_has_financiamiento_rule():
    """SYSTEM_PROMPT_V2 contains 'financiamiento' field-mapping rule."""
    from policy_extractor.extraction.prompt import SYSTEM_PROMPT_V2
    assert "financiamiento" in SYSTEM_PROMPT_V2.lower()


def test_system_prompt_v2_has_pago_subsecuente_rule():
    """SYSTEM_PROMPT_V2 contains 'pago_subsecuente' field-mapping rule."""
    from policy_extractor.extraction.prompt import SYSTEM_PROMPT_V2
    assert "pago_subsecuente" in SYSTEM_PROMPT_V2.lower()


def test_system_prompt_v2_has_folio_clave_disambiguation():
    """SYSTEM_PROMPT_V2 contains 'folio' and 'clave' disambiguation."""
    from policy_extractor.extraction.prompt import SYSTEM_PROMPT_V2
    assert "folio" in SYSTEM_PROMPT_V2.lower()
    assert "clave" in SYSTEM_PROMPT_V2.lower()


def test_system_prompt_v2_has_financial_breakdown_section():
    """SYSTEM_PROMPT_V2 contains 'Financial Breakdown' section header."""
    from policy_extractor.extraction.prompt import SYSTEM_PROMPT_V2
    assert "Financial Breakdown" in SYSTEM_PROMPT_V2


def test_system_prompt_v2_has_vehicle_identification_section():
    """SYSTEM_PROMPT_V2 contains vehicle identification rules (numero_serie / modelo)."""
    from policy_extractor.extraction.prompt import SYSTEM_PROMPT_V2
    assert "numero_serie" in SYSTEM_PROMPT_V2


# ---------------------------------------------------------------------------
# Tests — detect_insurer()
# ---------------------------------------------------------------------------

def test_detect_insurer_returns_zurich_for_zurich_text():
    """detect_insurer returns 'zurich' when 'zurich' appears in text."""
    from policy_extractor.extraction.prompt import detect_insurer
    text = "POLIZA DE SEGUROS ZURICH Compania de Seguros SA de CV Vigencia: 2024"
    assert detect_insurer(text) == "zurich"


def test_detect_insurer_is_case_insensitive():
    """detect_insurer is case-insensitive — 'ZURICH' and 'Zurich' both match."""
    from policy_extractor.extraction.prompt import detect_insurer
    assert detect_insurer("ZURICH INSURANCE GROUP") == "zurich"
    assert detect_insurer("Zurich Compania de Seguros") == "zurich"


def test_detect_insurer_returns_none_for_axa():
    """detect_insurer returns None for AXA text (no overlay defined yet)."""
    from policy_extractor.extraction.prompt import detect_insurer
    text = "Poliza AXA Seguros SA de CV Numero: AXA-001"
    assert detect_insurer(text) is None


def test_detect_insurer_returns_none_for_generic_text():
    """detect_insurer returns None for generic text with no known insurer."""
    from policy_extractor.extraction.prompt import detect_insurer
    assert detect_insurer("plain insurance policy text no insurer name") is None


def test_detect_insurer_returns_none_for_empty_string():
    """detect_insurer returns None for empty string."""
    from policy_extractor.extraction.prompt import detect_insurer
    assert detect_insurer("") is None


# ---------------------------------------------------------------------------
# Tests — get_system_prompt()
# ---------------------------------------------------------------------------

def test_get_system_prompt_includes_zurich_overlay_for_zurich_text():
    """get_system_prompt returns SYSTEM_PROMPT_V2 + ZURICH_OVERLAY for Zurich text."""
    from policy_extractor.extraction.prompt import get_system_prompt, ZURICH_OVERLAY
    zurich_text = "Poliza Zurich Compania de Seguros SA de CV automovil"
    prompt = get_system_prompt(zurich_text)
    # ZURICH_OVERLAY content must appear in the combined prompt
    assert "Zurich-Specific" in prompt
    # The base prompt must also be present
    assert "Financial Breakdown" in prompt


def test_get_system_prompt_does_not_include_zurich_overlay_for_generic_text():
    """get_system_prompt returns only SYSTEM_PROMPT_V2 (no overlay) for generic text."""
    from policy_extractor.extraction.prompt import get_system_prompt, ZURICH_OVERLAY
    generic_text = "GNP Seguros poliza de automovil prima total 15000"
    prompt = get_system_prompt(generic_text)
    # ZURICH_OVERLAY unique marker should NOT be present
    assert "Zurich-Specific" not in prompt
    # Base prompt must still be present
    assert "Financial Breakdown" in prompt


def test_get_system_prompt_returns_v2_base_for_empty_text():
    """get_system_prompt returns SYSTEM_PROMPT_V2 when text is empty."""
    from policy_extractor.extraction.prompt import get_system_prompt, SYSTEM_PROMPT_V2
    prompt = get_system_prompt("")
    assert prompt == SYSTEM_PROMPT_V2


# ---------------------------------------------------------------------------
# Tests — assemble_text_v2()
# ---------------------------------------------------------------------------

def test_assemble_text_v2_adds_financial_hint_for_prima_page():
    """assemble_text_v2 adds [FINANCIAL BREAKDOWN TABLE BELOW] for page containing 'prima'."""
    from policy_extractor.extraction.prompt import assemble_text_v2
    ingestion = _make_ingestion([(1, "Prima Total 15000 MXN\nDesglose de Primas")])
    result = assemble_text_v2(ingestion)
    assert "[FINANCIAL BREAKDOWN TABLE BELOW]" in result


def test_assemble_text_v2_adds_financial_hint_for_pago_page():
    """assemble_text_v2 adds financial hint for page containing 'pago'."""
    from policy_extractor.extraction.prompt import assemble_text_v2
    ingestion = _make_ingestion([(1, "Forma de Pago: Anual\nImporte: 5000")])
    result = assemble_text_v2(ingestion)
    assert "[FINANCIAL BREAKDOWN TABLE BELOW]" in result


def test_assemble_text_v2_no_hint_for_non_financial_page():
    """assemble_text_v2 does NOT add hint for page without financial keywords."""
    from policy_extractor.extraction.prompt import assemble_text_v2
    ingestion = _make_ingestion([(1, "Nombre del Contratante: Juan Garcia Lopez\nFecha de Emision: 01/01/2024")])
    result = assemble_text_v2(ingestion)
    assert "[FINANCIAL BREAKDOWN TABLE BELOW]" not in result


def test_assemble_text_v2_hint_only_on_financial_pages():
    """assemble_text_v2 adds hint to financial page but not to non-financial page."""
    from policy_extractor.extraction.prompt import assemble_text_v2
    ingestion = _make_ingestion([
        (1, "Nombre del Contratante: Juan Garcia Lopez"),       # no financial keywords
        (2, "Prima Total: 15000 MXN\nFinanciamiento: 0.00"),   # financial keywords
    ])
    result = assemble_text_v2(ingestion)
    lines = result.split("\n")
    # Find page 1 section — hint should NOT appear before page 2
    page1_section = result.split("--- Page 2")[0]
    page2_section = result.split("--- Page 2")[1]
    assert "[FINANCIAL BREAKDOWN TABLE BELOW]" not in page1_section
    assert "[FINANCIAL BREAKDOWN TABLE BELOW]" in page2_section


def test_assemble_text_v2_includes_page_separators():
    """assemble_text_v2 includes --- Page N --- separators for each page."""
    from policy_extractor.extraction.prompt import assemble_text_v2
    ingestion = _make_ingestion([(1, "page one text"), (2, "page two text")])
    result = assemble_text_v2(ingestion)
    assert "--- Page 1 ---" in result
    assert "--- Page 2 ---" in result


def test_assemble_text_v2_includes_page_text():
    """assemble_text_v2 includes page text content in output."""
    from policy_extractor.extraction.prompt import assemble_text_v2
    ingestion = _make_ingestion([(1, "unique content ABC123")])
    result = assemble_text_v2(ingestion)
    assert "unique content ABC123" in result


# ---------------------------------------------------------------------------
# Tests — ZURICH_OVERLAY content
# ---------------------------------------------------------------------------

def test_zurich_overlay_contains_financiamiento_rule():
    """ZURICH_OVERLAY contains rule for financiamiento field."""
    from policy_extractor.extraction.prompt import ZURICH_OVERLAY
    assert "financiamiento" in ZURICH_OVERLAY.lower()


def test_zurich_overlay_contains_folio_clave_rule():
    """ZURICH_OVERLAY contains rules for folio and clave disambiguation."""
    from policy_extractor.extraction.prompt import ZURICH_OVERLAY
    assert "folio" in ZURICH_OVERLAY.lower()
    assert "clave" in ZURICH_OVERLAY.lower()


# ---------------------------------------------------------------------------
# Tests — client.py uses V2 prompt
# ---------------------------------------------------------------------------

def test_client_uses_get_system_prompt(monkeypatch):
    """call_extraction_api uses get_system_prompt (not SYSTEM_PROMPT_V1) for system param."""
    import anthropic as anthropic_mod
    from policy_extractor.extraction import client as client_mod

    # Track what 'system' value was passed to messages.create
    captured = {}

    def fake_create(**kwargs):
        captured["system"] = kwargs.get("system")
        msg = MagicMock()
        msg.content = []
        return msg

    mock_client = MagicMock(spec=anthropic_mod.Anthropic)
    mock_client.messages.create.side_effect = fake_create

    try:
        client_mod.call_extraction_api(
            mock_client,
            assembled_text="Zurich Compania de Seguros test text prima total 15000",
            model="claude-haiku-4-5-20251001",
        )
    except Exception:
        pass  # We only care that create was called with the right system

    # get_system_prompt should have been called — Zurich text means overlay is included
    assert captured.get("system") is not None
    assert "Zurich-Specific" in captured["system"]


def test_client_injects_prompt_version_v2():
    """parse_and_validate injects PROMPT_VERSION_V2 (not PROMPT_VERSION_V1) into raw_input."""
    from policy_extractor.extraction.prompt import PROMPT_VERSION_V2
    from policy_extractor.extraction.client import parse_and_validate

    mock_message = MagicMock()
    mock_message.content = [MagicMock()]
    mock_message.content[0].type = "tool_use"
    mock_message.content[0].input = {
        "numero_poliza": "POL-001",
        "aseguradora": "GNP",
        "campos_adicionales": {},
        "confianza": {},
        "asegurados": [],
        "coberturas": [],
    }
    mock_message.model = "claude-haiku-4-5-20251001"

    policy, raw_input = parse_and_validate(mock_message, ingestion_file_hash="abc123")
    assert raw_input["prompt_version"] == PROMPT_VERSION_V2
