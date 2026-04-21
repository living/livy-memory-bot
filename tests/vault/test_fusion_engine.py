"""TDD RED/GREEN: fusion engine orchestration tests with confidence + convergence wiring."""
import pytest
from datetime import datetime, timezone, timedelta
from vault.memory_core.models import Claim, SourceRef, AuditTrail


def make_claim(
    claim_id: str,
    entity_id: str = "proj-1",
    claim_type: str = "status",
    topic_id: str = "topic-1",
    text: str = "status is green",
    source: str = "github",
    confidence: float = 0.0,
    superseded_by: str | None = None,
    days_ago: int = 0,
    num_evidence: int = 1,
    needs_review: bool = False,
    review_reason: str | None = None,
) -> Claim:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    evidence_ids = [f"ev-{claim_id}-{i}" for i in range(num_evidence)]
    return Claim(
        claim_id=claim_id,
        entity_type="project",
        entity_id=entity_id,
        topic_id=topic_id,
        claim_type=claim_type,
        text=text,
        source=source,
        source_ref=SourceRef(source_id=f"src-{claim_id}"),
        evidence_ids=evidence_ids,
        author="test",
        event_timestamp=ts,
        ingested_at=ts,
        confidence=confidence,
        privacy_level="internal",
        needs_review=needs_review,
        review_reason=review_reason,
        superseded_by=superseded_by,
        supersession_reason=None,
        supersession_version=None,
        audit_trail=AuditTrail(model_used="test", parser_version="v1", trace_id=f"tr-{claim_id}"),
    )


class TestFusionEngine:
    def test_fuse_returns_result_shape(self):
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", days_ago=1)
        existing = [make_claim("old", days_ago=10)]

        result = fuse(new_claim, existing)

        assert hasattr(result, "contradiction")
        assert hasattr(result, "superseded_claims")
        assert hasattr(result, "was_superseded")
        assert hasattr(result, "fused_claim")

    def test_fuse_applies_supersession_for_older_matching_claim(self):
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", entity_id="proj-1", claim_type="status", days_ago=1)
        old_matching = make_claim("old", entity_id="proj-1", claim_type="status", days_ago=10)

        result = fuse(new_claim, [old_matching])

        assert result.was_superseded is False
        assert len(result.superseded_claims) == 1
        assert result.superseded_claims[0].claim_id == "old"
        assert result.superseded_claims[0].superseded_by == "new"

    def test_fuse_marks_new_claim_as_superseded_when_existing_newer(self):
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", entity_id="proj-1", claim_type="status", days_ago=10)
        existing_newer = make_claim("existing", entity_id="proj-1", claim_type="status", days_ago=1)

        result = fuse(new_claim, [existing_newer])

        assert result.was_superseded is True
        assert result.fused_claim.superseded_by == "existing"

    def test_fuse_detects_contradiction(self):
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", text="status is red", days_ago=1)
        existing = [make_claim("old", text="status is green", days_ago=10, confidence=0.9)]

        result = fuse(new_claim, existing)

        assert result.contradiction is not None
        assert result.contradiction.new_claim_id == "new"
        assert result.contradiction.existing_claim_id == "old"

    def test_fuse_computes_confidence(self):
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", source="github", days_ago=1)
        existing = [make_claim("old", source="tldv", days_ago=2)]

        result = fuse(new_claim, existing)

        assert 0.0 <= result.fused_claim.confidence <= 1.0
        assert result.fused_claim.confidence > 0.5

    def test_fuse_preserves_non_superseded_existing_claims(self):
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", entity_id="proj-1", claim_type="status", days_ago=1)
        other_entity = make_claim("other", entity_id="proj-2", claim_type="status", days_ago=10)

        result = fuse(new_claim, [other_entity])

        assert len(result.superseded_claims) == 0
        assert result.was_superseded is False

    def test_fuse_ignores_already_superseded_in_supersession_pass(self):
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", entity_id="proj-1", claim_type="status", days_ago=1)
        old_superseded = make_claim(
            "old",
            entity_id="proj-1",
            claim_type="status",
            days_ago=10,
            superseded_by="other",
        )

        result = fuse(new_claim, [old_superseded])

        assert len(result.superseded_claims) == 0


class TestFusionConfidenceWiring:
    """Fusion engine uses confidence scoring with convergence (other_sources mechanism)."""

    def test_fuse_applies_convergence_from_existing_sources(self):
        """Fusion passes other_sources to compute_confidence for convergence."""
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", source="github", days_ago=30)
        existing = [
            make_claim("src1", source="tldv", days_ago=5),
            make_claim("src2", source="gmail", days_ago=10),
        ]

        result = fuse(new_claim, existing)

        # base(0.5) + source(0.2) + recency(0.0) + convergence(0.2) = 0.9
        assert result.fused_claim.confidence == pytest.approx(0.9)

    def test_fuse_reuses_other_sources_convergence_no_parallel(self):
        """Fusion does NOT use a parallel convergence mechanism - uses other_sources only."""
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", source="github", days_ago=60)
        existing = [make_claim("old", source="tldv", days_ago=30)]

        result = fuse(new_claim, existing)

        # Convergence via other_sources: base(0.5) + source(0.2) + convergence(0.1) = 0.8
        assert result.fused_claim.confidence == pytest.approx(0.8)


class TestFusionNeedsReviewLogic:
    """Canonical needs_review/review_reason when lacking evidence or low confidence."""

    def test_low_confidence_claim_marks_needs_review(self):
        """Claims with confidence below 0.5 get needs_review=True."""
        from vault.fusion_engine.engine import fuse

        # Create a claim that will score low due to combination of penalties
        # base(0.5) + source(0.0) + recency(-0.2) - contradiction(0.3) = 0.0
        new_claim = make_claim(
            "new",
            source="unknown",
            days_ago=120,
            num_evidence=1,  # Model requires evidence_ids
            claim_type="status",  # Different type to avoid supersession
        )
        contradicting = make_claim("old", source="github", days_ago=1, claim_type="risk")

        result = fuse(new_claim, [contradicting])

        assert result.fused_claim.confidence < 0.5
        assert result.fused_claim.needs_review is True
        assert result.fused_claim.review_reason == "low_confidence"

    def test_missing_evidence_marks_needs_review(self):
        """Claims without evidence_ids get needs_review=True."""
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim("new", source="github", days_ago=30, num_evidence=0)
        existing = []

        result = fuse(new_claim, existing)

        assert result.fused_claim.needs_review is True
        assert result.fused_claim.review_reason == "missing_evidence"

    def test_high_confidence_with_evidence_stays_no_review(self):
        """Claims with high confidence and evidence remain needs_review=False."""
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim(
            "new",
            source="github",
            days_ago=3,
            claim_type="decision",
            num_evidence=2,
        )
        existing = [
            make_claim("src1", source="tldv", days_ago=5),
        ]

        result = fuse(new_claim, existing)

        # High confidence: base(0.5) + source(0.2) + recency(0.2) + decision(0.15) + convergence(0.1) = 1.15 → 1.0
        assert result.fused_claim.confidence >= 0.8
        assert result.fused_claim.needs_review is False
        assert result.fused_claim.review_reason is None

    def test_existing_needs_review_preserved_if_not_overridden(self):
        """Pre-existing needs_review=True is preserved when not overridden by fusion logic."""
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim(
            "new",
            source="github",
            days_ago=30,
            num_evidence=1,
            needs_review=True,
            review_reason="manual_flag",
        )
        existing = []

        result = fuse(new_claim, existing)

        # High confidence claim but already flagged - preserve original reason
        assert result.fused_claim.needs_review is True
        assert result.fused_claim.review_reason == "manual_flag"

    def test_canonical_review_reason_when_contradiction_lowers_confidence(self):
        """Contradiction that lowers confidence triggers needs_review."""
        from vault.fusion_engine.engine import fuse

        # base(0.5) + source(0.2) + recency(0.0) - contradiction(0.3) = 0.4 < 0.5
        # Keep existing source equal to avoid convergence bonus.
        new_claim = make_claim(
            "new",
            source="github",
            days_ago=60,
            num_evidence=1,
            claim_type="status",
            text="status is green",
        )
        contradicting = make_claim(
            "old",
            source="github",
            days_ago=90,
            claim_type="status",
            text="status is red",
        )

        result = fuse(new_claim, [contradicting])

        assert result.fused_claim.confidence < 0.5
        assert result.fused_claim.needs_review is True
        assert result.fused_claim.review_reason == "low_confidence"


class TestFusionDecisionBonus:
    """Fusion engine applies decision claim bonus."""

    def test_fuse_applies_decision_bonus(self):
        """Fusion applies +0.15 decision bonus for decision claims with evidence."""
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim(
            "new",
            source="github",
            days_ago=30,
            claim_type="decision",
            num_evidence=2,
        )
        existing = []

        result = fuse(new_claim, existing)

        # base(0.5) + source(0.2) + recency(0.0) + decision(0.15) = 0.85
        assert result.fused_claim.confidence == pytest.approx(0.85)


class TestFusionDecisionBonusComposed:
    """Decision bonus composes with other scoring factors."""

    def test_fuse_decision_bonus_composes_with_convergence(self):
        """Decision bonus + convergence both apply."""
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim(
            "new",
            source="github",
            days_ago=30,
            claim_type="decision",
        )
        existing = [
            make_claim("src1", source="tldv", days_ago=5),
        ]

        result = fuse(new_claim, existing)

        # base(0.5) + source(0.2) + recency(0.0) + decision(0.15) + convergence(0.1) = 0.95
        assert result.fused_claim.confidence == pytest.approx(0.95)

    def test_fuse_decision_bonus_clamped_at_1(self):
        """Decision bonus + recency + convergence clamps to 1.0."""
        from vault.fusion_engine.engine import fuse

        new_claim = make_claim(
            "new",
            source="github",
            days_ago=3,
            claim_type="decision",
        )
        existing = [
            make_claim("src1", source="tldv", days_ago=5),
        ]

        result = fuse(new_claim, existing)

        # base(0.5) + source(0.2) + recency(0.2) + decision(0.15) + convergence(0.1) = 1.15 → clamp to 1.0
        assert result.fused_claim.confidence == pytest.approx(1.0)
