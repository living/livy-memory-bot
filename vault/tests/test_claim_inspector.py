"""Tests for vault/insights/claim_inspector.py."""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ---------------------------------------------------------------------------
# Sample claim factories
# ---------------------------------------------------------------------------

def _claim(overrides=None):
    base = {
        "claim_id": "c-001",
        "entity_type": "project",
        "entity_id": "living/livy-memory-bot",
        "topic_id": None,
        "claim_type": "status",
        "text": "PR merged",
        "source": "github",
        "source_ref": {"source_id": "pr-1", "url": "https://github.com/living/livy-memory-bot/pull/1"},
        "evidence_ids": ["ev-1"],
        "author": "lincoln",
        "event_timestamp": "2026-04-19T12:00:00+00:00",
        "ingested_at": "2026-04-19T13:00:00+00:00",
        "confidence": 0.85,
        "privacy_level": "internal",
        "superseded_by": None,
        "supersession_reason": None,
        "supersession_version": None,
        "audit_trail": {"model_used": "test", "parser_version": "v1", "trace_id": "t1"},
    }
    if overrides:
        base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExtractCountsBySource:
    """test_extract_counts_by_source — verify source breakdown is correct."""

    def test_single_source(self):
        from vault.insights.claim_inspector import extract_insights
        claims = [
            _claim({"claim_id": "c-1", "source": "github"}),
            _claim({"claim_id": "c-2", "source": "github"}),
        ]
        bundle = extract_insights(claims)
        assert bundle.by_source["github"] == 2
        assert bundle.total == 2

    def test_multiple_sources(self):
        from vault.insights.claim_inspector import extract_insights
        claims = [
            _claim({"claim_id": "c-1", "source": "github"}),
            _claim({"claim_id": "c-2", "source": "tldv"}),
            _claim({"claim_id": "c-3", "source": "tldv"}),
            _claim({"claim_id": "c-4", "source": "trello"}),
        ]
        bundle = extract_insights(claims)
        assert bundle.by_source["github"] == 1
        assert bundle.by_source["tldv"] == 2
        assert bundle.by_source["trello"] == 1
        assert bundle.total == 4


class TestFiltersActiveAndSuperseded:
    """test_filters_active_and_superseded — verify active vs superseded split."""

    def test_active_claims_preserved(self):
        from vault.insights.claim_inspector import extract_insights
        claims = [_claim({"claim_id": "c-1"}), _claim({"claim_id": "c-2"})]
        bundle = extract_insights(claims)
        assert bundle.active == 2
        assert bundle.superseded_total == 0
        assert len(bundle.superseded_this_week) == 0

    def test_superseded_claims_counted(self):
        from vault.insights.claim_inspector import extract_insights
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        claims = [
            _claim({"claim_id": "c-1"}),
            _claim({"claim_id": "c-2", "superseded_by": "c-new-1", "supersession_reason": "updated", "supersession_version": 2, "event_timestamp": old}),
        ]
        bundle = extract_insights(claims)
        assert bundle.active == 1
        assert bundle.superseded_total == 1
        assert bundle.superseded_this_week == []

    def test_superseded_this_week(self):
        from vault.insights.claim_inspector import extract_insights
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=2)).isoformat()
        old = (now - timedelta(days=10)).isoformat()
        claims = [
            _claim({"claim_id": "c-1", "superseded_by": "c-new-1", "supersession_reason": "updated", "supersession_version": 2, "event_timestamp": recent}),
            _claim({"claim_id": "c-2", "superseded_by": "c-new-2", "supersession_reason": "updated", "supersession_version": 2, "event_timestamp": old}),
        ]
        bundle = extract_insights(claims)
        assert bundle.superseded_total == 2
        assert len(bundle.superseded_this_week) == 1
        assert bundle.superseded_this_week[0]["claim_id"] == "c-1"


class TestDetectsContradictions:
    """test_detects_contradictions_conf_delta — verify contradiction detection."""

    def test_no_contradiction_same_confidence(self):
        from vault.insights.claim_inspector import extract_insights
        now = datetime.now(timezone.utc).isoformat()
        claims = [
            _claim({"claim_id": "c-1", "entity_id": "living/repo", "confidence": 0.7, "event_timestamp": now}),
            _claim({"claim_id": "c-2", "entity_id": "living/repo", "confidence": 0.7, "event_timestamp": now}),
        ]
        bundle = extract_insights(claims)
        assert len(bundle.contradictions) == 0

    def test_contradiction_detected(self):
        from vault.insights.claim_inspector import extract_insights
        now = datetime.now(timezone.utc).isoformat()
        claims = [
            _claim({"claim_id": "c-1", "entity_id": "living/repo", "confidence": 0.3, "event_timestamp": now}),
            _claim({"claim_id": "c-2", "entity_id": "living/repo", "confidence": 0.8, "event_timestamp": now}),
        ]
        bundle = extract_insights(claims)
        assert len(bundle.contradictions) == 1
        assert bundle.contradictions[0].entity_id == "living/repo"
        assert bundle.contradictions[0].delta == pytest.approx(0.5, abs=0.01)

    def test_no_contradiction_below_delta_threshold(self):
        from vault.insights.claim_inspector import extract_insights
        now = datetime.now(timezone.utc).isoformat()
        claims = [
            _claim({"claim_id": "c-1", "entity_id": "living/repo", "confidence": 0.6, "event_timestamp": now}),
            _claim({"claim_id": "c-2", "entity_id": "living/repo", "confidence": 0.8, "event_timestamp": now}),
        ]
        bundle = extract_insights(claims)
        assert len(bundle.contradictions) == 0

    def test_contradiction_only_on_status_type(self):
        from vault.insights.claim_inspector import extract_insights
        now = datetime.now(timezone.utc).isoformat()
        claims = [
            _claim({"claim_id": "c-1", "entity_id": "living/repo", "claim_type": "ownership", "confidence": 0.3, "event_timestamp": now}),
            _claim({"claim_id": "c-2", "entity_id": "living/repo", "claim_type": "ownership", "confidence": 0.9, "event_timestamp": now}),
        ]
        bundle = extract_insights(claims)
        assert len(bundle.contradictions) == 0  # ownership is not status


class TestHandlesMalformedTimestamps:
    """test_handles_malformed_timestamps — verify graceful degradation."""

    def test_malformed_timestamp_skipped(self):
        from vault.insights.claim_inspector import extract_insights
        claims = [
            _claim({"claim_id": "c-1", "event_timestamp": "not-a-date"}),
            _claim({"claim_id": "c-2", "event_timestamp": "2026-04-19T12:00:00+00:00"}),
        ]
        bundle = extract_insights(claims)
        # Both should be processed; the malformed one is in total/active
        assert bundle.total == 2
        assert bundle.active == 2

    def test_missing_timestamp_field(self):
        from vault.insights.claim_inspector import extract_insights
        bad = _claim({"claim_id": "c-1"})
        del bad["event_timestamp"]
        claims = [bad, _claim({"claim_id": "c-2"})]
        bundle = extract_insights(claims)
        assert bundle.total == 2

    def test_empty_claims_list(self):
        from vault.insights.claim_inspector import extract_insights
        bundle = extract_insights([])
        assert bundle.total == 0
        assert bundle.by_source == {}
        assert bundle.active == 0
        assert bundle.superseded_total == 0
        assert len(bundle.superseded_this_week) == 0
        assert len(bundle.contradictions) == 0


class TestWeekCoverage:
    """Verify weekly coverage logic for fallback decision."""

    def test_coverage_check_covered(self):
        from vault.insights.claim_inspector import week_covered_by_claims
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        claims = [
            _claim({"claim_id": "c-1", "event_timestamp": week_ago.isoformat()}),
            _claim({"claim_id": "c-2", "event_timestamp": now.isoformat()}),
        ]
        assert week_covered_by_claims(claims) is True

    def test_coverage_check_empty(self):
        from vault.insights.claim_inspector import week_covered_by_claims
        assert week_covered_by_claims([]) is False

    def test_coverage_check_old_claims_only(self):
        from vault.insights.claim_inspector import week_covered_by_claims
        old = datetime.now(timezone.utc) - timedelta(days=30)
        claims = [_claim({"claim_id": "c-1", "event_timestamp": old.isoformat()})]
        assert week_covered_by_claims(claims) is False
