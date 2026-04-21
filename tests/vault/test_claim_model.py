import pytest
from vault.memory_core.models import Claim, SourceRef


def test_claim_defaults_needs_review_false():
    c = Claim(
        claim_id="test-1",
        entity_id="e1",
        entity_type="project",
        topic_id=None,
        claim_type="status",
        text="test claim",
        source="tldv",
        source_ref=SourceRef(source_id="s1"),
        evidence_ids=["ev1"],
        author="test",
        event_timestamp="2026-04-01T00:00:00Z",
        ingested_at="2026-04-01T00:00:00Z",
        confidence=0.5,
        privacy_level="internal",
    )
    assert c.needs_review is False
    assert c.review_reason is None


def test_claim_accepts_needs_review_and_reason():
    c = Claim(
        claim_id="test-2",
        entity_id="e2",
        entity_type="project",
        topic_id=None,
        claim_type="decision",
        text="we decided to use Vonage",
        source="tldv",
        source_ref=SourceRef(source_id="s2"),
        evidence_ids=["ev2"],
        author="test",
        event_timestamp="2026-04-01T00:00:00Z",
        ingested_at="2026-04-01T00:00:00Z",
        confidence=0.5,
        privacy_level="internal",
        needs_review=True,
        review_reason="sem_evidencia",
    )
    assert c.needs_review is True
    assert c.review_reason == "sem_evidencia"
