"""TDD RED: supersession logic tests."""
import pytest
from datetime import datetime, timezone, timedelta
from vault.memory_core.models import Claim, SourceRef, AuditTrail, Source


def make_claim(
    entity_id: str = "proj-1",
    claim_type: str = "status",
    days_ago: int = 0,
    superseded_by: str | None = None,
    claim_id: str = "test-claim",
    event_timestamp: str | None = None,
) -> Claim:
    ts = event_timestamp or (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return Claim(
        claim_id=claim_id,
        entity_type="project",
        entity_id=entity_id,
        topic_id="topic-1",
        claim_type=claim_type,
        text="Test claim",
        source="github",
        source_ref=SourceRef(source_id="src-1"),
        evidence_ids=["ev-1"],
        author="test",
        event_timestamp=ts,
        ingested_at=ts,
        confidence=0.0,
        privacy_level="internal",
        superseded_by=superseded_by,
        supersession_reason=None,
        supersession_version=None,
        audit_trail=AuditTrail(model_used="test", parser_version="v1", trace_id="trace-1"),
    )


class TestShouldSupersede:
    """should_supersede(candidate, existing) logic."""

    def test_same_entity_and_type_newer_candidate(self):
        """Candidate newer than existing on same entity+type → supersedes."""
        from vault.fusion_engine.supersession import should_supersede
        existing = make_claim(days_ago=10, claim_id="existing")
        candidate = make_claim(days_ago=5, claim_id="candidate")
        assert should_supersede(candidate, existing) is True

    def test_same_entity_and_type_older_candidate(self):
        """Candidate older than existing on same entity+type → does not supersede."""
        from vault.fusion_engine.supersession import should_supersede
        existing = make_claim(days_ago=5, claim_id="existing")
        candidate = make_claim(days_ago=10, claim_id="candidate")
        assert should_supersede(candidate, existing) is False

    def test_different_entity_id(self):
        """Different entity_id → does not supersede."""
        from vault.fusion_engine.supersession import should_supersede
        existing = make_claim(entity_id="proj-1", days_ago=10)
        candidate = make_claim(entity_id="proj-2", days_ago=5)
        assert should_supersede(candidate, existing) is False

    def test_different_claim_type(self):
        """Different claim_type → does not supersede."""
        from vault.fusion_engine.supersession import should_supersede
        existing = make_claim(claim_type="status", days_ago=10)
        candidate = make_claim(claim_type="decision", days_ago=5)
        assert should_supersede(candidate, existing) is False

    def test_existing_already_superseded(self):
        """Existing already superseded → does not supersede."""
        from vault.fusion_engine.supersession import should_supersede
        existing = make_claim(days_ago=10, superseded_by="other-claim")
        candidate = make_claim(days_ago=5)
        assert should_supersede(candidate, existing) is False

    def test_same_timestamp_does_not_supersede(self):
        """Same event_timestamp → does not supersede (stable ordering)."""
        from vault.fusion_engine.supersession import should_supersede
        ts = datetime.now(timezone.utc).isoformat()
        existing = make_claim(claim_id="existing", event_timestamp=ts)
        candidate = make_claim(claim_id="candidate", event_timestamp=ts)
        assert should_supersede(candidate, existing) is False


class TestApplySupersession:
    """apply_supersession(candidate, existing) side effects."""

    def test_updates_superseded_by(self):
        """apply_supersession sets superseded_by on existing."""
        from vault.fusion_engine.supersession import apply_supersession
        candidate = make_claim(claim_id="candidate")
        existing = make_claim(claim_id="existing")
        result = apply_supersession(candidate, existing)
        assert result.superseded_by == "candidate"
        assert result.supersession_reason is not None
        assert result.supersession_version == 1

    def test_supersession_reason_set(self):
        """apply_supersession populates supersession_reason."""
        from vault.fusion_engine.supersession import apply_supersession
        candidate = make_claim(claim_id="candidate")
        existing = make_claim(claim_id="existing")
        result = apply_supersession(candidate, existing)
        assert result.supersession_reason is not None
        assert len(result.supersession_reason) > 0

    def test_returns_new_instance(self):
        """apply_supersession returns a new Claim, does not mutate existing."""
        from vault.fusion_engine.supersession import apply_supersession
        candidate = make_claim(claim_id="candidate")
        existing = make_claim(claim_id="existing")
        result = apply_supersession(candidate, existing)
        assert existing.superseded_by is None
        assert result.claim_id == existing.claim_id
        assert result.claim_id != candidate.claim_id
