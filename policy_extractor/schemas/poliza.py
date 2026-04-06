from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .asegurado import AseguradoExtraction
from .cobertura import CoberturaExtraction


class PolicyExtraction(BaseModel):
    """Extraction contract for a single insurance policy.

    Field names in Spanish — agency team reads JSON output directly.
    Used by: instructor (Phase 3), storage/writer.py (Phase 5).
    """

    model_config = ConfigDict(populate_by_name=True)

    # Identity (required)
    numero_poliza: str
    aseguradora: str

    # Policy metadata
    tipo_seguro: Optional[str] = None
    fecha_emision: Optional[date] = None
    inicio_vigencia: Optional[date] = None
    fin_vigencia: Optional[date] = None

    # Parties
    nombre_contratante: Optional[str] = None
    nombre_agente: Optional[str] = None

    # Financial
    prima_total: Optional[Decimal] = None
    prima_neta: Optional[Decimal] = None
    derecho_poliza: Optional[Decimal] = None
    recargo: Optional[Decimal] = None
    descuento: Optional[Decimal] = None
    iva: Optional[Decimal] = None
    otros_cargos: Optional[Decimal] = None
    primer_pago: Optional[Decimal] = None
    pago_subsecuente: Optional[Decimal] = None
    moneda: str = "MXN"
    forma_pago: Optional[str] = None
    frecuencia_pago: Optional[str] = None

    # Related objects (one-to-many)
    asegurados: list[AseguradoExtraction] = Field(default_factory=list)
    coberturas: list[CoberturaExtraction] = Field(default_factory=list)

    # Provenance (DATA-05)
    source_file_hash: Optional[str] = None   # sha256 hex string
    model_id: Optional[str] = None           # e.g., "claude-sonnet-4-6-20250514"
    prompt_version: Optional[str] = None     # e.g., "v1.0.0"
    extracted_at: Optional[datetime] = None  # UTC timestamp

    # Overflow (DATA-02)
    campos_adicionales: dict = Field(default_factory=dict)

    # Confidence per field (EXT-04)
    confianza: dict = Field(default_factory=dict)

    # Post-extraction validation warnings (EXT-02)
    validation_warnings: list[dict] = Field(default_factory=list)

    @field_validator("fecha_emision", "inicio_vigencia", "fin_vigencia", mode="before")
    @classmethod
    def normalize_date(cls, v):
        """Normalize DD/MM/YYYY, MM/DD/YYYY, and ISO 8601 to date objects."""
        if v is None or isinstance(v, date):
            return v
        if isinstance(v, str) and v.strip():
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(v.strip(), fmt).date()
                except ValueError:
                    continue
        return None  # Unknown format -> null, logged by extraction layer
