"""
vault/qw2/fact_check.py — QW-2 fact-check wrapper.
Uses vault.fact_check.score_confidence() to calculate confidence_level.
"""
from __future__ import annotations

import sys
from pathlib import Path as _Path
from typing import Any, TypedDict

_WS = _Path(__file__).resolve().parents[2]
if str(_WS) not in sys.path:
    sys.path.insert(0, str(_WS))

from vault.fact_check import score_confidence


class Decision(TypedDict):
    source: str  # tldv | github | trello
    source_ref: str
    confidence_level: str | None
    corroborated_sources: list[str] | None


def enrich_decision(decision: Decision) -> dict[str, Any]:
    """
    Recebe decision dict com 'source' (tldv/github/trello).
    Retorna decision com 'confidence_level' adicionado.

    Mapping:
    - tldv  → official+=1
    - github → official+=1
    - trello → indirect+=1
    - corroborated_sources (list) → corroborated += len(list)

    Usa vault/fact_check.score_confidence():
    - high:      2+ official OR 1 official + 1+ corroborated
    - medium:    1 official OR 2+ indirect
    - low:       1 indirect
    - unverified: no evidence
    """
    if decision.get("confidence_level"):
        return decision  # skip se já calculado

    source = decision.get("source", "")
    official = 0
    corroborated = 0
    indirect = 0

    if source == "tldv":
        official += 1
    elif source == "github":
        official += 1
    elif source == "trello":
        indirect += 1

    # corroborated sources elevam o nível
    corrob = decision.get("corroborated_sources") or []
    corroborated = len(corrob)

    level = score_confidence(official, corroborated, indirect)
    decision["confidence_level"] = level
    return decision


def enrich_decisions(decisions: list[Decision]) -> list[Decision]:
    """Batch version of enrich_decision."""
    return [enrich_decision(d) for d in decisions]
