#!/usr/bin/env python3
"""
evidence_normalizer.py — Convert SignalEvents into normalized EvidenceItems.
"""
import hashlib
from dataclasses import dataclass
from signal_bus import SignalEvent


def _stable_slug(text: str, max_len: int = 50) -> str:
    """
    Produce a stable, deterministic slug from arbitrary text.
    Uses SHA-1 over the UTF-8 bytes so the same input always produces
    the same output regardless of Python's process-seeded hash().
    """
    text = text.strip()
    if not text:
        return ""
    # Fast path: short-enough ASCII alphanum slugs are stable as-is
    slug = text.lower().replace(" ", "-")
    if len(slug) <= max_len:
        return slug
    # Truncate + append first 8 hex chars of SHA-1 of the full text for stability
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{slug[:max_len]}-{digest}"


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
    # Keep raw description for fuzzy matching in the reconciler
    _description: str = ""

    # Allow extra fields to be passed via __post_init__ compat
    def __init__(self, topic_ref, entity_type, entity_key, claim_type, source,
                 confidence, evidence_ref, origin_id, observed_at, _description=""):
        object.__setattr__(self, "topic_ref", topic_ref)
        object.__setattr__(self, "entity_type", entity_type)
        object.__setattr__(self, "entity_key", entity_key)
        object.__setattr__(self, "claim_type", claim_type)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "evidence_ref", evidence_ref)
        object.__setattr__(self, "origin_id", origin_id)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "_description", _description)


def normalize_signal_event(event: SignalEvent) -> EvidenceItem:
    payload = event.payload or {}
    desc = payload.get("description") or ""

    entity_type = "issue" if event.signal_type in {"failure", "correction"} else "decision"
    slug = _stable_slug(desc, max_len=50)
    if not slug:
        slug = _stable_slug(event.origin_id, max_len=50)

    return EvidenceItem(
        topic_ref=event.topic_ref,
        entity_type=entity_type,
        entity_key=f"{entity_type}:{slug}",
        claim_type=event.signal_type,
        source=event.source,
        confidence=float(payload.get("confidence") or 0.0),
        evidence_ref=payload.get("evidence"),
        origin_id=event.origin_id,
        observed_at=event.collected_at,
        _description=desc,
    )
