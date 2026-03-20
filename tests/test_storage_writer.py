"""Unit tests for policy_extractor/storage/writer.py — upsert_policy and orm_to_schema."""
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from policy_extractor.schemas.asegurado import AseguradoExtraction
from policy_extractor.schemas.cobertura import CoberturaExtraction
from policy_extractor.schemas.poliza import PolicyExtraction
from policy_extractor.storage.models import Base, Poliza
from policy_extractor.storage.writer import orm_to_schema, upsert_policy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine for tests."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """Session yielded per test then closed."""
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


@pytest.fixture
def sample_extraction() -> PolicyExtraction:
    """Representative PolicyExtraction for testing."""
    return PolicyExtraction(
        numero_poliza="POL-001",
        aseguradora="AXA",
        tipo_seguro="auto",
        nombre_contratante="Juan Perez",
        prima_total=Decimal("15000.50"),
        moneda="MXN",
        asegurados=[
            AseguradoExtraction(
                tipo="persona",
                nombre_descripcion="Juan Perez",
                rfc="PEPJ800101ABC",
            )
        ],
        coberturas=[
            CoberturaExtraction(
                nombre_cobertura="Responsabilidad Civil",
                suma_asegurada=Decimal("500000.00"),
                moneda="MXN",
            )
        ],
        confianza={"numero_poliza": "high", "aseguradora": "high"},
    )


# ---------------------------------------------------------------------------
# Tests: upsert_policy
# ---------------------------------------------------------------------------


def test_upsert_creates_new_poliza(session, sample_extraction):
    """upsert_policy with fresh PolicyExtraction creates a new Poliza row with correct scalar fields."""
    poliza = upsert_policy(session, sample_extraction)

    assert poliza.id is not None
    assert poliza.numero_poliza == "POL-001"
    assert poliza.aseguradora == "AXA"
    assert poliza.tipo_seguro == "auto"
    assert poliza.nombre_contratante == "Juan Perez"
    assert poliza.prima_total == Decimal("15000.50")
    assert poliza.moneda == "MXN"


def test_upsert_deduplicates_same_poliza(session, sample_extraction):
    """upsert_policy with same (numero_poliza, aseguradora) updates existing row — count stays 1."""
    # First insert
    upsert_policy(session, sample_extraction)

    # Modify extraction and upsert again
    updated = sample_extraction.model_copy(
        update={"nombre_contratante": "Juan Garcia", "tipo_seguro": "vida"}
    )
    upsert_policy(session, updated)

    count = session.query(Poliza).filter_by(
        numero_poliza="POL-001", aseguradora="AXA"
    ).count()
    assert count == 1

    poliza = session.query(Poliza).filter_by(
        numero_poliza="POL-001", aseguradora="AXA"
    ).first()
    assert poliza.nombre_contratante == "Juan Garcia"
    assert poliza.tipo_seguro == "vida"


def test_upsert_persists_asegurados(session, sample_extraction):
    """upsert_policy persists child asegurados with correct FK."""
    poliza = upsert_policy(session, sample_extraction)

    session.refresh(poliza)
    assert len(poliza.asegurados) == 1
    aseg = poliza.asegurados[0]
    assert aseg.tipo == "persona"
    assert aseg.nombre_descripcion == "Juan Perez"
    assert aseg.rfc == "PEPJ800101ABC"
    assert aseg.poliza_id == poliza.id


def test_upsert_persists_coberturas(session, sample_extraction):
    """upsert_policy persists child coberturas with correct FK."""
    poliza = upsert_policy(session, sample_extraction)

    session.refresh(poliza)
    assert len(poliza.coberturas) == 1
    cob = poliza.coberturas[0]
    assert cob.nombre_cobertura == "Responsabilidad Civil"
    assert cob.suma_asegurada == Decimal("500000.00")
    assert cob.moneda == "MXN"
    assert cob.poliza_id == poliza.id


def test_upsert_replaces_children_on_update(session, sample_extraction):
    """On upsert, old children are deleted and replaced by new ones — not duplicated."""
    # First insert
    upsert_policy(session, sample_extraction)

    # Update with different children
    new_asegurado = AseguradoExtraction(
        tipo="bien",
        nombre_descripcion="Vehiculo Toyota",
    )
    new_cobertura = CoberturaExtraction(
        nombre_cobertura="Daños Materiales",
        suma_asegurada=Decimal("200000.00"),
        moneda="MXN",
    )
    updated = sample_extraction.model_copy(
        update={"asegurados": [new_asegurado], "coberturas": [new_cobertura]}
    )
    poliza = upsert_policy(session, updated)

    session.refresh(poliza)
    assert len(poliza.asegurados) == 1
    assert poliza.asegurados[0].tipo == "bien"
    assert poliza.asegurados[0].nombre_descripcion == "Vehiculo Toyota"

    assert len(poliza.coberturas) == 1
    assert poliza.coberturas[0].nombre_cobertura == "Daños Materiales"


def test_upsert_stores_confianza_in_campos_adicionales(session, sample_extraction):
    """confianza dict is stored inside campos_adicionales under key 'confianza'."""
    poliza = upsert_policy(session, sample_extraction)

    assert poliza.campos_adicionales is not None
    assert "confianza" in poliza.campos_adicionales
    assert poliza.campos_adicionales["confianza"] == {
        "numero_poliza": "high",
        "aseguradora": "high",
    }


def test_upsert_decimal_fields_survive(session):
    """Decimal fields (prima_total, suma_asegurada, deducible) survive round-trip."""
    extraction = PolicyExtraction(
        numero_poliza="POL-DEC",
        aseguradora="GNP",
        prima_total=Decimal("99999.99"),
        coberturas=[
            CoberturaExtraction(
                nombre_cobertura="Cobertura A",
                suma_asegurada=Decimal("1234567.89"),
                deducible=Decimal("5000.00"),
                moneda="MXN",
            )
        ],
    )
    poliza = upsert_policy(session, extraction)

    session.refresh(poliza)
    assert poliza.prima_total == Decimal("99999.99")
    assert poliza.coberturas[0].suma_asegurada == Decimal("1234567.89")
    assert poliza.coberturas[0].deducible == Decimal("5000.00")


# ---------------------------------------------------------------------------
# Tests: orm_to_schema
# ---------------------------------------------------------------------------


def test_orm_to_schema_scalar_fields(session, sample_extraction):
    """orm_to_schema converts a Poliza ORM row back to PolicyExtraction with correct scalar fields."""
    poliza = upsert_policy(session, sample_extraction)
    session.refresh(poliza)

    result = orm_to_schema(poliza)

    assert isinstance(result, PolicyExtraction)
    assert result.numero_poliza == sample_extraction.numero_poliza
    assert result.aseguradora == sample_extraction.aseguradora
    assert result.tipo_seguro == sample_extraction.tipo_seguro
    assert result.nombre_contratante == sample_extraction.nombre_contratante
    assert result.prima_total == sample_extraction.prima_total
    assert result.moneda == sample_extraction.moneda


def test_orm_to_schema_confianza_extracted(session, sample_extraction):
    """orm_to_schema extracts confianza from campos_adicionales back to top-level field."""
    poliza = upsert_policy(session, sample_extraction)
    session.refresh(poliza)

    result = orm_to_schema(poliza)

    assert result.confianza == sample_extraction.confianza
    # confianza must NOT appear in campos_adicionales of the result
    assert "confianza" not in result.campos_adicionales


def test_orm_to_schema_asegurados(session, sample_extraction):
    """orm_to_schema maps poliza.asegurados to AseguradoExtraction list."""
    poliza = upsert_policy(session, sample_extraction)
    session.refresh(poliza)

    result = orm_to_schema(poliza)

    assert len(result.asegurados) == 1
    aseg = result.asegurados[0]
    assert aseg.tipo == "persona"
    assert aseg.nombre_descripcion == "Juan Perez"
    assert aseg.rfc == "PEPJ800101ABC"


def test_orm_to_schema_coberturas(session, sample_extraction):
    """orm_to_schema maps poliza.coberturas to CoberturaExtraction list."""
    poliza = upsert_policy(session, sample_extraction)
    session.refresh(poliza)

    result = orm_to_schema(poliza)

    assert len(result.coberturas) == 1
    cob = result.coberturas[0]
    assert cob.nombre_cobertura == "Responsabilidad Civil"
    assert cob.suma_asegurada == Decimal("500000.00")
    assert cob.moneda == "MXN"


def test_round_trip_fidelity(session, sample_extraction):
    """Round-trip: upsert then orm_to_schema produces equivalent data to original extraction."""
    poliza = upsert_policy(session, sample_extraction)
    session.refresh(poliza)

    result = orm_to_schema(poliza)

    assert result.numero_poliza == sample_extraction.numero_poliza
    assert result.aseguradora == sample_extraction.aseguradora
    assert result.tipo_seguro == sample_extraction.tipo_seguro
    assert result.prima_total == sample_extraction.prima_total
    assert result.confianza == sample_extraction.confianza

    # Asegurados
    assert len(result.asegurados) == len(sample_extraction.asegurados)
    assert result.asegurados[0].nombre_descripcion == sample_extraction.asegurados[0].nombre_descripcion

    # Coberturas
    assert len(result.coberturas) == len(sample_extraction.coberturas)
    assert result.coberturas[0].nombre_cobertura == sample_extraction.coberturas[0].nombre_cobertura
    assert result.coberturas[0].suma_asegurada == sample_extraction.coberturas[0].suma_asegurada


def test_round_trip_decimal_fidelity(session):
    """Decimal fields survive full round-trip through upsert and orm_to_schema."""
    extraction = PolicyExtraction(
        numero_poliza="POL-RT-DEC",
        aseguradora="Zurich",
        prima_total=Decimal("1234.56"),
        coberturas=[
            CoberturaExtraction(
                nombre_cobertura="RT Cobertura",
                suma_asegurada=Decimal("9999999.99"),
                deducible=Decimal("123.45"),
                moneda="USD",
            )
        ],
    )
    poliza = upsert_policy(session, extraction)
    session.refresh(poliza)

    result = orm_to_schema(poliza)

    assert result.prima_total == Decimal("1234.56")
    assert result.coberturas[0].suma_asegurada == Decimal("9999999.99")
    assert result.coberturas[0].deducible == Decimal("123.45")
    assert result.coberturas[0].moneda == "USD"


# ---------------------------------------------------------------------------
# Tests: _load_exclusion_config and _apply_exclusions (D-11 through D-14)
# ---------------------------------------------------------------------------


def test_load_exclusion_config_returns_empty_dict_for_default_only():
    """_load_exclusion_config returns empty dict when config has only 'default' key."""
    from policy_extractor.storage.writer import _load_exclusion_config
    _load_exclusion_config.cache_clear()

    fake_config = {"default": [], "_comment": "test"}
    with patch("builtins.open", create=True) as mock_open:
        import json
        from io import StringIO
        mock_open.return_value.__enter__ = lambda s: StringIO(json.dumps(fake_config))
        mock_open.return_value.__exit__ = lambda s, *a: False
        # Patch pathlib Path.exists to return True
        with patch("pathlib.Path.exists", return_value=True):
            _load_exclusion_config.cache_clear()
            with patch("policy_extractor.storage.writer._load_exclusion_config",
                       return_value={}):
                from policy_extractor.storage.writer import _apply_exclusions
                # No exclusions — nothing is dropped
                result = _apply_exclusions({"field_a": 1, "field_b": 2}, "zurich")
                assert result == {"field_a": 1, "field_b": 2}


def test_apply_exclusions_drops_configured_fields():
    """_apply_exclusions drops fields listed in config for matching insurer."""
    from policy_extractor.storage.writer import _apply_exclusions
    fake_config = {"zurich": ["agencia_responsable", "campo_inutil"]}
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value=fake_config):
        campos = {"agencia_responsable": "Unidad X", "campo_inutil": "foo", "prima_neta": 1000}
        result = _apply_exclusions(campos, "Zurich")
        assert "agencia_responsable" not in result
        assert "campo_inutil" not in result
        assert "prima_neta" in result


def test_apply_exclusions_does_not_drop_unconfigured_fields():
    """_apply_exclusions does NOT drop fields not in the exclusion list."""
    from policy_extractor.storage.writer import _apply_exclusions
    fake_config = {"zurich": ["excluded_field"]}
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value=fake_config):
        campos = {"excluded_field": "x", "keep_me": "value", "also_keep": 42}
        result = _apply_exclusions(campos, "zurich")
        assert "keep_me" in result
        assert "also_keep" in result
        assert result["keep_me"] == "value"
        assert result["also_keep"] == 42


def test_apply_exclusions_global_star_applies_to_all_insurers():
    """_apply_exclusions applies '*' global exclusions to all insurers."""
    from policy_extractor.storage.writer import _apply_exclusions
    fake_config = {"*": ["always_excluded"]}
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value=fake_config):
        # Test with "axa" insurer — no specific config, but "*" applies
        campos = {"always_excluded": "drop_me", "keep_me": "value"}
        result = _apply_exclusions(campos, "axa")
        assert "always_excluded" not in result
        assert "keep_me" in result

        # Test with "mapfre" insurer — same result
        result2 = _apply_exclusions(campos, "mapfre")
        assert "always_excluded" not in result2


def test_apply_exclusions_is_case_insensitive_on_insurer():
    """_apply_exclusions is case-insensitive on insurer name."""
    from policy_extractor.storage.writer import _apply_exclusions
    fake_config = {"zurich": ["campo_secreto"]}
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value=fake_config):
        campos = {"campo_secreto": "hidden", "visible": "ok"}
        # Test with "ZURICH" uppercase
        result = _apply_exclusions(campos, "ZURICH")
        assert "campo_secreto" not in result
        assert "visible" in result
        # Test with "Zurich" title case
        result2 = _apply_exclusions(campos, "Zurich")
        assert "campo_secreto" not in result2


def test_apply_exclusions_returns_none_for_none_campos():
    """_apply_exclusions returns None when campos is None."""
    from policy_extractor.storage.writer import _apply_exclusions
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value={}):
        assert _apply_exclusions(None, "zurich") is None


def test_apply_exclusions_returns_empty_dict_unchanged():
    """_apply_exclusions returns empty dict unchanged."""
    from policy_extractor.storage.writer import _apply_exclusions
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value={}):
        result = _apply_exclusions({}, "zurich")
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: upsert_policy writes validation_warnings (EXT-02)
# ---------------------------------------------------------------------------


def test_upsert_writes_validation_warnings_when_present(session):
    """upsert_policy writes validation_warnings to poliza.validation_warnings column."""
    extraction = PolicyExtraction(
        numero_poliza="POL-WARN-001",
        aseguradora="Zurich",
        prima_total=Decimal("10000.00"),
        validation_warnings=[
            {"field": "prima_total", "message": "Invariant violation", "severity": "warning"}
        ],
    )
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value={}):
        poliza = upsert_policy(session, extraction)

    assert poliza.validation_warnings is not None
    assert len(poliza.validation_warnings) == 1
    assert poliza.validation_warnings[0]["field"] == "prima_total"
    assert poliza.validation_warnings[0]["severity"] == "warning"


def test_upsert_writes_validation_warnings_as_none_when_empty(session):
    """upsert_policy writes None to validation_warnings when no warnings are present."""
    extraction = PolicyExtraction(
        numero_poliza="POL-NOWARN-001",
        aseguradora="GNP",
        prima_total=Decimal("5000.00"),
        validation_warnings=[],  # empty
    )
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value={}):
        poliza = upsert_policy(session, extraction)

    assert poliza.validation_warnings is None


# ---------------------------------------------------------------------------
# Tests: upsert_policy applies field exclusion at all three levels
# ---------------------------------------------------------------------------


def test_upsert_applies_exclusion_to_poliza_campos(session):
    """upsert_policy applies field exclusion to poliza-level campos_adicionales."""
    extraction = PolicyExtraction(
        numero_poliza="POL-EXCL-001",
        aseguradora="Zurich",
        campos_adicionales={"keep_me": "value", "drop_me": "unwanted"},
    )
    fake_config = {"zurich": ["drop_me"]}
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value=fake_config):
        poliza = upsert_policy(session, extraction)

    assert "keep_me" in poliza.campos_adicionales
    assert "drop_me" not in poliza.campos_adicionales


def test_upsert_applies_exclusion_to_asegurado_campos(session):
    """upsert_policy applies field exclusion to asegurado-level campos_adicionales."""
    extraction = PolicyExtraction(
        numero_poliza="POL-EXCL-002",
        aseguradora="Zurich",
        asegurados=[
            AseguradoExtraction(
                tipo="persona",
                nombre_descripcion="Test Person",
                campos_adicionales={"keep_field": "ok", "drop_field": "unwanted"},
            )
        ],
    )
    fake_config = {"zurich": ["drop_field"]}
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value=fake_config):
        poliza = upsert_policy(session, extraction)

    session.refresh(poliza)
    aseg_campos = poliza.asegurados[0].campos_adicionales
    assert aseg_campos is not None
    assert "keep_field" in aseg_campos
    assert "drop_field" not in aseg_campos


def test_upsert_applies_exclusion_to_cobertura_campos(session):
    """upsert_policy applies field exclusion to cobertura-level campos_adicionales."""
    extraction = PolicyExtraction(
        numero_poliza="POL-EXCL-003",
        aseguradora="Zurich",
        coberturas=[
            CoberturaExtraction(
                nombre_cobertura="Test Coverage",
                campos_adicionales={"keep_cob": "yes", "drop_cob": "no"},
            )
        ],
    )
    fake_config = {"zurich": ["drop_cob"]}
    with patch("policy_extractor.storage.writer._load_exclusion_config", return_value=fake_config):
        poliza = upsert_policy(session, extraction)

    session.refresh(poliza)
    cob_campos = poliza.coberturas[0].campos_adicionales
    assert cob_campos is not None
    assert "keep_cob" in cob_campos
    assert "drop_cob" not in cob_campos
