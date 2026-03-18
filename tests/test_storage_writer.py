"""Unit tests for policy_extractor/storage/writer.py — upsert_policy and orm_to_schema."""
from decimal import Decimal

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
