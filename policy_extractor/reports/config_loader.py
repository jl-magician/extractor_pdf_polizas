"""Per-insurer YAML config loader for PDF report generation.

Exports:
    load_insurer_config(aseguradora: str) -> dict
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_CONFIGS_DIR = Path(__file__).parent / "configs"


@lru_cache(maxsize=16)
def _load_config_by_name(normalized_name: str) -> dict:
    """Load a YAML config by normalized insurer name (cached).

    Falls back to default.yaml if no insurer-specific file exists.
    Never raises FileNotFoundError.
    """
    config_path = _CONFIGS_DIR / f"{normalized_name}.yaml"
    if not config_path.exists():
        config_path = _CONFIGS_DIR / "default.yaml"
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def load_insurer_config(aseguradora: str) -> dict:
    """Load per-insurer report configuration from YAML.

    Args:
        aseguradora: Insurer name (case-insensitive, spaces normalized).

    Returns:
        dict with keys: brand_color, display_name, field_order, sections.
        Falls back to default.yaml for unknown insurers.
    """
    normalized = aseguradora.lower().strip().replace(" ", "_")
    return _load_config_by_name(normalized)
