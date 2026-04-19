"""Contradiction detection — finding conflicting claims on the same topic/entity."""
from __future__ import annotations

from dataclasses import dataclass

from vault.memory_core.models import Claim


@dataclass(frozen=True)
class Contradiction:
    """Represents a detected contradiction between two claims."""

    existing_claim_id: str
    new_claim_id: str
    severity: str  # "low" | "medium" | "high"

    @property
    def avg_confidence(self) -> float:
        return 0.5  # Placeholder — set by factory


def _severity(avg_confidence: float) -> str:
    if avg_confidence < 0.5:
        return "low"
    elif avg_confidence < 0.8:
        return "medium"
    else:
        return "high"


def detect_contradiction(
    new_claim: Claim,
    existing_claims: list[Claim],
) -> Contradiction | None:
    """Detect if new_claim contradicts any existing claim.

    A contradiction exists when:
    - Same topic_id AND same entity_id
    - Different claim text
    - Existing claim is not already superseded
    - Severity is based on average confidence

    Returns
    -------
    Contradiction or None
    """
    candidates = [
        c for c in existing_claims
        if c.superseded_by is None
        and c.topic_id == new_claim.topic_id
        and c.entity_id == new_claim.entity_id
        and c.text != new_claim.text
    ]

    if not candidates:
        return None

    existing = candidates[0]
    avg_confidence = (new_claim.confidence + existing.confidence) / 2.0
    severity = _severity(avg_confidence)

    return Contradiction(
        existing_claim_id=existing.claim_id,
        new_claim_id=new_claim.claim_id,
        severity=severity,
    )
