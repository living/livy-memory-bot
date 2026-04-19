import uuid
from datetime import datetime, timezone

import pytest

from vault.memory_core.exceptions import CorruptStateError, MissingEvidenceError
from vault.memory_core.models import AuditTrail, Claim, SourceRef


def test_claim_without_evidence_ids_raises():
    ref = SourceRef(source_id="abc", url="https://example.com")

    with pytest.raises(MissingEvidenceError):
        Claim.new(
            entity_type="project",
            entity_id="proj-1",
            claim_type="status",
            text="Card moved to Done",
            source="trello",
            source_ref=ref,
            evidence_ids=[],
            author="lincoln@livingnet.com.br",
            event_timestamp="2026-04-19T12:00:00Z",
            privacy_level="internal",
        )


def test_claim_without_audit_trail_raises():
    ref = SourceRef(source_id="abc", url="https://example.com")

    claim = Claim(
        claim_id="c1",
        entity_type="project",
        entity_id="proj-1",
        topic_id=None,
        claim_type="status",
        text="Card moved to Done",
        source="trello",
        source_ref=ref,
        evidence_ids=["ev-1"],
        author="lincoln@livingnet.com.br",
        event_timestamp="2026-04-19T12:00:00Z",
        ingested_at="2026-04-19T12:01:00Z",
        confidence=0.5,
        privacy_level="public",
        superseded_by=None,
        supersession_reason=None,
        supersession_version=None,
        audit_trail=None,
    )

    with pytest.raises(CorruptStateError):
        claim.validate()


def test_claim_superseded_requires_supersession_version():
    ref = SourceRef(source_id="abc", url="https://example.com")

    claim = Claim.new(
        entity_type="project",
        entity_id="proj-1",
        claim_type="status",
        text="Card moved to Done",
        source="trello",
        source_ref=ref,
        evidence_ids=["ev-1"],
        author="lincoln@livingnet.com.br",
        event_timestamp="2026-04-19T12:00:00Z",
        privacy_level="internal",
    )
    claim.superseded_by = "c2"
    claim.supersession_reason = "newer evidence"
    claim.supersession_version = None

    with pytest.raises(CorruptStateError):
        claim.validate()


def test_valid_claim_passes():
    ref = SourceRef(source_id="abc", url="https://example.com")

    claim = Claim.new(
        entity_type="project",
        entity_id="proj-1",
        claim_type="status",
        text="Card moved to Done",
        source="trello",
        source_ref=ref,
        evidence_ids=["ev-1"],
        author="lincoln@livingnet.com.br",
        event_timestamp="2026-04-19T12:00:00Z",
        privacy_level="internal",
    )

    assert claim.claim_id is not None
    assert claim.confidence == 0.0
    assert claim.audit_trail is not None


def test_claim_new_sets_uuid_and_utc_fields():
    ref = SourceRef(source_id="abc", url="https://example.com")

    claim = Claim.new(
        entity_type="project",
        entity_id="proj-1",
        claim_type="status",
        text="Card moved to Done",
        source="trello",
        source_ref=ref,
        evidence_ids=["ev-1"],
        author="lincoln@livingnet.com.br",
        event_timestamp="2026-04-19T12:00:00Z",
        privacy_level="internal",
    )

    # claim_id is a valid UUID
    assert uuid.UUID(claim.claim_id)
    # audit_trail.trace_id is a valid UUID
    assert uuid.UUID(claim.audit_trail.trace_id)
    # ingested_at is UTC (ends in +00:00)
    dt = datetime.fromisoformat(claim.ingested_at)
    assert dt.tzinfo == timezone.utc


def test_claim_supersession_reason_without_superseded_by_raises():
    ref = SourceRef(source_id="abc", url="https://example.com")

    claim = Claim(
        claim_id="c1",
        entity_type="project",
        entity_id="proj-1",
        topic_id=None,
        claim_type="status",
        text="Card moved to Done",
        source="trello",
        source_ref=ref,
        evidence_ids=["ev-1"],
        author="lincoln@livingnet.com.br",
        event_timestamp="2026-04-19T12:00:00Z",
        ingested_at="2026-04-19T12:01:00Z",
        confidence=0.5,
        privacy_level="public",
        superseded_by=None,
        supersession_reason="some reason",
        supersession_version=None,
        audit_trail=AuditTrail(model_used="test", parser_version="v1", trace_id=str(uuid.uuid4())),
    )

    with pytest.raises(CorruptStateError, match="supersession_reason but superseded_by is None"):
        claim.validate()


def test_claim_supersession_version_without_superseded_by_raises():
    ref = SourceRef(source_id="abc", url="https://example.com")

    claim = Claim(
        claim_id="c1",
        entity_type="project",
        entity_id="proj-1",
        topic_id=None,
        claim_type="status",
        text="Card moved to Done",
        source="trello",
        source_ref=ref,
        evidence_ids=["ev-1"],
        author="lincoln@livingnet.com.br",
        event_timestamp="2026-04-19T12:00:00Z",
        ingested_at="2026-04-19T12:01:00Z",
        confidence=0.5,
        privacy_level="public",
        superseded_by=None,
        supersession_reason=None,
        supersession_version=2,
        audit_trail=AuditTrail(model_used="test", parser_version="v1", trace_id=str(uuid.uuid4())),
    )

    with pytest.raises(CorruptStateError, match="supersession_version but superseded_by is None"):
        claim.validate()
