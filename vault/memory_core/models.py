from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
import uuid


EntityType = Literal[
    "person",
    "project",
    "repository",
    "pull_request",
    "meeting",
    "topic",
    "decision",
    "email_thread",
]
ClaimType = Literal[
    "status",
    "decision",
    "action_item",
    "risk",
    "ownership",
    "timeline_event",
    "linkage",
]
PrivacyLevel = Literal["public", "internal", "restricted"]
Source = Literal["trello", "github", "tldv", "gmail", "gcal"]


@dataclass
class SourceRef:
    source_id: str
    url: str | None = None
    blob_path: str | None = None


@dataclass
class AuditTrail:
    model_used: str
    parser_version: str
    trace_id: str


@dataclass
class Claim:
    claim_id: str
    entity_type: EntityType
    entity_id: str
    topic_id: str | None
    claim_type: ClaimType
    text: str
    source: Source
    source_ref: SourceRef
    evidence_ids: list[str]
    author: str
    event_timestamp: str
    ingested_at: str
    confidence: float
    privacy_level: PrivacyLevel
    superseded_by: str | None = None
    supersession_reason: str | None = None
    supersession_version: int | None = None
    audit_trail: AuditTrail | None = None

    def validate(self) -> None:
        """Validate all invariants. Raises CorruptStateError on violation."""
        from vault.memory_core.exceptions import CorruptStateError, MissingEvidenceError

        if not self.evidence_ids:
            raise MissingEvidenceError(
                f"Claim {self.claim_id} has empty evidence_ids — "
                "every claim requires at least one evidence_id"
            )
        if self.audit_trail is None:
            raise CorruptStateError(
                f"Claim {self.claim_id} has no audit_trail — "
                "write without audit is rejected"
            )
        if self.superseded_by is not None:
            if not self.supersession_reason:
                raise CorruptStateError(
                    f"Claim {self.claim_id} superseded without supersession_reason"
                )
            if self.supersession_version is None:
                raise CorruptStateError(
                    f"Claim {self.claim_id} superseded without supersession_version"
                )

    @staticmethod
    def new(
        entity_type: EntityType,
        entity_id: str,
        claim_type: ClaimType,
        text: str,
        source: Source,
        source_ref: SourceRef,
        evidence_ids: list[str],
        author: str,
        event_timestamp: str,
        privacy_level: PrivacyLevel,
        topic_id: str | None = None,
        model_used: str = "omniroute/fastest",
        parser_version: str = "v1",
    ) -> "Claim":
        claim_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        audit = AuditTrail(
            model_used=model_used,
            parser_version=parser_version,
            trace_id=str(uuid.uuid4()),
        )
        claim = Claim(
            claim_id=claim_id,
            entity_type=entity_type,
            entity_id=entity_id,
            topic_id=topic_id,
            claim_type=claim_type,
            text=text,
            source=source,
            source_ref=source_ref,
            evidence_ids=evidence_ids,
            author=author,
            event_timestamp=event_timestamp,
            ingested_at=now,
            confidence=0.0,
            privacy_level=privacy_level,
            superseded_by=None,
            supersession_reason=None,
            supersession_version=None,
            audit_trail=audit,
        )
        claim.validate()
        return claim


@dataclass
class Evidence:
    evidence_id: str
    source: Source
    source_id: str
    raw_ref: str
    event_timestamp: str
    author: str
    privacy_level: PrivacyLevel
    content_hash: str
    blob_path: str | None = None
