from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AseguradoExtraction(BaseModel):
    """Single insured party — either a person (persona) or an asset (bien)."""

    tipo: Literal["persona", "bien"]
    nombre_descripcion: str

    # Person-specific (None for assets)
    fecha_nacimiento: Optional[date] = None
    rfc: Optional[str] = None
    curp: Optional[str] = None
    direccion: Optional[str] = None
    parentesco: Optional[str] = None

    # Type-specific extras in JSON overflow
    # Assets: {"tipo_bien": "vehiculo", "marca": "Toyota", "modelo": "Corolla",
    #          "anio": 2022, "placas": "ABC1234", "vin": "1HGCM82633A004352"}
    # Persons: additional fields not captured by typed columns
    campos_adicionales: dict = Field(default_factory=dict)
