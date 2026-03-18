"""Pydantic v2 extraction schemas — the data contract for all downstream phases."""
from .asegurado import AseguradoExtraction
from .cobertura import CoberturaExtraction
from .poliza import PolicyExtraction

__all__ = ["PolicyExtraction", "AseguradoExtraction", "CoberturaExtraction"]
