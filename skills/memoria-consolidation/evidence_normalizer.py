#!/usr/bin/env python3
"""
evidence_normalizer.py — Convert SignalEvents into normalized EvidenceItems.
"""
from dataclasses import dataclass
from signal_bus import SignalEvent


@dataclass(frozen=True)
class EvidenceItem:
    topic_ref: str | None
    entity_type: str
    entity_key: str
    claim_type: str
    source: str
    confidence: float
    evidence_ref: str | None
    origin_id: str
    observed_at: str


def normalize_signal_event(event: SignalEvent) -> EvidenceItem:
    desc = (event.payload.get("description") or "").lower()
    entity_type = "issue" if event.signal_type in {"failure", "correction"} else "decision"
    slug = desc.replace(" ", "-")[:60] or event.origin_id.lower()
    return EvidenceItem(
        topic_ref=event.topic_ref,
        entity_type=entity_type,
        entity_key=f"{entity_type}:{slug}",
        claim_type=event.signal_type,
        source=event.source,
        confidence=float(event.payload.get("confidence") or 0.0),
        evidence_ref=event.payload.get("evidence"),
        origin_id=event.origin_id,
        observed_at=event.collected_at,
    )
