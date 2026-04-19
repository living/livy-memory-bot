"""TDD RED: contradiction detection tests."""
from datetime import datetime, timezone, timedelta
from vault.memory_core.models import Claim, SourceRef, AuditTrail


def make_claim(
    claim_id: str,
    topic_id: str = "topic-1",
    entity_id: str = "proj-1",
    text: str = "status is green",
    confidence: float = 0.8,
    superseded_by: str | None = None,
    days_ago: int = 0,
) -> Claim:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return Claim(
        claim_id=claim_id,
        entity_type="project",
        entity_id=entity_id,
        topic_id=topic_id,
        claim_type="status",
        text=text,
        source="github",
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


class TestDetectContradiction:
    def test_detects_contradiction_same_topic_entity_different_text(self):
        from vault.fusion_engine.contradiction import detect_contradiction

        new_claim = make_claim("new", text="status is red")
        existing = [make_claim("old", text="status is green")]

        contradiction = detect_contradiction(new_claim, existing)
        assert contradiction is not None
        assert contradiction.existing_claim_id == "old"
        assert contradiction.new_claim_id == "new"

    def test_no_contradiction_if_same_text(self):
        from vault.fusion_engine.contradiction import detect_contradiction

        new_claim = make_claim("new", text="status is green")
        existing = [make_claim("old", text="status is green")]

        contradiction = detect_contradiction(new_claim, existing)
        assert contradiction is None

    def test_no_contradiction_if_different_topic(self):
        from vault.fusion_engine.contradiction import detect_contradiction

        new_claim = make_claim("new", topic_id="topic-1", text="status is red")
        existing = [make_claim("old", topic_id="topic-2", text="status is green")]

        contradiction = detect_contradiction(new_claim, existing)
        assert contradiction is None

    def test_no_contradiction_if_different_entity(self):
        from vault.fusion_engine.contradiction import detect_contradiction

        new_claim = make_claim("new", entity_id="proj-1", text="status is red")
        existing = [make_claim("old", entity_id="proj-2", text="status is green")]

        contradiction = detect_contradiction(new_claim, existing)
        assert contradiction is None

    def test_ignores_superseded_existing_claim(self):
        from vault.fusion_engine.contradiction import detect_contradiction

        new_claim = make_claim("new", text="status is red")
        existing = [make_claim("old", text="status is green", superseded_by="other")]

        contradiction = detect_contradiction(new_claim, existing)
        assert contradiction is None

    def test_severity_low_for_average_confidence_below_0_5(self):
        from vault.fusion_engine.contradiction import detect_contradiction

        new_claim = make_claim("new", text="status is red", confidence=0.4)
        existing = [make_claim("old", text="status is green", confidence=0.4)]

        contradiction = detect_contradiction(new_claim, existing)
        assert contradiction is not None
        assert contradiction.severity == "low"

    def test_severity_medium_for_average_confidence_between_0_5_and_0_8(self):
        from vault.fusion_engine.contradiction import detect_contradiction

        new_claim = make_claim("new", text="status is red", confidence=0.7)
        existing = [make_claim("old", text="status is green", confidence=0.7)]

        contradiction = detect_contradiction(new_claim, existing)
        assert contradiction is not None
        assert contradiction.severity == "medium"

    def test_severity_high_for_average_confidence_above_0_8(self):
        from vault.fusion_engine.contradiction import detect_contradiction

        new_claim = make_claim("new", text="status is red", confidence=0.9)
        existing = [make_claim("old", text="status is green", confidence=0.95)]

        contradiction = detect_contradiction(new_claim, existing)
        assert contradiction is not None
        assert contradiction.severity == "high"
