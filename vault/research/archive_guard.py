"""Archive guardrail — only archive entries when ALL 3 conditions are met.

Conditions:
    1. No access for 90+ days   (last_accessed_at >= 90 days ago)
    2. No active references      (all sources have event_at >= 90 days ago)
    3. No pending conflicts      (conflicts list empty or no 'pending' status)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


REF_ARCHIVE_DAYS = 90


def can_archive(entry: dict[str, Any]) -> bool:
    """Return True if the entry is eligible for archiving.

    An entry can be archived only when ALL three conditions are met:
        1. last_accessed_at is 90+ days ago (or None)
        2. all sources have event_at >= 90 days ago
        3. no conflicts with status 'pending'
    """
    return (
        _no_access_90days(entry) and
        _no_active_references(entry) and
        _no_pending_conflicts(entry)
    )


def _no_access_90days(entry: dict[str, Any]) -> bool:
    """Condition 1: entry has not been accessed in the last 90 days."""
    last_accessed = entry.get("last_accessed_at")
    if last_accessed is None:
        # No access record = never accessed, satisfies condition
        return True
    return _days_ago(last_accessed) >= REF_ARCHIVE_DAYS


def _no_active_references(entry: dict[str, Any]) -> bool:
    """Condition 2: no sources with recent event_at within 90 days."""
    sources = entry.get("sources", [])
    if not sources:
        return True
    return all(
        _days_ago(s.get("event_at") or "1970-01-01T00:00:00+00:00") >= REF_ARCHIVE_DAYS
        for s in sources
    )


def _no_pending_conflicts(entry: dict[str, Any]) -> bool:
    """Condition 3: no conflicts with status 'pending'."""
    conflicts = entry.get("conflicts", [])
    if not conflicts:
        return True
    return all(c.get("status") != "pending" for c in conflicts)


def _days_ago(iso_timestamp: str) -> float:
    """Return the number of days since the given ISO timestamp."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    now = datetime(2026, 4, 18, tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 86400
