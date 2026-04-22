"""Supersession logic — determining when a new claim renders an older one stale."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from difflib import SequenceMatcher

from vault.memory_core.models import Claim


def _parse_ts(ts: str) -> datetime:
    """Parse an ISO timestamp, treating naive datetimes as UTC."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def should_supersede(candidate: Claim, existing: Claim) -> bool:
    """Return True when candidate supersedes existing.

    Rules:
    - Same entity_id
    - Same claim_type
    - status claim never supersedes a decision claim
    - candidate.event_timestamp is strictly newer than existing.event_timestamp
    - existing is not already superseded
    - decision superseding decision requires either:
      - text similarity > 0.7, or
      - explicit supersession_reason on candidate
    """
    if candidate.entity_id != existing.entity_id:
        return False

    # Hard guard: status claims must never supersede decisions.
    if candidate.claim_type == "status" and existing.claim_type == "decision":
        return False

    if candidate.claim_type != existing.claim_type:
        return False
    if existing.superseded_by is not None:
        return False

    candidate_ts = _parse_ts(candidate.event_timestamp)
    existing_ts = _parse_ts(existing.event_timestamp)

    if candidate_ts <= existing_ts:
        return False

    if candidate.claim_type == "decision":
        has_explicit_reason = candidate.supersession_reason is not None
        has_high_similarity = SequenceMatcher(
            None,
            candidate.text.lower(),
            existing.text.lower(),
        ).ratio() > 0.7
        if not (has_explicit_reason or has_high_similarity):
            return False

    return True


def apply_supersession(candidate: Claim, existing: Claim) -> Claim:
    """Return a new Claim (existing) marked as superseded by candidate.

    Raises CorruptStateError if existing is already superseded.
    """
    from vault.memory_core.exceptions import CorruptStateError

    if existing.superseded_by is not None:
        raise CorruptStateError(
            f"Claim {existing.claim_id} is already superseded by "
            f"{existing.superseded_by}; cannot supersede again"
        )

    superseded = copy.copy(existing)
    superseded.superseded_by = candidate.claim_id
    superseded.supersession_reason = (
        f"Superseded by {candidate.claim_id} "
        f"(event {candidate.event_timestamp})"
    )
    superseded.supersession_version = 1

    # Validate the resulting state
    superseded.validate()

    return superseded
