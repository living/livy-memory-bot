"""Tests for vault/research/archive_guard.py — archive eligibility guardrails.

An entry may only be archived if ALL three conditions are met:
    1. No access for 90+ days  (last_accessed_at is 90+ days ago)
    2. No active references     (no sources with recent event_at)
    3. No pending conflicts     (conflicts list is empty or no 'pending' status)
"""
from datetime import datetime, timedelta, timezone

import pytest

from vault.research.archive_guard import can_archive


# ---------------------------------------------------------------------------
# Signature & output
# ---------------------------------------------------------------------------


def test_can_archive_returns_bool():
    """can_archive(entry) must return a bool."""
    entry = _make_entry(last_accessed_days_ago=100)
    result = can_archive(entry)
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Condition 1: last_accessed_at >= 90 days ago
# ---------------------------------------------------------------------------


def test_cannot_archive_recently_accessed():
    """Entry accessed within 90 days must NOT be archived."""
    entry = _make_entry(last_accessed_days_ago=30)
    assert can_archive(entry) is False


def test_cannot_archive_exactly_89_days_ago():
    """Entry accessed 89 days ago must NOT be archived (boundary)."""
    entry = _make_entry(last_accessed_days_ago=89)
    assert can_archive(entry) is False


def test_can_archive_90_days_ago():
    """Entry not accessed for exactly 90 days can archive when other conditions are met."""
    entry = _make_entry(last_accessed_days_ago=90, source_event_days_ago=200, conflicts=[])
    assert can_archive(entry) is True


def test_can_archive_very_old_access():
    """Entry with very old access can archive when other conditions are met."""
    entry = _make_entry(last_accessed_days_ago=365, source_event_days_ago=200, conflicts=[])
    assert can_archive(entry) is True


def test_can_archive_no_last_accessed_at():
    """Entry with no last_accessed_at is treated as never accessed."""
    entry = _make_entry(last_accessed_days_ago=None, source_event_days_ago=200, conflicts=[])
    assert can_archive(entry) is True


# ---------------------------------------------------------------------------
# Condition 2: No active references (no recent sources)
# ---------------------------------------------------------------------------


def test_cannot_archive_with_recent_source_event():
    """Entry with a source event within 90 days has active reference."""
    entry = _make_entry(
        last_accessed_days_ago=100,
        source_event_days_ago=30,
    )
    assert can_archive(entry) is False


def test_cannot_archive_with_source_event_exactly_89_days():
    """Entry with source event 89 days ago has active reference."""
    entry = _make_entry(
        last_accessed_days_ago=100,
        source_event_days_ago=89,
    )
    assert can_archive(entry) is False


def test_can_archive_no_sources():
    """Entry with no sources may archive when no pending conflicts and old/no access."""
    entry = _make_entry(last_accessed_days_ago=100, sources=[], conflicts=[])
    assert can_archive(entry) is True


# ---------------------------------------------------------------------------
# Condition 3: No pending conflicts
# ---------------------------------------------------------------------------


def test_cannot_archive_with_pending_conflict():
    """Entry with a pending conflict must NOT be archived."""
    entry = _make_entry(
        last_accessed_days_ago=100,
        conflicts=[{"status": "pending", "type": "merge"}],
    )
    assert can_archive(entry) is False


def test_can_archive_resolved_conflict():
    """Entry with only resolved conflicts may be archived."""
    entry = _make_entry(
        last_accessed_days_ago=100,
        source_event_days_ago=200,
        conflicts=[{"status": "resolved", "type": "merge"}],
    )
    assert can_archive(entry) is True


def test_can_archive_no_conflicts():
    """Entry with no conflicts may be archived when other conditions are met."""
    entry = _make_entry(last_accessed_days_ago=100, source_event_days_ago=200, conflicts=[])
    assert can_archive(entry) is True


# ---------------------------------------------------------------------------
# All conditions — happy path
# ---------------------------------------------------------------------------


def test_can_archive_all_conditions_met():
    """Entry with all 3 conditions met CAN be archived."""
    entry = _make_entry(
        last_accessed_days_ago=100,
        sources=[{"event_at": "2024-01-01T00:00:00Z"}],
        conflicts=[],
    )
    assert can_archive(entry) is True


def test_cannot_archive_only_two_conditions_met():
    """Archive requires ALL three conditions — two is not enough."""
    # Condition 1 met, but has pending conflict
    entry1 = _make_entry(
        last_accessed_days_ago=100,
        conflicts=[{"status": "pending", "type": "merge"}],
    )
    assert can_archive(entry1) is False

    # Condition 1 met, but has recent source
    entry2 = _make_entry(
        last_accessed_days_ago=100,
        source_event_days_ago=30,
    )
    assert can_archive(entry2) is False

    # Condition 2 & 3 met, but recent access
    entry3 = _make_entry(
        last_accessed_days_ago=30,
        sources=[{"event_at": "2024-01-01T00:00:00Z"}],
        conflicts=[],
    )
    assert can_archive(entry3) is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    last_accessed_days_ago: int | None = 100,
    sources: list | None = None,
    source_event_days_ago: int | None = 200,
    conflicts: list | None = None,
) -> dict:
    """Build a minimal entry dict for testing."""
    now = datetime(2026, 4, 18, tzinfo=timezone.utc)

    if last_accessed_days_ago is not None:
        last_accessed_at = (now - timedelta(days=last_accessed_days_ago)).isoformat()
    else:
        last_accessed_at = None

    if sources is None:
        if source_event_days_ago is not None:
            source_event_at = (now - timedelta(days=source_event_days_ago)).isoformat()
        else:
            source_event_at = None
        sources = [{"event_at": source_event_at}] if source_event_at else []

    return {
        "last_accessed_at": last_accessed_at,
        "sources": sources,
        "conflicts": conflicts if conflicts is not None else [],
    }
