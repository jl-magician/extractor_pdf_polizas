"""Persistent extraction rules — user-approved corrections applied to every extraction.

Rules are stored in data/extraction_rules.json and loaded into the system prompt
on every extraction call.

Usage:
    from policy_extractor.extraction.rules import load_rules, add_rule, remove_rule, get_rules_prompt
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "extraction_rules.json"


def _ensure_file() -> None:
    """Create the rules file if it doesn't exist."""
    _RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _RULES_PATH.exists():
        _RULES_PATH.write_text("[]", encoding="utf-8")


def load_rules() -> list[dict]:
    """Load all extraction rules from disk."""
    _ensure_file()
    try:
        return json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def add_rule(field: str, instruction: str, source_poliza: Optional[str] = None) -> dict:
    """Add a new extraction rule and return it."""
    rules = load_rules()
    rule = {
        "id": len(rules) + 1,
        "field": field,
        "instruction": instruction,
        "source_poliza": source_poliza,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rules.append(rule)
    _RULES_PATH.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")
    return rule


def remove_rule(rule_id: int) -> bool:
    """Remove a rule by ID. Returns True if found and removed."""
    rules = load_rules()
    new_rules = [r for r in rules if r.get("id") != rule_id]
    if len(new_rules) == len(rules):
        return False
    _RULES_PATH.write_text(json.dumps(new_rules, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def get_rules_prompt() -> str:
    """Build a prompt section from all active extraction rules.

    Returns empty string if no rules exist.
    """
    rules = load_rules()
    if not rules:
        return ""

    lines = ["\n\n## Learned Extraction Rules (MUST FOLLOW)\n"]
    lines.append("These rules were validated by the user. Apply them to ALL extractions:\n")
    for rule in rules:
        lines.append(f"- **{rule['field']}**: {rule['instruction']}")
    return "\n".join(lines)
