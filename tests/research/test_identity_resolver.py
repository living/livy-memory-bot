"""Tests for vault/research/identity_resolver.py — email-first identity resolution."""
from datetime import datetime, timezone

import pytest

from vault.research.identity_resolver import resolve_identity


# ---------------------------------------------------------------------------
# resolve_identity signature
# ---------------------------------------------------------------------------


def test_resolve_returns_dict_with_required_keys():
    """Output must contain: confidence (float), reason (str), link_to (str|None)."""
    result = resolve_identity(
        source="github",
        identifier="usr_abc123",
        candidates=[],
    )
    assert isinstance(result, dict)
    assert "confidence" in result
    assert "reason" in result
    assert "link_to" in result
    assert isinstance(result["confidence"], float)
    assert isinstance(result["reason"], str)
    assert result["link_to"] is None or isinstance(result["link_to"], str)


# ---------------------------------------------------------------------------
# Rule 1: exact email match → confidence >= 0.90 auto-link
# ---------------------------------------------------------------------------


def test_email_exact_match_returns_high_confidence():
    """When a candidate with the same email is found, confidence must be >= 0.90."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": "alice@example.com",
            "username": None,
            "name": "Alice",
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        email="alice@example.com",
        candidates=candidates,
    )
    assert result["confidence"] >= 0.90
    assert result["link_to"] == "per_tldv_001"


def test_email_no_match_returns_low_confidence():
    """When no email match, confidence must be < 0.45 (no-link band)."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": "bob@example.com",
            "username": None,
            "name": "Bob",
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        email="alice@example.com",
        candidates=candidates,
    )
    assert result["confidence"] < 0.45


def test_email_match_provides_reason():
    """Reason must mention email matching."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": "alice@example.com",
            "username": None,
            "name": None,
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        email="alice@example.com",
        candidates=candidates,
    )
    assert "email" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Rule 2: partial username match → +0.15 boost
# ---------------------------------------------------------------------------


def test_partial_username_match_boosts_confidence():
    """Same username appearing in different sources adds +0.15 to confidence."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": None,
            "username": "alice_w",
            "name": None,
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        username="alice_w",
        candidates=candidates,
    )
    # username alone = 0.60 base (at auto-link threshold)
    assert result["confidence"] == 0.60
    assert result["link_to"] == "per_tldv_001"


def test_username_partial_match_boost():
    """Partial username match (e.g., 'alice' vs 'alice_w') also gets +0.15 boost."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": None,
            "username": "alice_w",
            "name": None,
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        username="alice",
        candidates=candidates,
    )
    # partial match = 0.60 base (at auto-link threshold)
    assert result["confidence"] == 0.60
    assert result["link_to"] == "per_tldv_001"


def test_username_no_match_no_boost():
    """Different usernames → no boost."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": None,
            "username": "bob_s",
            "name": None,
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        username="alice_w",
        candidates=candidates,
    )
    assert result["confidence"] < 0.45


# ---------------------------------------------------------------------------
# Rule 3: review_band (0.45–0.59) tie-breakers
#   tie-break order: most sources > most recent event > conflict:pending
# ---------------------------------------------------------------------------


def test_review_band_requires_manual_review():
    """Confidence in [0.45, 0.59) must NOT auto-link."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": None,
            "username": "alice_w",
            "name": "Alice",
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        name="Alice",
        candidates=candidates,
    )
    assert 0.45 <= result["confidence"] < 0.60
    assert result["link_to"] is None  # review band → no auto-link


def test_review_band_tiebreaker_most_sources():
    """Candidate with more matching sources wins in review_band."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_A",
            "email": None,
            "username": None,
            "name": "Alice",
            "sources": ["tldv", "github"],  # 2 sources
        },
        {
            "source": "jira",
            "identifier": "per_tldv_B",
            "email": None,
            "username": None,
            "name": "Alice",
            "sources": ["jira"],  # 1 source
        },
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        name="Alice",
        candidates=candidates,
    )
    assert 0.45 <= result["confidence"] < 0.60
    assert result["link_to"] is None
    assert "per_tldv_A" in result["reason"]


def test_review_band_tiebreaker_most_recent_event():
    """Candidate with more recent event_at wins in review_band when sources equal."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_A",
            "email": None,
            "username": None,
            "name": "Alice",
            "sources": ["tldv"],
            "event_at": "2026-01-01T00:00:00Z",
        },
        {
            "source": "jira",
            "identifier": "per_tldv_B",
            "email": None,
            "username": None,
            "name": "Alice",
            "sources": ["tldv"],
            "event_at": "2026-04-01T00:00:00Z",
        },
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        name="Alice",
        candidates=candidates,
    )
    assert 0.45 <= result["confidence"] < 0.60
    assert result["link_to"] is None
    assert "per_tldv_B" in result["reason"]


def test_review_band_tiebreaker_conflict_pending():
    """When still tied, candidate with conflict:pending wins."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_A",
            "email": None,
            "username": None,
            "name": "Alice",
            "sources": ["tldv"],
            "event_at": "2026-01-01T00:00:00Z",
            "conflict": None,
        },
        {
            "source": "jira",
            "identifier": "per_tldv_B",
            "email": None,
            "username": None,
            "name": "Alice",
            "sources": ["tldv"],
            "event_at": "2026-01-01T00:00:00Z",
            "conflict": "pending",
        },
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        name="Alice",
        candidates=candidates,
    )
    assert 0.45 <= result["confidence"] < 0.60
    assert result["link_to"] is None
    assert "per_tldv_B" in result["reason"]


# ---------------------------------------------------------------------------
# Threshold bands
# ---------------------------------------------------------------------------


def test_auto_link_threshold():
    """confidence >= 0.60 → auto-link (link_to != None)."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": "alice@example.com",
            "username": "alice_w",
            "name": None,
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        email="alice@example.com",
        username="alice_w",
        candidates=candidates,
    )
    # email match >= 0.90 + username boost +0.15 = 1.05, capped at 1.0
    assert result["confidence"] >= 0.60
    assert result["link_to"] is not None


def test_no_link_band():
    """confidence < 0.45 → no link."""
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        candidates=[],
    )
    assert result["confidence"] < 0.45
    assert result["link_to"] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_email_and_username_boost_combined():
    """Email match (0.90) + username boost (+0.15) = capped at 1.0."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": "alice@example.com",
            "username": "alice_w",
            "name": None,
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        email="alice@example.com",
        username="alice_w",
        candidates=candidates,
    )
    # email (0.90) + username (+0.15) = 1.05, capped at 1.0
    assert result["confidence"] == 1.0
    assert result["link_to"] == "per_tldv_001"


def test_empty_candidates_returns_no_link():
    """No candidates → no-link band."""
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        candidates=[],
    )
    assert result["confidence"] < 0.45
    assert result["link_to"] is None
    assert "no candidates" in result["reason"].lower()


def test_source_ignored_when_identifying_itself():
    """Source must not match itself in candidates."""
    candidates = [
        {
            "source": "github",
            "identifier": "per_tldv_001",
            "email": "alice@example.com",
            "username": None,
            "name": None,
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        email="alice@example.com",
        candidates=candidates,
    )
    # Should not link to self → no-link
    assert result["confidence"] < 0.45


def test_multiple_candidates_best_match_wins():
    """When multiple candidates match, highest confidence wins."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_A",
            "email": None,
            "username": "alice_w",
            "name": None,
        },
        {
            "source": "jira",
            "identifier": "per_tldv_B",
            "email": "alice@example.com",
            "username": None,
            "name": None,
        },
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        email="alice@example.com",
        username="alice_w",
        candidates=candidates,
    )
    # per_tldv_B has email match (0.90) vs per_tldv_A has username (0.60)
    assert result["link_to"] == "per_tldv_B"
    assert result["confidence"] >= 0.90


def test_confidence_is_float():
    """confidence must always be a float, never int."""
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        candidates=[],
    )
    assert type(result["confidence"]) is float


def test_reason_describes_match_type():
    """Reason should describe the primary match type."""
    candidates = [
        {
            "source": "tldv",
            "identifier": "per_tldv_001",
            "email": "alice@example.com",
            "username": None,
            "name": None,
        }
    ]
    result = resolve_identity(
        source="github",
        identifier="usr_xyz",
        email="alice@example.com",
        candidates=candidates,
    )
    reason = result["reason"].lower()
    assert "email" in reason or "match" in reason
