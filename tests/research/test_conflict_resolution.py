"""Tests for vault/research/source_priority.py — cross-source conflict resolution."""
from datetime import datetime, timezone

import pytest

from vault.research.source_priority import resolve_conflict, SOURCE_PRIORITY


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


def test_source_priority_exists():
    """SOURCE_PRIORITY must be defined as dict with required keys."""
    assert isinstance(SOURCE_PRIORITY, dict)
    assert "github" in SOURCE_PRIORITY
    assert "tldv" in SOURCE_PRIORITY
    assert "trello" in SOURCE_PRIORITY
    # github > tldv > trello
    assert SOURCE_PRIORITY["github"] > SOURCE_PRIORITY["tldv"] > SOURCE_PRIORITY["trello"]


def test_source_priority_values():
    """SOURCE_PRIORITY values must be github=3, tldv=2, trello=1."""
    assert SOURCE_PRIORITY["github"] == 3
    assert SOURCE_PRIORITY["tldv"] == 2
    assert SOURCE_PRIORITY["trello"] == 1


# ---------------------------------------------------------------------------
# resolve_conflict signature
# ---------------------------------------------------------------------------


def test_resolve_conflict_returns_dict():
    """Output must be a dict."""
    result = resolve_conflict("entity_1", [])
    assert isinstance(result, dict)


def test_resolve_conflict_has_required_keys():
    """Output must contain: resolved (str), confidence (float), reason (str)."""
    result = resolve_conflict("entity_1", [])
    assert "resolved" in result
    assert "confidence" in result
    assert "reason" in result


def test_resolve_conflict_confidence_is_float():
    """confidence must always be a float."""
    result = resolve_conflict("entity_1", [])
    assert isinstance(result["confidence"], float)


def test_resolve_conflict_requires_entity_id():
    """First arg must be the entity_id being resolved."""
    result = resolve_conflict("entity_abc", [])
    assert result is not None


# ---------------------------------------------------------------------------
# Rule 1: Priority wins (github > tldv > trello)
# ---------------------------------------------------------------------------


def test_github_wins_over_tldv():
    """GitHub source must win over TLDV when all else equal."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "ent_tldv_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
        {
            "source": "github",
            "identifier": "ent_gh_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_gh_001"
    assert "github" in result["reason"].lower()


def test_github_wins_over_trello():
    """GitHub source must win over Trello when all else equal."""
    candidates = [
        {
            "source": "trello",
            "identifier": "ent_trello_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
        {
            "source": "github",
            "identifier": "ent_gh_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_gh_001"


def test_tldv_wins_over_trello():
    """TLDV source must win over Trello when all else equal."""
    candidates = [
        {
            "source": "trello",
            "identifier": "ent_trello_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
        {
            "source": "tldv",
            "identifier": "ent_tldv_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_tldv_001"


def test_single_candidate_wins():
    """Single candidate always wins."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "ent_tldv_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_tldv_001"


# ---------------------------------------------------------------------------
# Rule 2: Tie on priority → most recent event_at wins
# ---------------------------------------------------------------------------


def test_tie_priority_most_recent_wins():
    """When two sources have equal priority, most recent event_at wins."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "ent_tldv_001",
            "event_at": "2026-01-01T00:00:00Z",
        },
        {
            "source": "tldv",
            "identifier": "ent_tldv_002",
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_tldv_002"
    assert "event_at" in result["reason"].lower() or "recent" in result["reason"].lower()


def test_github_tie_most_recent_wins():
    """GitHub tie broken by most recent event_at."""
    candidates = [
        {
            "source": "github",
            "identifier": "ent_gh_001",
            "event_at": "2026-01-01T00:00:00Z",
        },
        {
            "source": "github",
            "identifier": "ent_gh_002",
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_gh_002"


def test_none_event_at_is_oldest():
    """Missing event_at treated as oldest (epoch)."""
    candidates = [
        {
            "source": "github",
            "identifier": "ent_gh_001",
            "event_at": None,
        },
        {
            "source": "github",
            "identifier": "ent_gh_002",
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_gh_002"


# ---------------------------------------------------------------------------
# Rule 3: Total tie → conflict:pending
# ---------------------------------------------------------------------------


def test_total_tie_returns_pending():
    """When priority and event_at are identical, conflict:pending."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "ent_tldv_A",
            "event_at": "2026-04-01T00:00:00Z",
            "conflict": None,
        },
        {
            "source": "tldv",
            "identifier": "ent_tldv_B",
            "event_at": "2026-04-01T00:00:00Z",
            "conflict": None,
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "conflict:pending"
    assert "conflict" in result["reason"].lower() or "pending" in result["reason"].lower()


def test_conflict_pending_wins_tie():
    """Candidate with conflict:pending wins when all else equal."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "ent_tldv_A",
            "event_at": "2026-04-01T00:00:00Z",
            "conflict": None,
        },
        {
            "source": "tldv",
            "identifier": "ent_tldv_B",
            "event_at": "2026-04-01T00:00:00Z",
            "conflict": "pending",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_tldv_B"


def test_conflict_pending_wins_over_non_pending():
    """conflict:pending wins over conflict=None even with same priority/event."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "ent_tldv_A",
            "event_at": "2026-04-01T00:00:00Z",
            "conflict": "resolved",
        },
        {
            "source": "tldv",
            "identifier": "ent_tldv_B",
            "event_at": "2026-04-01T00:00:00Z",
            "conflict": "pending",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_tldv_B"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_candidates_returns_pending():
    """No candidates → conflict:pending."""
    result = resolve_conflict("ent_001", [])
    assert result["resolved"] == "conflict:pending"
    assert result["confidence"] < 1.0


def test_confidence_lower_for_pending():
    """conflict:pending should have lower confidence than resolved."""
    # Resolved case
    candidates_resolved = [
        {
            "source": "github",
            "identifier": "ent_gh_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result_resolved = resolve_conflict("ent_001", candidates_resolved)
    
    # Pending case (true tie)
    candidates_pending = [
        {
            "source": "tldv",
            "identifier": "ent_tldv_A",
            "event_at": "2026-04-01T00:00:00Z",
            "conflict": None,
        },
        {
            "source": "tldv",
            "identifier": "ent_tldv_B",
            "event_at": "2026-04-01T00:00:00Z",
            "conflict": None,
        },
    ]
    result_pending = resolve_conflict("ent_002", candidates_pending)
    
    assert result_resolved["confidence"] > result_pending["confidence"]


def test_unknown_source_uses_default_priority():
    """Unknown source should have lower priority than known sources."""
    candidates = [
        {
            "source": "github",
            "identifier": "ent_gh_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
        {
            "source": "unknown",
            "identifier": "ent_unknown_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_gh_001"


def test_real_world_priority_scenario():
    """GitHub with old event beats TLDV with new event (priority > recency)."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "ent_tldv_001",
            "event_at": "2026-04-15T00:00:00Z",  # newer
        },
        {
            "source": "github",
            "identifier": "ent_gh_001",
            "event_at": "2026-04-01T00:00:00Z",  # older
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    # GitHub wins despite being older
    assert result["resolved"] == "ent_gh_001"


def test_z_suffix_event_at_parsed():
    """event_at with Z suffix must be parsed correctly."""
    candidates = [
        {
            "source": "github",
            "identifier": "ent_gh_001",
            "event_at": "2026-04-01T00:00:00Z",
        },
        {
            "source": "github",
            "identifier": "ent_gh_002",
            "event_at": "2026-04-15T00:00:00Z",
        },
    ]
    result = resolve_conflict("ent_001", candidates)
    assert result["resolved"] == "ent_gh_002"
