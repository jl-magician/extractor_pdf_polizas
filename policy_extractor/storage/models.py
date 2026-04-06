"""SQLAlchemy 2.0 ORM models for policy data persistence."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship





class Base(DeclarativeBase):
    pass


class Poliza(Base):
    __tablename__ = "polizas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Core filterable columns
    numero_poliza: Mapped[str] = mapped_column(String, index=True)
    aseguradora: Mapped[str] = mapped_column(String, index=True)
    tipo_seguro: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    fecha_emision: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    inicio_vigencia: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    fin_vigencia: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    nombre_agente: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    nombre_contratante: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Monetary — Numeric not Float (DATA-04)
    prima_total: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    prima_neta: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    derecho_poliza: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    recargo: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    descuento: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    iva: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    otros_cargos: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    primer_pago: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    pago_subsecuente: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    moneda: Mapped[str] = mapped_column(String(3), default="MXN")

    # Payment info
    forma_pago: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    frecuencia_pago: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Provenance (DATA-05)
    source_file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # JSON overflow (DATA-02)
    campos_adicionales: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Evaluation fields (MIG-03, QAL-03 — populated by Phase 10 evaluator)
    evaluation_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    evaluation_json: Mapped[Optional[str]] = mapped_column(sa.Text(), nullable=True)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    evaluated_model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Validation warnings (EXT-02 — Phase 13)
    validation_warnings: Mapped[Optional[list]] = mapped_column(sa.JSON, nullable=True)

    # Relationships (DATA-01)
    asegurados: Mapped[list["Asegurado"]] = relationship(
        "Asegurado", back_populates="poliza", cascade="all, delete-orphan"
    )
    coberturas: Mapped[list["Cobertura"]] = relationship(
        "Cobertura", back_populates="poliza", cascade="all, delete-orphan"
    )
    corrections: Mapped[list["Correction"]] = relationship(
        "Correction", back_populates="poliza", cascade="all, delete-orphan",
        order_by="Correction.corrected_at"
    )


class Asegurado(Base):
    __tablename__ = "asegurados"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id"), index=True)

    # Discriminator (DATA-01)
    tipo: Mapped[str] = mapped_column(String)  # "persona" | "bien"
    nombre_descripcion: Mapped[str] = mapped_column(String)

    # Person fields (nullable for assets)
    fecha_nacimiento: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rfc: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    curp: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parentesco: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Type-specific extras (DATA-02)
    # Assets: {"tipo_bien": "vehiculo", "vin": "...", "placas": "..."} etc.
    campos_adicionales: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    poliza: Mapped["Poliza"] = relationship("Poliza", back_populates="asegurados")


class Cobertura(Base):
    __tablename__ = "coberturas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id"), index=True)

    nombre_cobertura: Mapped[str] = mapped_column(String)
    suma_asegurada: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    deducible: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=15, scale=2), nullable=True
    )
    moneda: Mapped[str] = mapped_column(String(3), default="MXN")

    # Insurer-specific extras (DATA-02)
    # Examples: coaseguro, copago, prima_individual, periodo_espera
    campos_adicionales: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    poliza: Mapped["Poliza"] = relationship("Poliza", back_populates="coberturas")


class IngestionCache(Base):
    __tablename__ = "ingestion_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    file_path: Mapped[str] = mapped_column(String)
    total_pages: Mapped[int] = mapped_column()
    page_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ocr_language: Mapped[str] = mapped_column(String, default="spa")


class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id", ondelete="CASCADE"), index=True)
    field_path: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    poliza: Mapped["Poliza"] = relationship("Poliza", back_populates="corrections")


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    total_files: Mapped[int] = mapped_column(default=0)
    completed_files: Mapped[int] = mapped_column(default=0)
    failed_files: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    results_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
