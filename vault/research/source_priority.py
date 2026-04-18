"""Source priority resolver for cross-source conflict resolution.

Priority order (highest to lowest): github > tldv > trello

Resolution rules:
    1. Higher source priority wins
    2. If tie on priority → most recent event_at wins
    3. If total tie → conflict:pending

Usage:
    from vault.research.source_priority import resolve_conflict

    result = resolve_conflict("entity_123", [
        {"source": "github", "identifier": "gh_001", "event_at": "2026-04-01T00:00:00Z"},
        {"source": "tldv", "identifier": "tldv_001", "event_at": "2026-04-15T00:00:00Z"},
    ])
    # result = {"resolved": "gh_001", "confidence": 1.0, "reason": "github priority 3 > tldv priority 2"}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# Priority order: github > tldv > trello
SOURCE_PRIORITY: dict[str, int] = {
    "github": 3,
    "tldv": 2,
    "trello": 1,
}

# Default priority for unknown sources
DEFAULT_PRIORITY = 0


def resolve_conflict(
    entity_id: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve cross-source conflict for an entity.

    Args:
        entity_id: The entity identifier being resolved.
        candidates: List of candidate entities from different sources.
            Each candidate must have: source, identifier.
            Optional: event_at (ISO str), conflict (str).

    Returns:
        {
            "resolved": str,      # identifier of winner or "conflict:pending"
            "confidence": float,  # 1.0 for resolved, <1.0 for pending
            "reason": str,        # human-readable explanation
        }
    """
    if not candidates:
        return {
            "resolved": "conflict:pending",
            "confidence": 0.0,
            "reason": "no candidates",
        }

    # Score each candidate
    scored = []
    for cand in candidates:
        priority = SOURCE_PRIORITY.get(cand.get("source", ""), DEFAULT_PRIORITY)
        event_at = _parse_event_at(cand.get("event_at"))
        conflict = cand.get("conflict")
        conflict_pending = 1 if conflict == "pending" else 0

        scored.append({
            "candidate": cand,
            "priority": priority,
            "event_at": event_at,
            "conflict_pending": conflict_pending,
        })

    # Sort by: priority DESC, event_at DESC, conflict_pending DESC
    scored.sort(key=lambda x: (x["priority"], x["event_at"], x["conflict_pending"]), reverse=True)

    top = scored[0]
    top_priority = top["priority"]
    top_event_at = top["event_at"]
    top_conflict_pending = top["conflict_pending"]

    # Check for ties
    ties = [
        s for s in scored
        if s["priority"] == top_priority
        and s["event_at"] == top_event_at
        and s["conflict_pending"] == top_conflict_pending
    ]

    if len(ties) > 1:
        # True tie → conflict:pending
        return {
            "resolved": "conflict:pending",
            "confidence": 0.5,
            "reason": f"conflict:pending (tie between {len(ties)} candidates)",
        }

    # Winner found
    winner = top["candidate"]
    source = winner.get("source", "unknown")
    priority_val = SOURCE_PRIORITY.get(source, DEFAULT_PRIORITY)

    same_priority = [s for s in scored if s["priority"] == top_priority]
    if len(same_priority) > 1:
        reason = f"{source} priority {priority_val}; most recent event_at"
    else:
        reason = f"{source} priority {priority_val}"

    return {
        "resolved": winner.get("identifier"),
        "confidence": 1.0,
        "reason": reason,
    }


def _parse_event_at(event_at_str: str | None) -> datetime:
    """Parse event_at string to datetime, returning epoch on failure."""
    if not event_at_str:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        # Handle Z suffix
        return datetime.fromisoformat(event_at_str.replace("Z", "+00:00"))
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
