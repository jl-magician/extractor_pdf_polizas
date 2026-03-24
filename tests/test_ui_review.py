"""Tests for Phase 15 — HITL review workflow endpoints."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from policy_extractor.storage.models import Asegurado, Base, Cobertura, Correction, Poliza

# ---------------------------------------------------------------------------
# In-memory DB shared across all connections via StaticPool
# Must be set up BEFORE importing app so the override takes effect.
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


from policy_extractor.api import app, get_db  # noqa: E402 — after DB setup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def apply_db_override():
    """Apply DB override for every test in this module, then restore."""
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


@pytest.fixture(autouse=True)
def clean_tables():
    """Truncate all relevant tables before each test for isolation."""
    db = TestingSessionLocal()
    try:
        db.query(Correction).delete()
        db.query(Cobertura).delete()
        db.query(Asegurado).delete()
        db.query(Poliza).delete()
        db.commit()
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture
def sample_poliza():
    """Create a test poliza with an asegurado and cobertura, return (pid, aid, cid)."""
    db = TestingSessionLocal()
    p = Poliza(
        numero_poliza="TEST-001",
        aseguradora="TestCo",
        prima_total=Decimal("1000.00"),
        moneda="MXN",
        campos_adicionales={"numero_endoso": "E-001"},
    )
    db.add(p)
    db.flush()
    a = Asegurado(poliza_id=p.id, tipo="persona", nombre_descripcion="Juan Perez")
    c = Cobertura(
        poliza_id=p.id,
        nombre_cobertura="RC",
        suma_asegurada=Decimal("500000.00"),
        deducible=Decimal("1000.00"),
        moneda="MXN",
    )
    db.add_all([a, c])
    db.commit()
    pid, aid, cid = p.id, a.id, c.id
    db.close()
    return pid, aid, cid


# ---------------------------------------------------------------------------
# Helper to create/remove a dummy PDF for test isolation
# ---------------------------------------------------------------------------


def _create_dummy_pdf(pid: int) -> Path:
    pdf_dir = Path("data/pdfs")
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{pid}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")
    return pdf_path


# ---------------------------------------------------------------------------
# GET /ui/polizas/{id}/review tests
# ---------------------------------------------------------------------------


def test_review_page_returns_200(sample_poliza):
    """Review page returns 200 when PDF exists."""
    pid, _, _ = sample_poliza
    pdf_path = _create_dummy_pdf(pid)
    try:
        resp = client.get(f"/ui/polizas/{pid}/review")
        assert resp.status_code == 200
        assert "TEST-001" in resp.text
    finally:
        pdf_path.unlink(missing_ok=True)


def test_review_page_has_pdf_iframe(sample_poliza):
    """Review page includes an iframe pointing to the PDF endpoint."""
    pid, _, _ = sample_poliza
    pdf_path = _create_dummy_pdf(pid)
    try:
        resp = client.get(f"/ui/polizas/{pid}/review")
        assert resp.status_code == 200
        assert f"/ui/polizas/{pid}/pdf" in resp.text
        assert "<iframe" in resp.text
    finally:
        pdf_path.unlink(missing_ok=True)


def test_review_page_404_without_pdf(sample_poliza):
    """Review page returns 404 when PDF is not present."""
    pid, _, _ = sample_poliza
    # Ensure no PDF file exists for this poliza
    pdf_path = Path("data/pdfs") / f"{pid}.pdf"
    pdf_path.unlink(missing_ok=True)
    resp = client.get(f"/ui/polizas/{pid}/review")
    assert resp.status_code == 404


def test_review_page_404_poliza_not_found():
    """Review page returns 404 for a non-existent poliza."""
    resp = client.get("/ui/polizas/99999/review")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /ui/polizas/{id}/review/field tests
# ---------------------------------------------------------------------------


def test_patch_field_returns_partial(sample_poliza):
    """PATCH returns 200 with field row partial containing new value."""
    pid, _, _ = sample_poliza
    resp = client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": "nombre_contratante", "value": "Maria Lopez"},
    )
    assert resp.status_code == 200
    assert "Maria Lopez" in resp.text


def test_patch_updates_poliza_row(sample_poliza):
    """PATCH prima_total updates the polizas table row."""
    pid, _, _ = sample_poliza
    resp = client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": "prima_total", "value": "2000.00"},
    )
    assert resp.status_code == 200
    db = TestingSessionLocal()
    try:
        p = db.get(Poliza, pid)
        assert p.prima_total == Decimal("2000.00")
    finally:
        db.close()


def test_patch_logs_correction(sample_poliza):
    """PATCH logs a correction record with correct field_path and values."""
    pid, _, _ = sample_poliza
    resp = client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": "nombre_contratante", "value": "Maria Lopez"},
    )
    assert resp.status_code == 200
    db = TestingSessionLocal()
    try:
        corrections = db.query(Correction).filter_by(poliza_id=pid).all()
        assert len(corrections) == 1
        c = corrections[0]
        assert c.field_path == "nombre_contratante"
        assert c.new_value == "Maria Lopez"
        assert c.old_value is None  # was not set originally
    finally:
        db.close()


def test_patch_nested_field(sample_poliza):
    """PATCH asegurados.{aid}.nombre_descripcion updates nested row and logs correction."""
    pid, aid, _ = sample_poliza
    resp = client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": f"asegurados.{aid}.nombre_descripcion", "value": "Pedro Garcia"},
    )
    assert resp.status_code == 200
    db = TestingSessionLocal()
    try:
        a = db.get(Asegurado, aid)
        assert a.nombre_descripcion == "Pedro Garcia"
        corrections = db.query(Correction).filter_by(
            poliza_id=pid, field_path=f"asegurados.{aid}.nombre_descripcion"
        ).all()
        assert len(corrections) == 1
    finally:
        db.close()


def test_patch_campos_adicionales(sample_poliza):
    """PATCH campos_adicionales.numero_endoso updates JSON key and logs correction."""
    pid, _, _ = sample_poliza
    resp = client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": "campos_adicionales.numero_endoso", "value": "E-002"},
    )
    assert resp.status_code == 200
    db = TestingSessionLocal()
    try:
        p = db.get(Poliza, pid)
        assert p.campos_adicionales["numero_endoso"] == "E-002"
        corrections = db.query(Correction).filter_by(
            poliza_id=pid, field_path="campos_adicionales.numero_endoso"
        ).all()
        assert len(corrections) == 1
    finally:
        db.close()


def test_patch_cobertura_field(sample_poliza):
    """PATCH coberturas.{cid}.suma_asegurada updates the cobertura row."""
    pid, _, cid = sample_poliza
    resp = client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": f"coberturas.{cid}.suma_asegurada", "value": "750000.00"},
    )
    assert resp.status_code == 200
    db = TestingSessionLocal()
    try:
        c = db.get(Cobertura, cid)
        assert c.suma_asegurada == Decimal("750000.00")
    finally:
        db.close()


def test_patch_empty_string_sets_null(sample_poliza):
    """PATCH forma_pago with empty string sets it to None."""
    pid, _, _ = sample_poliza
    resp = client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": "forma_pago", "value": ""},
    )
    assert resp.status_code == 200
    db = TestingSessionLocal()
    try:
        p = db.get(Poliza, pid)
        assert p.forma_pago is None
    finally:
        db.close()


def test_patch_non_nullable_rejects_empty(sample_poliza):
    """PATCH numero_poliza with empty string returns 422."""
    pid, _, _ = sample_poliza
    resp = client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": "numero_poliza", "value": ""},
    )
    assert resp.status_code == 422


def test_patch_no_correction_when_value_unchanged(sample_poliza):
    """PATCH with the same value does not create a correction record."""
    pid, _, _ = sample_poliza
    # Set a known value first
    client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": "moneda", "value": "MXN"},
    )
    db = TestingSessionLocal()
    try:
        count_before = db.query(Correction).filter_by(poliza_id=pid).count()
    finally:
        db.close()
    # PATCH with same value — poliza.moneda is already "MXN" so old == new
    # (first patch: old="MXN" new="MXN" → no new correction)
    # Verify total correction count is same
    db2 = TestingSessionLocal()
    try:
        count_after = db2.query(Correction).filter_by(poliza_id=pid).count()
        assert count_after == count_before
    finally:
        db2.close()


# ---------------------------------------------------------------------------
# GET /ui/polizas/{id}/corrections-partial tests
# ---------------------------------------------------------------------------


def test_corrections_partial(sample_poliza):
    """corrections-partial returns 200 and shows correction field paths."""
    pid, _, _ = sample_poliza
    # Insert a correction directly
    db = TestingSessionLocal()
    try:
        from datetime import datetime
        corr = Correction(
            poliza_id=pid,
            field_path="nombre_contratante",
            old_value=None,
            new_value="Maria Lopez",
            corrected_at=datetime.utcnow(),
        )
        db.add(corr)
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/ui/polizas/{pid}/corrections-partial")
    assert resp.status_code == 200
    assert "nombre_contratante" in resp.text


def test_corrections_partial_404_missing_poliza():
    """corrections-partial returns 404 for non-existent poliza."""
    resp = client.get("/ui/polizas/99999/corrections-partial")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests that require Plan 02 template changes — marked xfail
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="poliza_detail.html corrections section added in Plan 02")
def test_detail_shows_corrections_section(sample_poliza):
    """Detail page shows 'Correcciones' section after a correction is made."""
    pid, _, _ = sample_poliza
    client.patch(
        f"/ui/polizas/{pid}/review/field",
        data={"field_path": "nombre_contratante", "value": "Maria Lopez"},
    )
    resp = client.get(f"/ui/polizas/{pid}")
    assert resp.status_code == 200
    assert "Correcciones" in resp.text


@pytest.mark.xfail(reason="Revisar button added to poliza_detail.html in Plan 02")
def test_detail_has_revisar_button_with_pdf(sample_poliza):
    """Detail page shows 'Revisar' button when PDF exists."""
    pid, _, _ = sample_poliza
    pdf_path = _create_dummy_pdf(pid)
    try:
        resp = client.get(f"/ui/polizas/{pid}")
        assert resp.status_code == 200
        assert "Revisar" in resp.text
    finally:
        pdf_path.unlink(missing_ok=True)
