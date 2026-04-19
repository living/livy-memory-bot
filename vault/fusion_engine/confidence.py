"""Confidence scoring for claims.

Formula:
  base 0.5
  + source_reliability  (github/tldv: +0.2, gmail: +0.15, trello/gcal: +0.1)
  + recency             (<7d: +0.2, <30d: +0.1, <90d: 0, >90d: -0.2)
  + convergence         (+0.1 per distinct source, max +0.3)
  - contradiction       (-0.3 if contradicting_claim is provided)
  clamp final to [0.0, 1.0]
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from vault.memory_core.models import Claim, Source


# Source reliability multipliers
_SOURCE_RELIABILITY: dict[Source, float] = {
    "github": 0.2,
    "tldv": 0.2,
    "gmail": 0.15,
    "trello": 0.1,
    "gcal": 0.1,
}

# Recency thresholds (in days)
_RECENCY_THRESHOLDS = [
    (7, 0.2),    # < 7 days
    (30, 0.1),   # < 30 days
    (90, 0.0),   # < 90 days
    (float("inf"), -0.2),  # >= 90 days
]

# Convergence bonus per distinct source
_CONVERGENCE_BONUS_PER_SOURCE = 0.1
_CONVERGENCE_MAX = 0.3

# Contradiction penalty
_CONTRADICTION_PENALTY = 0.3

# Base confidence
_BASE_CONFIDENCE = 0.5


def _days_old(event_timestamp: str) -> float:
    """Return fractional days between event_timestamp and now."""
    try:
        ts = datetime.fromisoformat(event_timestamp)
    except ValueError:
        # Malformed timestamp — treat as ancient
        return float("inf")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - ts
    return delta.total_seconds() / 86400.0


def _recency_score(event_timestamp: str) -> float:
    """Return recency modifier based on how old a claim is."""
    days = _days_old(event_timestamp)
    for threshold, bonus in _RECENCY_THRESHOLDS:
        if days < threshold:
            return bonus
    return -0.2  # fallback


def compute_confidence(
    claim: Claim,
    contradicting_claim: Claim | None,
    other_sources: list[Source] | None = None,
) -> float:
    """Compute confidence score for a claim.

    Parameters
    ----------
    claim:
        The claim to score.
    contradicting_claim:
        If provided, applies the contradiction penalty.
    other_sources:
        Additional sources contributing to this claim's topic.
        Each distinct source adds +0.1 (capped at +0.3).
    """
    score = _BASE_CONFIDENCE

    # Source reliability
    score += _SOURCE_RELIABILITY.get(claim.source, 0.0)

    # Recency
    score += _recency_score(claim.event_timestamp)

    # Convergence
    if other_sources:
        convergence = min(
            len(other_sources) * _CONVERGENCE_BONUS_PER_SOURCE,
            _CONVERGENCE_MAX,
        )
        score += convergence

    # Contradiction penalty
    if contradicting_claim is not None:
        score -= _CONTRADICTION_PENALTY

    # Clamp
    return max(0.0, min(1.0, score))
