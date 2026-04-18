"""Identity resolver — email-first + fallback context.

Input:
    source (str): the source system of the identifier being resolved (e.g. "github")
    identifier (str): the unique id in that source
    email (str|None): optional email address of the identity
    username (str|None): optional username/handle
    name (str|None): optional display name
    candidates (list[dict]): possible existing persons to link to.
        Each candidate has: source, identifier, email?, username?, name?,
                            sources? (list), event_at? (str ISO), conflict? (str)

Output:
    {
        "confidence": float,   # 0.0–1.0
        "reason": str,
        "link_to": str|None,   # identifier of the winning candidate, or None
    }

Thresholds (Phase 1):
    auto-link   : confidence >= 0.60
    review_band : 0.45 <= confidence < 0.60  → link_to = None (needs review)
    no-link     : confidence < 0.45          → link_to = None

Scoring:
    email exact match   → base 0.90
    username partial    → base 0.60 (+0.15 boost if added on top of another signal)
    name match          → base 0.50 (review_band territory)

Tie-break order inside review_band (highest priority first):
    1. Most source affiliations (len of candidate["sources"])
    2. Most recent event_at
    3. Has conflict == "pending"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def resolve_identity(
    source: str,
    identifier: str,
    candidates: list[dict[str, Any]],
    email: str | None = None,
    username: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Resolve the given identity against a list of candidates.

    Returns the highest-confidence match, or no-link when none qualifies.
    """
    if not candidates:
        return {"confidence": 0.0, "reason": "no candidates", "link_to": None}

    # Filter out candidates from the same source (don't self-link)
    others = [c for c in candidates if c.get("source") != source]
    if not others:
        return {"confidence": 0.0, "reason": "no candidates from other sources", "link_to": None}

    scored: list[dict[str, Any]] = []
    for candidate in others:
        confidence, reason = _score(candidate, email=email, username=username, name=name)
        # Cap at 1.0
        confidence = min(1.0, confidence)
        scored.append({"candidate": candidate, "confidence": confidence, "reason": reason})

    if not scored:
        return {"confidence": 0.0, "reason": "no candidates", "link_to": None}

    # Pick best
    best = max(scored, key=lambda x: x["confidence"])
    confidence = best["confidence"]
    reason = best["reason"]
    candidate = best["candidate"]

    if confidence >= 0.60:
        # auto-link
        return {
            "confidence": float(confidence),
            "reason": reason,
            "link_to": candidate["identifier"],
        }
    elif confidence >= 0.45:
        # review_band — apply tie-breakers across all candidates in this band
        band = [s for s in scored if 0.45 <= s["confidence"] < 0.60]
        winner = _tiebreak(band)
        winner_id = winner["candidate"].get("identifier")
        return {
            "confidence": float(winner["confidence"]),
            "reason": f"review_band winner={winner_id}: {winner['reason']}",
            "link_to": None,  # No auto-link in review band
        }
    else:
        return {
            "confidence": float(confidence),
            "reason": reason,
            "link_to": None,
        }


def _score(
    candidate: dict[str, Any],
    email: str | None,
    username: str | None,
    name: str | None,
) -> tuple[float, str]:
    """Compute (confidence, reason) for a single candidate."""
    confidence = 0.0
    reasons: list[str] = []

    # --- Rule 1: email exact match → 0.90 base ---
    cand_email = candidate.get("email")
    if email and cand_email and email.lower() == cand_email.lower():
        confidence += 0.90
        reasons.append("email exact match")

    # --- Rule 2: username partial match → +0.15 boost (base 0.60 if no other signal) ---
    cand_username = candidate.get("username")
    if username and cand_username:
        if _username_matches(username, cand_username):
            if confidence == 0.0:
                # No prior signal — username alone: base 0.60
                confidence = 0.60
                reasons.append("username match (base 0.60)")
            else:
                # Boost on top of existing signal
                confidence += 0.15
                reasons.append("username match (+0.15 boost)")

    # --- Rule 3: name match → base 0.50 (review_band) ---
    cand_name = candidate.get("name")
    if name and cand_name and name.lower() == cand_name.lower():
        if confidence == 0.0:
            confidence = 0.50
            reasons.append("name match (base 0.50)")

    reason = "; ".join(reasons) if reasons else "no match signal"
    return confidence, reason


def _username_matches(a: str, b: str) -> bool:
    """Partial username match: exact or one contains the other."""
    a_low, b_low = a.lower(), b.lower()
    return a_low == b_low or a_low in b_low or b_low in a_low


def _tiebreak(band: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the winner within the review_band using explicit tie-breakers.

    Order: most sources > most recent event_at > conflict:pending.
    Falls back to first in list when still tied.
    """
    def sort_key(entry: dict[str, Any]) -> tuple:
        cand = entry["candidate"]

        # 1. Number of source affiliations (more = better)
        sources_count = len(cand.get("sources", []))

        # 2. Most recent event_at (parse ISO; None → epoch)
        event_at_str = cand.get("event_at")
        if event_at_str:
            try:
                # Handle Z suffix
                dt = datetime.fromisoformat(event_at_str.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime(1970, 1, 1, tzinfo=timezone.utc)
        else:
            dt = datetime(1970, 1, 1, tzinfo=timezone.utc)

        # 3. conflict:pending preferred (1 > 0)
        conflict_score = 1 if cand.get("conflict") == "pending" else 0

        return (sources_count, dt, conflict_score)

    return max(band, key=sort_key)
