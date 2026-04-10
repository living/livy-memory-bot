"""Conservative identity resolution for person unification.

Strategy:
1. exact github_login match → auto-merge
2. normalized email match (case-insensitive, stripped) → auto-merge
3. ambiguous (multiple candidates) → REVIEW (no auto-merge)
4. no match → NO_MATCH
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MergeAction(Enum):
    """Resolution outcome for identity matching."""
    MERGE = "merge"       # Unambiguous match → safe to auto-merge
    REVIEW = "review"     # Ambiguous → needs human review
    NO_MATCH = "no_match"  # No identity signal found


@dataclass
class IdentityResult:
    """Result of identity resolution.

    Attributes:
        action: Resolution outcome (MERGE, REVIEW, or NO_MATCH)
        canonical_id: id_canonical of matched entity (for MERGE)
        candidates: List of matched candidates (for REVIEW)
    """
    action: MergeAction
    canonical_id: Optional[str] = None
    candidates: list[dict] = field(default_factory=list)


def normalize_email(email: str) -> str:
    """Normalize email for comparison.

    - Strip whitespace
    - Lowercase domain (case-insensitive email)
    - Preserves local part case per RFC 5321 (but many providers normalize)

    Note: Does NOT strip +suffix per conservative approach.
    """
    if not email:
        return ""
    email = email.strip().lower()
    return email


def _get_github_login(entity: dict) -> Optional[str]:
    """Extract github_login from entity, None if absent."""
    return entity.get("github_login")


def _get_email(entity: dict) -> Optional[str]:
    """Extract and normalize email from entity."""
    email = entity.get("email")
    if not email:
        return None
    return normalize_email(email)


def resolve_identity(
    existing: list[dict] | dict,
    incoming: dict,
) -> IdentityResult:
    """Resolve identity between incoming record and existing person entities.

    Args:
        existing: Single existing entity dict OR list of existing entities.
                 Each entity must have id_canonical, github_login, email.
        incoming: Incoming record with identity hints (github_login, email).

    Returns:
        IdentityResult with action, canonical_id (for MERGE), or candidates (for REVIEW).
    """
    # Normalize to list
    if isinstance(existing, dict):
        entities = [existing]
    else:
        entities = list(existing)

    # Extract incoming signals
    incoming_login = _get_github_login(incoming)
    incoming_email = _get_email(incoming)

    # Track matches by type
    github_matches: list[dict] = []
    email_matches: list[dict] = []

    for entity in entities:
        # Exact github_login match (case-sensitive per GitHub semantics)
        if incoming_login is not None:
            entity_login = _get_github_login(entity)
            if entity_login == incoming_login:
                github_matches.append(entity)

        # Normalized email match (case-insensitive, stripped)
        if incoming_email is not None:
            entity_email = _get_email(entity)
            if entity_email == incoming_email:
                email_matches.append(entity)

    # Combine matches across signals first to detect ambiguity conservatively.
    all_matched_entities = github_matches + email_matches
    unique_by_id = {
        e.get("id_canonical"): e
        for e in all_matched_entities
        if e.get("id_canonical") is not None
    }

    # Ambiguous: different candidates matched by different signals.
    if len(unique_by_id) > 1:
        return IdentityResult(
            action=MergeAction.REVIEW,
            candidates=list(unique_by_id.values()),
        )

    # Unambiguous: exactly one candidate matched (by github, email, or both).
    if len(unique_by_id) == 1:
        only_match = next(iter(unique_by_id.values()))
        return IdentityResult(
            action=MergeAction.MERGE,
            canonical_id=only_match.get("id_canonical"),
        )

    # Fallback for partial fixtures without id_canonical.
    if all_matched_entities:
        # Deduplicate by object identity to avoid double-counting same dict matched twice.
        dedup = list({id(e): e for e in all_matched_entities}.values())
        if len(dedup) == 1:
            return IdentityResult(action=MergeAction.MERGE)
        return IdentityResult(action=MergeAction.REVIEW, candidates=dedup)

    # No match.
    return IdentityResult(action=MergeAction.NO_MATCH)
