from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class CoberturaExtraction(BaseModel):
    """Single coverage line item on a policy."""

    nombre_cobertura: str
    suma_asegurada: Optional[Decimal] = None
    deducible: Optional[Decimal] = None
    moneda: str = "MXN"

    # Insurer-specific extras: coaseguro, copago, prima_individual, periodo_espera
    campos_adicionales: dict = Field(default_factory=dict)
