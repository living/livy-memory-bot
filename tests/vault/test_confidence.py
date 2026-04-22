"""TDD RED/GREEN: confidence scoring tests with decision bonus."""
import pytest
from datetime import datetime, timezone, timedelta
from vault.memory_core.models import Claim, SourceRef, AuditTrail


def make_claim(
    source: str = "github",
    days_ago: int = 0,
    num_evidence: int = 1,
    claim_id: str = "test-claim",
    claim_type: str = "status",
    needs_review: bool = False,
    review_reason: str | None = None,
) -> Claim:
    """Helper to create a claim for testing."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    evidence_ids = [f"ev-{i}" for i in range(num_evidence)]
    return Claim(
        claim_id=claim_id,
        entity_type="project",
        entity_id="proj-1",
        topic_id="topic-1",
        claim_type=claim_type,
        text="Test claim",
        source=source,  # type: ignore[arg-type]
        source_ref=SourceRef(source_id="src-1"),
        evidence_ids=evidence_ids,
        author="test",
        event_timestamp=ts,
        ingested_at=ts,
        confidence=0.0,
        privacy_level="internal",
        needs_review=needs_review,
        review_reason=review_reason,
        superseded_by=None,
        supersession_reason=None,
        supersession_version=None,
        audit_trail=AuditTrail(model_used="test", parser_version="v1", trace_id="trace-1"),
    )


class TestConfidenceScoring:
    """Confidence score calculation: base + source_reliability + recency + convergence - contradiction."""

    def test_base_confidence(self):
        """Base confidence is 0.5 when all modifiers are zero."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="unknown", days_ago=60, num_evidence=1)
        score = compute_confidence(claim, contradicting_claim=None)
        assert score == pytest.approx(0.5)

    def test_source_github_tldv(self):
        """github and tldv sources get +0.2."""
        from vault.fusion_engine.confidence import compute_confidence
        for source in ("github", "tldv"):
            claim = make_claim(source=source, days_ago=60)
            score = compute_confidence(claim, contradicting_claim=None)
            assert score == pytest.approx(0.7), f"source={source} should be 0.7"

    def test_source_gmail(self):
        """gmail source gets +0.15."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="gmail", days_ago=60)
        score = compute_confidence(claim, contradicting_claim=None)
        assert score == pytest.approx(0.65)

    def test_source_trello_gcal(self):
        """trello and gcal sources get +0.1."""
        from vault.fusion_engine.confidence import compute_confidence
        for source in ("trello", "gcal"):
            claim = make_claim(source=source, days_ago=60)
            score = compute_confidence(claim, contradicting_claim=None)
            assert score == pytest.approx(0.6), f"source={source} should be 0.6"

    def test_recency_under_7_days(self):
        """Claims <7 days old get +0.2."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=3)
        score = compute_confidence(claim, contradicting_claim=None)
        # base(0.5) + source(0.2) + recency(0.2) = 0.9
        assert score == pytest.approx(0.9)

    def test_recency_under_30_days(self):
        """Claims >=7 and <30 days old get +0.1."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=15)
        score = compute_confidence(claim, contradicting_claim=None)
        # base(0.5) + source(0.2) + recency(0.1) = 0.8
        assert score == pytest.approx(0.8)

    def test_recency_under_90_days(self):
        """Claims >=30 and <90 days old get 0 recency modifier."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=45)
        score = compute_confidence(claim, contradicting_claim=None)
        # base(0.5) + source(0.2) + recency(0.0) = 0.7
        assert score == pytest.approx(0.7)

    def test_recency_over_90_days(self):
        """Claims >=90 days old get -0.2 recency penalty."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=120)
        score = compute_confidence(claim, contradicting_claim=None)
        # base(0.5) + source(0.2) + recency(-0.2) = 0.5
        assert score == pytest.approx(0.5)

    def test_convergence_single_source(self):
        """Convergence adds +0.1 per source, max +0.3."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=60)
        other_sources = ["tldv"]
        score = compute_confidence(claim, contradicting_claim=None, other_sources=other_sources)
        # base(0.5) + source(0.2) + convergence(+0.1) = 0.8
        assert score == pytest.approx(0.8)

    def test_convergence_distinct_sources_only(self):
        """Convergence must count distinct sources only (duplicates count once)."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=60)
        other_sources = ["github", "github"]
        score = compute_confidence(claim, contradicting_claim=None, other_sources=other_sources)
        # base(0.5) + source(0.2) + convergence(+0.1 for distinct github only) = 0.8
        assert score == pytest.approx(0.8)

    def test_convergence_max_3_sources(self):
        """Convergence caps at +0.3 even with more sources."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=60)
        other_sources = ["tldv", "gmail", "trello", "gcal"]
        score = compute_confidence(claim, contradicting_claim=None, other_sources=other_sources)
        # base(0.5) + source(0.2) + convergence(+0.3 max) = 1.0
        assert score == pytest.approx(1.0)

    def test_contradiction_penalty(self):
        """A contradicting claim reduces confidence by 0.3."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=3, claim_id="claim-1")
        contradicting = make_claim(source="tldv", days_ago=1, claim_id="claim-2")
        score = compute_confidence(claim, contradicting_claim=contradicting)
        # base(0.5) + source(0.2) + recency(0.2) - contradiction(0.3) = 0.6
        assert score == pytest.approx(0.6)

    def test_confidence_clamped_at_1_0(self):
        """Score must not exceed 1.0."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=3)
        other_sources = ["tldv", "gmail"]
        score = compute_confidence(claim, contradicting_claim=None, other_sources=other_sources)
        # base(0.5) + source(0.2) + recency(0.2) + convergence(0.2) = 1.1 → clamp to 1.0
        assert score == pytest.approx(1.0)

    def test_confidence_clamped_at_0_0(self):
        """Score must not go below 0.0."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="unknown", days_ago=120)
        contradicting = make_claim(source="github", days_ago=1)
        score = compute_confidence(claim, contradicting_claim=contradicting)
        # base(0.5) + source(0.0) + recency(-0.2) - contradiction(0.3) = 0.0
        assert score == pytest.approx(0.0)


class TestDecisionClaimBonus:
    """Decision claims with evidence_ids get +0.15 bonus."""

    def test_decision_claim_with_evidence_ids_gets_015_bonus(self):
        """Decision claim with evidence_ids adds +0.15 to confidence."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=30, claim_type="decision")
        # base(0.5) + source(0.2) + recency(0.0) + decision_bonus(0.15) = 0.85
        score = compute_confidence(claim, contradicting_claim=None)
        assert score == pytest.approx(0.85)

    def test_decision_claim_without_evidence_ids_no_bonus(self):
        """Decision claim without evidence_ids does NOT get bonus."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=30, claim_type="decision", num_evidence=0)
        # base(0.5) + source(0.2) + recency(0.0) = 0.7 (no bonus without evidence)
        score = compute_confidence(claim, contradicting_claim=None)
        assert score == pytest.approx(0.7)

    def test_non_decision_claim_no_bonus(self):
        """Non-decision claims do not get the decision bonus."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=30, claim_type="status")
        # base(0.5) + source(0.2) + recency(0.0) = 0.7 (no decision bonus)
        score = compute_confidence(claim, contradicting_claim=None)
        assert score == pytest.approx(0.7)

    def test_decision_bonus_composes_with_convergence(self):
        """Decision bonus + convergence can both apply."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=30, claim_type="decision")
        other_sources = ["tldv"]
        # base(0.5) + source(0.2) + recency(0.0) + decision(0.15) + convergence(0.1) = 0.95
        score = compute_confidence(claim, contradicting_claim=None, other_sources=other_sources)
        assert score == pytest.approx(0.95)

    def test_decision_bonus_composes_with_recency(self):
        """Decision bonus + recency both apply."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=3, claim_type="decision")
        # base(0.5) + source(0.2) + recency(0.2) + decision(0.15) = 1.05 → clamp to 1.0
        score = compute_confidence(claim, contradicting_claim=None)
        assert score == pytest.approx(1.0)


class TestBackwardCompatibility:
    """Existing behavior must remain unchanged for backward compatibility."""

    def test_existing_confidence_still_works(self):
        """Original scoring formula still produces same scores."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=3)
        other_sources = ["tldv", "gmail"]
        score = compute_confidence(claim, contradicting_claim=None, other_sources=other_sources)
        # Original formula: base(0.5) + source(0.2) + recency(0.2) + convergence(0.2) = 1.1 → 1.0
        assert score == pytest.approx(1.0)

    def test_contradiction_still_applies(self):
        """Contradiction penalty still works."""
        from vault.fusion_engine.confidence import compute_confidence
        claim = make_claim(source="github", days_ago=3, claim_id="c1")
        contradicting = make_claim(source="tldv", days_ago=1, claim_id="c2")
        score = compute_confidence(claim, contradicting_claim=contradicting)
        # base(0.5) + source(0.2) + recency(0.2) - contradiction(0.3) = 0.6
        assert score == pytest.approx(0.6)

    def test_no_breaking_changes_to_function_signature(self):
        """compute_confidence signature unchanged (backward compatible)."""
        from vault.fusion_engine.confidence import compute_confidence
        import inspect
        sig = inspect.signature(compute_confidence)
        params = list(sig.parameters.keys())
        assert "claim" in params
        assert "contradicting_claim" in params
        assert "other_sources" in params
