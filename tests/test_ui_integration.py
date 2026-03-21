"""Integration tests for Phase 14 web UI — all pages, navigation, and ROADMAP criteria.

Covers:
- All 4 main page routes return 200 (/, /subir, /ui/polizas, /ui/lotes)
- Sidebar navigation links present on every page
- Active page indicator per route
- CDN tags (tailwindcss/browser@4 and htmx.org@2.0.8) on every page
- Spanish UI text throughout
- ROADMAP success criteria SC-1 through SC-5
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from policy_extractor.storage.models import Base, Poliza

# ---------------------------------------------------------------------------
# In-memory DB with StaticPool so all connections share the same DB.
# Must be set up BEFORE importing app to override get_db correctly.
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


from policy_extractor.api import app, get_db  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def apply_db_override():
    """Apply and restore DB override for each test."""
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest.fixture(autouse=True)
def clean_tables():
    """Truncate tables before each test for isolation."""
    db = TestingSessionLocal()
    try:
        db.query(Poliza).delete()
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def seeded_poliza():
    """Insert a minimal Poliza for detail/export tests."""
    db = TestingSessionLocal()
    try:
        poliza = Poliza(
            numero_poliza="INT-001",
            aseguradora="Zurich",
            tipo_seguro="Auto",
            nombre_contratante="Maria Lopez",
            moneda="MXN",
        )
        db.add(poliza)
        db.commit()
        db.refresh(poliza)
        poliza_id = poliza.id
    finally:
        db.close()
    return poliza_id


# ---------------------------------------------------------------------------
# Section 1: All main page routes return 200
# ---------------------------------------------------------------------------


def test_dashboard_returns_200(client):
    """GET / returns 200 with text/html."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_upload_page_returns_200(client):
    """GET /subir returns 200 with text/html."""
    resp = client.get("/subir")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_poliza_list_returns_200(client):
    """GET /ui/polizas returns 200 with text/html."""
    resp = client.get("/ui/polizas")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_lotes_returns_200(client):
    """GET /ui/lotes returns 200 with text/html."""
    resp = client.get("/ui/lotes")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# Section 2: Sidebar navigation links on every page
# ---------------------------------------------------------------------------

_ALL_ROUTES = ["/", "/subir", "/ui/polizas", "/ui/lotes"]
_SIDEBAR_HREFS = ['href="/"', 'href="/subir"', 'href="/ui/polizas"', 'href="/ui/lotes"']


@pytest.mark.parametrize("route", _ALL_ROUTES)
def test_sidebar_has_dashboard_link(client, route):
    """Every page contains href='/' in the sidebar."""
    resp = client.get(route)
    assert resp.status_code == 200
    assert 'href="/"' in resp.text


@pytest.mark.parametrize("route", _ALL_ROUTES)
def test_sidebar_has_upload_link(client, route):
    """Every page contains href='/subir' in the sidebar."""
    resp = client.get(route)
    assert resp.status_code == 200
    assert 'href="/subir"' in resp.text


@pytest.mark.parametrize("route", _ALL_ROUTES)
def test_sidebar_has_polizas_link(client, route):
    """Every page contains href='/ui/polizas' in the sidebar."""
    resp = client.get(route)
    assert resp.status_code == 200
    assert 'href="/ui/polizas"' in resp.text


@pytest.mark.parametrize("route", _ALL_ROUTES)
def test_sidebar_has_lotes_link(client, route):
    """Every page contains href='/ui/lotes' in the sidebar."""
    resp = client.get(route)
    assert resp.status_code == 200
    assert 'href="/ui/lotes"' in resp.text


# ---------------------------------------------------------------------------
# Section 3: Active page indicator
# ---------------------------------------------------------------------------


def test_dashboard_active_indicator(client):
    """GET / highlights Dashboard in sidebar (active class present)."""
    resp = client.get("/")
    assert resp.status_code == 200
    # The base template applies border-l-2 border-blue-400 for active page
    assert "border-blue-400" in resp.text


def test_upload_active_indicator(client):
    """GET /subir highlights Subir PDFs in sidebar."""
    resp = client.get("/subir")
    assert resp.status_code == 200
    assert "border-blue-400" in resp.text


def test_poliza_list_active_indicator(client):
    """GET /ui/polizas highlights Polizas in sidebar."""
    resp = client.get("/ui/polizas")
    assert resp.status_code == 200
    assert "border-blue-400" in resp.text


def test_lotes_active_indicator(client):
    """GET /ui/lotes highlights Historial de Lotes in sidebar."""
    resp = client.get("/ui/lotes")
    assert resp.status_code == 200
    assert "border-blue-400" in resp.text


# ---------------------------------------------------------------------------
# Section 4: CDN integrity — every page includes both CDN tags
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("route", _ALL_ROUTES)
def test_tailwind_cdn_on_every_page(client, route):
    """Every page includes tailwindcss/browser@4 CDN script tag."""
    resp = client.get(route)
    assert resp.status_code == 200
    assert "tailwindcss/browser@4" in resp.text


@pytest.mark.parametrize("route", _ALL_ROUTES)
def test_htmx_cdn_on_every_page(client, route):
    """Every page includes htmx.org@2.0.8 CDN script tag."""
    resp = client.get(route)
    assert resp.status_code == 200
    assert "htmx.org@2.0.8" in resp.text


# ---------------------------------------------------------------------------
# Section 5: Spanish UI — all pages use Spanish copy
# ---------------------------------------------------------------------------


def test_dashboard_spanish_ui(client):
    """Dashboard uses Spanish text (Dashboard heading visible)."""
    resp = client.get("/")
    assert "Dashboard" in resp.text


def test_upload_spanish_ui(client):
    """Upload page uses Spanish text ('Arrastra' or 'Subir')."""
    resp = client.get("/subir")
    assert "Arrastra" in resp.text or "Subir" in resp.text


def test_polizas_spanish_ui(client):
    """Poliza list uses Spanish text ('Polizas')."""
    resp = client.get("/ui/polizas")
    assert "Polizas" in resp.text


def test_lotes_spanish_ui(client):
    """Lotes page uses Spanish text ('Historial' or 'Lotes')."""
    resp = client.get("/ui/lotes")
    assert "Historial" in resp.text or "Lotes" in resp.text


# ---------------------------------------------------------------------------
# Section 6: ROADMAP success criteria
# ---------------------------------------------------------------------------


def test_sc1_upload_page_has_hx_post(client):
    """SC-1: GET /subir contains hx-post attribute (drag-and-drop upload submission)."""
    resp = client.get("/subir")
    assert resp.status_code == 200
    assert "hx-post" in resp.text


def test_sc2_poliza_list_has_rows_and_search(client):
    """SC-2: GET /ui/polizas contains 'poliza-rows' table and search input."""
    resp = client.get("/ui/polizas")
    assert resp.status_code == 200
    assert "poliza-rows" in resp.text
    # Search input present (type="search" or name="q")
    assert 'name="q"' in resp.text or 'type="search"' in resp.text


def test_sc3_dashboard_has_total_polizas(client):
    """SC-3: GET / contains 'Total Polizas' stat card."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Total Polizas" in resp.text


def test_sc3_dashboard_has_requieren_revision(client):
    """SC-3: GET / contains 'Requieren revision' section."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Requieren revision" in resp.text


def test_sc4_poliza_detail_has_export_links(client, seeded_poliza):
    """SC-4: Poliza detail page contains 'Descargar Excel' and 'Descargar JSON' links."""
    resp = client.get(f"/ui/polizas/{seeded_poliza}")
    assert resp.status_code == 200
    assert "Descargar Excel" in resp.text
    assert "Descargar JSON" in resp.text


def test_sc5_upload_module_has_pdfs_retention_dir():
    """SC-5: upload.py defines PDFS_RETENTION_DIR for PDF retention."""
    from policy_extractor.api.upload import PDFS_RETENTION_DIR
    assert PDFS_RETENTION_DIR is not None
    # Should point to data/pdfs/
    assert "pdfs" in str(PDFS_RETENTION_DIR)
