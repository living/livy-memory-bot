"""Backlink helpers for Wave B entity frontmatter.

Defines explicit schema builders for:
- relationships[]
- linked_from[]
"""
from __future__ import annotations

from typing import Any

_ALLOWED_CONFIDENCE = {"low", "medium", "high", "unverified"}


def build_relationship(
    to_id: str,
    role: str,
    source_ref: str,
    confidence: str = "medium",
    since: str | None = None,
    until: str | None = None,
) -> dict[str, Any]:
    """Build a relationship item for entity frontmatter.

    Shape:
      {
        to_id, role, since, until, source_ref, confidence
      }
    """
    if not to_id or ":" not in to_id:
        raise ValueError("to_id must be canonical id")
    if not role:
        raise ValueError("role is required")
    if not source_ref:
        raise ValueError("source_ref is required")
    if confidence not in _ALLOWED_CONFIDENCE:
        raise ValueError("invalid confidence")

    return {
        "to_id": to_id,
        "role": role,
        "since": since,
        "until": until,
        "source_ref": source_ref,
        "confidence": confidence,
    }


def build_linked_from(
    entity_ref: str,
    role: str,
    source_ref: str,
    confidence: str = "medium",
) -> dict[str, str]:
    """Build a linked_from item for reverse pointers in frontmatter.

    Shape:
      {
        entity_ref, role, source_ref, confidence
      }
    """
    if not entity_ref or ":" not in entity_ref:
        raise ValueError("entity_ref must be canonical id")
    if not role:
        raise ValueError("role is required")
    if not source_ref:
        raise ValueError("source_ref is required")
    if confidence not in _ALLOWED_CONFIDENCE:
        raise ValueError("invalid confidence")

    return {
        "entity_ref": entity_ref,
        "role": role,
        "source_ref": source_ref,
        "confidence": confidence,
    }
