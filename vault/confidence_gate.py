"""
vault/confidence_gate.py — source-aware confidence write-gate.
"""
from __future__ import annotations

from typing import Any

_OFFICIAL = {"exec", "openclaw_config", "api_direct", "tldv_api", "github_api", "supabase_rest"}
_CORROBORATED = {"curated_topic"}
_INDIRECT = {"signal_event", "observation", "chat_history"}


def classify_source(source: dict) -> str:
    stype = str(source.get("type", "") or "")
    if stype in _OFFICIAL:
        return "official"
    if stype in _CORROBORATED:
        return "corroborated"
    return "indirect"


def score_confidence(official: int, corroborated: int, indirect: int) -> str:
    if official >= 2:
        return "high"
    if official >= 1 and corroborated >= 1:
        return "high"
    if official >= 1:
        return "medium"
    if indirect >= 2:
        return "medium"
    if indirect == 1:
        return "low"
    return "unverified"


def score_from_sources(sources: list[dict]) -> str:
    official = sum(1 for s in sources if classify_source(s) == "official")
    corroborated = sum(1 for s in sources if classify_source(s) == "corroborated")
    indirect = sum(1 for s in sources if classify_source(s) == "indirect")
    return score_confidence(official, corroborated, indirect)


def gate_decision(sources: list[dict]) -> dict:
    conf = score_from_sources(sources)
    return {
        "allowed": True,
        "enforced_confidence": conf,
        "source_count": len(sources),
    }
