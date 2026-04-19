"""TDD RED: fusion engine orchestration tests."""
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
) -> Claim:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return Claim(
        claim_id=claim_id,
        entity_type="project",
        entity_id=entity_id,
        topic_id=topic_id,
        claim_type=claim_type,
        text=text,
        source=source,
        source_ref=SourceRef(source_id=f"src-{claim_id}"),
        evidence_ids=[f"ev-{claim_id}"],
        author="test",
        event_timestamp=ts,
        ingested_at=ts,
        confidence=confidence,
        privacy_level="internal",
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
