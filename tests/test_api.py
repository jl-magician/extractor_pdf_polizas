"""Tests for FastAPI CRUD endpoints — Phase 5 Plan 02 (STOR-03, STOR-04).

Covers:
- GET /polizas (list with filters and pagination)
- GET /polizas/{id} (single policy, 404 on missing)
- POST /polizas (create, returns 201)
- PUT /polizas/{id} (update, 404 on missing)
- DELETE /polizas/{id} (delete with cascade, 404 on missing)
- Decimal serialization (no TypeError)
- /docs Swagger UI
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from policy_extractor.storage.models import Asegurado, Base, Cobertura, Poliza

# ---------------------------------------------------------------------------
# In-memory DB setup for tests — must happen BEFORE importing app
# ---------------------------------------------------------------------------

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


from policy_extractor.api import app, get_db  # noqa: E402 — must be after DB setup

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe tables before each test for isolation."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def seeded_poliza():
    """Insert one Poliza with one Asegurado and one Cobertura, return the row."""
    db = TestingSessionLocal()
    try:
        poliza = Poliza(
            numero_poliza="POL-001",
            aseguradora="AXA",
            tipo_seguro="vida",
            nombre_agente="Juan Lopez",
            prima_total=Decimal("1500.50"),
            moneda="MXN",
            campos_adicionales={"confianza": {}},
        )
        aseg = Asegurado(tipo="persona", nombre_descripcion="Carlos Ruiz")
        cob = Cobertura(nombre_cobertura="Muerte", moneda="MXN", suma_asegurada=Decimal("500000.00"))
        poliza.asegurados.append(aseg)
        poliza.coberturas.append(cob)
        db.add(poliza)
        db.commit()
        db.refresh(poliza)
        poliza_id = poliza.id
    finally:
        db.close()
    return poliza_id


# ---------------------------------------------------------------------------
# GET /polizas — list
# ---------------------------------------------------------------------------


def test_get_polizas_empty():
    """GET /polizas with empty DB returns 200 with empty list."""
    response = client.get("/polizas")
    assert response.status_code == 200
    assert response.json() == []


def test_get_polizas_with_data(seeded_poliza):
    """GET /polizas returns list with nested asegurados and coberturas."""
    response = client.get("/polizas")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    policy = data[0]
    assert policy["numero_poliza"] == "POL-001"
    assert policy["aseguradora"] == "AXA"
    assert "asegurados" in policy
    assert "coberturas" in policy
    assert len(policy["asegurados"]) == 1
    assert len(policy["coberturas"]) == 1


def test_get_polizas_filter_aseguradora(seeded_poliza):
    """GET /polizas?aseguradora=AXA returns only AXA policies."""
    response_match = client.get("/polizas", params={"aseguradora": "AXA"})
    assert response_match.status_code == 200
    assert len(response_match.json()) == 1

    response_no_match = client.get("/polizas", params={"aseguradora": "MAPFRE"})
    assert response_no_match.status_code == 200
    assert response_no_match.json() == []


def test_get_polizas_filter_tipo_seguro(seeded_poliza):
    """GET /polizas?tipo_seguro=vida filters by insurance type."""
    response = client.get("/polizas", params={"tipo_seguro": "vida"})
    assert response.status_code == 200
    assert len(response.json()) == 1

    response_no = client.get("/polizas", params={"tipo_seguro": "auto"})
    assert response_no.status_code == 200
    assert response_no.json() == []


def test_get_polizas_filter_nombre_agente(seeded_poliza):
    """GET /polizas?nombre_agente=Juan Lopez filters by agent."""
    response = client.get("/polizas", params={"nombre_agente": "Juan Lopez"})
    assert response.status_code == 200
    assert len(response.json()) == 1

    response_no = client.get("/polizas", params={"nombre_agente": "Pedro"})
    assert response_no.status_code == 200
    assert response_no.json() == []


def test_get_polizas_pagination(seeded_poliza):
    """GET /polizas?skip=0&limit=1 returns only 1 result."""
    # Add a second policy
    db = TestingSessionLocal()
    try:
        poliza2 = Poliza(
            numero_poliza="POL-002",
            aseguradora="GNP",
            campos_adicionales={"confianza": {}},
        )
        db.add(poliza2)
        db.commit()
    finally:
        db.close()

    response = client.get("/polizas", params={"skip": 0, "limit": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1

    response_all = client.get("/polizas")
    assert len(response_all.json()) == 2


def test_get_polizas_date_filter(seeded_poliza):
    """GET /polizas?desde=2024-01-01&hasta=2024-12-31 filters by date range."""
    # Add a policy with explicit date range
    db = TestingSessionLocal()
    try:
        from datetime import date
        poliza_dated = Poliza(
            numero_poliza="POL-DATE",
            aseguradora="Qualitas",
            inicio_vigencia=date(2024, 3, 1),
            fin_vigencia=date(2024, 9, 30),
            campos_adicionales={"confianza": {}},
        )
        db.add(poliza_dated)
        db.commit()
    finally:
        db.close()

    response = client.get("/polizas", params={"desde": "2024-01-01", "hasta": "2024-12-31"})
    assert response.status_code == 200
    data = response.json()
    # Only the dated policy matches; seeded_poliza has no dates set
    poliza_nums = [p["numero_poliza"] for p in data]
    assert "POL-DATE" in poliza_nums


# ---------------------------------------------------------------------------
# GET /polizas/{id} — single policy
# ---------------------------------------------------------------------------


def test_get_poliza_by_id(seeded_poliza):
    """GET /polizas/{id} returns 200 with single policy."""
    response = client.get(f"/polizas/{seeded_poliza}")
    assert response.status_code == 200
    data = response.json()
    assert data["numero_poliza"] == "POL-001"


def test_get_poliza_by_id_not_found():
    """GET /polizas/{id} returns 404 for non-existent ID."""
    response = client.get("/polizas/9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /polizas — create
# ---------------------------------------------------------------------------


def test_post_poliza_creates_record():
    """POST /polizas creates a record and returns 201."""
    payload = {
        "numero_poliza": "NEW-001",
        "aseguradora": "HDI",
        "tipo_seguro": "auto",
        "asegurados": [],
        "coberturas": [],
        "campos_adicionales": {},
        "confianza": {},
    }
    response = client.post("/polizas", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["numero_poliza"] == "NEW-001"
    assert data["aseguradora"] == "HDI"


# ---------------------------------------------------------------------------
# PUT /polizas/{id} — update
# ---------------------------------------------------------------------------


def test_put_poliza_updates_record(seeded_poliza):
    """PUT /polizas/{id} updates existing record and returns 200."""
    payload = {
        "numero_poliza": "POL-001",
        "aseguradora": "AXA",
        "tipo_seguro": "gastos_medicos",
        "asegurados": [],
        "coberturas": [],
        "campos_adicionales": {},
        "confianza": {},
    }
    response = client.put(f"/polizas/{seeded_poliza}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tipo_seguro"] == "gastos_medicos"


def test_put_poliza_not_found():
    """PUT /polizas/{id} returns 404 for non-existent ID."""
    payload = {
        "numero_poliza": "GHOST-001",
        "aseguradora": "Unknown",
        "asegurados": [],
        "coberturas": [],
        "campos_adicionales": {},
        "confianza": {},
    }
    response = client.put("/polizas/9999", json=payload)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /polizas/{id} — delete
# ---------------------------------------------------------------------------


def test_delete_poliza_removes_record(seeded_poliza):
    """DELETE /polizas/{id} removes the policy and returns 200."""
    response = client.delete(f"/polizas/{seeded_poliza}")
    assert response.status_code == 200

    # Verify it's gone
    get_response = client.get(f"/polizas/{seeded_poliza}")
    assert get_response.status_code == 404


def test_delete_poliza_not_found():
    """DELETE /polizas/{id} returns 404 for non-existent ID."""
    response = client.delete("/polizas/9999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Decimal serialization
# ---------------------------------------------------------------------------


def test_decimal_serialization(seeded_poliza):
    """Decimal fields (prima_total, suma_asegurada) serialize without TypeError."""
    response = client.get(f"/polizas/{seeded_poliza}")
    assert response.status_code == 200
    data = response.json()
    # prima_total should be present and not cause a crash; model_dump(mode='json') renders it as string or float
    assert "prima_total" in data


# ---------------------------------------------------------------------------
# Swagger /docs
# ---------------------------------------------------------------------------


def test_swagger_docs_endpoint():
    """/docs returns 200 (Swagger UI is accessible)."""
    response = client.get("/docs")
    assert response.status_code == 200
