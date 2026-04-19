"""Fusion engine orchestration.

Combines supersession checks, contradiction detection, and confidence scoring.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from vault.memory_core.models import Claim
from vault.fusion_engine.confidence import compute_confidence
from vault.fusion_engine.contradiction import Contradiction, detect_contradiction
from vault.fusion_engine.supersession import apply_supersession, should_supersede


@dataclass(frozen=True)
class FusionResult:
    """Result of fusing a claim with existing knowledge."""

    fused_claim: Claim
    contradiction: Contradiction | None
    superseded_claims: list[Claim]
    was_superseded: bool


def _mark_new_claim_superseded(new_claim: Claim, superseding_claim: Claim) -> Claim:
    updated = copy.copy(new_claim)
    updated.superseded_by = superseding_claim.claim_id
    updated.supersession_reason = (
        f"Superseded by existing claim {superseding_claim.claim_id} "
        f"(event {superseding_claim.event_timestamp})"
    )
    updated.supersession_version = 1
    updated.validate()
    return updated


def fuse(new_claim: Claim, existing_claims: list[Claim]) -> FusionResult:
    """Fuse new_claim with existing_claims.

    Steps:
    1) Detect contradiction (same topic/entity, different text, active claims only)
    2) Apply supersession where new claim supersedes older active matching claims
    3) If an existing active matching claim is newer, mark new claim as superseded
    4) Recompute confidence with contradiction penalty and source convergence
    """
    contradiction = detect_contradiction(new_claim, existing_claims)

    superseded_claims: list[Claim] = []
    was_superseded = False
    fused_claim = copy.copy(new_claim)

    # Supersede older matching claims
    for existing in existing_claims:
        if should_supersede(fused_claim, existing):
            superseded_claims.append(apply_supersession(fused_claim, existing))

    # Check whether the new claim is itself superseded by any newer active matching claim
    for existing in existing_claims:
        if (
            existing.entity_id == fused_claim.entity_id
            and existing.claim_type == fused_claim.claim_type
            and existing.superseded_by is None
            and not should_supersede(fused_claim, existing)
            and should_supersede(existing, fused_claim)
        ):
            fused_claim = _mark_new_claim_superseded(fused_claim, existing)
            was_superseded = True
            break

    # Confidence scoring with source convergence (exclude current claim source)
    other_sources = [c.source for c in existing_claims if c.source != fused_claim.source]
    fused_claim.confidence = compute_confidence(
        fused_claim,
        contradicting_claim=next(
            (c for c in existing_claims if contradiction and c.claim_id == contradiction.existing_claim_id),
            None,
        ),
        other_sources=other_sources,
    )

    return FusionResult(
        fused_claim=fused_claim,
        contradiction=contradiction,
        superseded_claims=superseded_claims,
        was_superseded=was_superseded,
    )
