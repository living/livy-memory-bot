"""
vault/fact_check.py — Confidence scoring and fact-check cache.
Phase 1B: Implements AGENTS.md Context7 policy.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "memory" / "vault" / ".cache" / "fact-check"
CACHE_TTL_SECONDS = 86400  # 24 hours

# ------------------------------------------------------------------
# Confidence scoring
# ------------------------------------------------------------------

def score_confidence(official: int, corroborated: int, indirect: int) -> str:
    """
    Map source counts to a confidence level per AGENTS.md rules.

    high  : 2+ official OR 1 official + 1 corroborated
    medium: 1 official OR 2+ indirect
    low   : 1 indirect
    unverified: no evidence
    """
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


# ------------------------------------------------------------------
# Source classification
# ------------------------------------------------------------------

_OFFICIAL_TYPES = {
    "exec", "openclaw_config", "api_direct",
    "tldv_api", "github_api", "supabase_rest",
}
_CORROBORATED_TYPES = {"curated_topic"}
_INDIRECT_TYPES = {
    "signal_event", "observation", "chat_history",
}


def classify_source(source: dict) -> str:
    """Classify a single source dict as official/corroborated/indirect."""
    stype = source.get("type", "")
    if stype in _OFFICIAL_TYPES:
        return "official"
    if stype in _CORROBORATED_TYPES:
        return "corroborated"
    return "indirect"


def score_from_sources(sources: list[dict]) -> str:
    """Aggregate a list of sources into a confidence level."""
    official = sum(1 for s in sources if classify_source(s) == "official")
    corroborated = sum(1 for s in sources if classify_source(s) == "corroborated")
    indirect = sum(1 for s in sources if classify_source(s) == "indirect")
    return score_confidence(official, corroborated, indirect)


# ------------------------------------------------------------------
# Cache TTL helpers
# ------------------------------------------------------------------

def _is_stale(checked_at: datetime, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    age = now - checked_at
    return age.total_seconds() > CACHE_TTL_SECONDS


# ------------------------------------------------------------------
# Safe cache keys
# ------------------------------------------------------------------

def _safe_key(key: str) -> str:
    """Sanitise a cache key to a safe filename (no path traversal)."""
    safe = hashlib.sha256(key.encode()).hexdigest()[:32]
    return f"{safe}.json"


# ------------------------------------------------------------------
# Cache I/O
# ------------------------------------------------------------------

CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_cache_dir() -> None:
    """Ensure the cache directory exists. Call before any cache operation."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_get(key: str) -> dict | None:
    """Load a cached fact-check result, or None if missing/stale."""
    if not key:
        return None
    _ensure_cache_dir()
    cache_file = CACHE_DIR / _safe_key(key)
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        checked_at_str = data.get("checked_at", "")
        checked_at = datetime.fromisoformat(checked_at_str)
        if _is_stale(checked_at):
            return None
        return data
    except Exception:
        return None


def cache_set(key: str, data: dict) -> None:
    """Write a fact-check result to the cache."""
    if not key:
        return
    _ensure_cache_dir()
    cache_file = CACHE_DIR / _safe_key(key)
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def cached_lookup(key: str) -> dict | None:
    """Alias for cache_get — checks cache first."""
    return cache_get(key)
