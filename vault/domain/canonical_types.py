"""
vault/domain/canonical_types.py — Canonical domain contract validators.

Defines typed validators for all Living domain entities and relationships.
Each validator returns True on success or a list of field errors on failure.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Union

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ID_PREFIXES = frozenset([
    "person:",
    "project:",
    "repo:",
    "meeting:",
    "card:",
    "decision:",
])

# Allowed source types across all entities
SOURCE_TYPES = frozenset([
    "github",
    "tldv",
    "trello",
    "manual",
    "signal",
])

# Relationship roles
RELATIONSHIP_ROLES = frozenset([
    "author",
    "reviewer",
    "commenter",
    "member",
    "contributor",
    "owner",
    "participant",
    "assignee",
    "creator",
    "depends_on",
    "implements",
    "references",
])

# Decision confidence levels
DECISION_CONFIDENCES = frozenset([
    "high",
    "medium",
    "low",
    "unverified",
])

# Required traceability fields shared by all entity types
TRACEABILITY_FIELDS = frozenset([
    "source_type",
    "source_ref",
    "retrieved_at",
    "lineage_run_id",
    "mapper_version",
])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_valid_id_prefix(entity_id: Any) -> bool:
    """Check if an id_canonical uses a known prefix with a colon separator."""
    if not isinstance(entity_id, str) or not entity_id.strip():
        return False
    return any(entity_id.startswith(p) for p in ID_PREFIXES)


def is_iso_date(value: Any) -> bool:
    """Check if value is a valid ISO date (date-only or full datetime)."""
    if not isinstance(value, str):
        return False
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S+00:00"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            pass
    # Also accept with 'Z' suffix
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _check_traceability(entity: dict) -> list[str]:
    """Return list of missing traceability field names."""
    return [f for f in TRACEABILITY_FIELDS if f not in entity]


def _error_list(*fields: str) -> list[str]:
    """Construct a list of field error strings."""
    return list(fields)


# ---------------------------------------------------------------------------
# Entity validators — each returns True or list of error strings
# ---------------------------------------------------------------------------

def validate_person(entity: dict) -> Union[bool, list[str]]:
    """Validate a Person entity."""
    errors: list[str] = []

    # Required fields
    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not is_valid_id_prefix(entity["id_canonical"]):
        errors.append("id_canonical_prefix")
    elif not entity["id_canonical"].startswith("person:"):
        errors.append("id_canonical_prefix")

    if "name" not in entity:
        errors.append("name")

    # Optional but must be valid if present
    if "github_login" in entity and not isinstance(entity["github_login"], str):
        errors.append("github_login_type")

    if "email" in entity and not isinstance(entity["email"], str):
        errors.append("email_type")

    # Unknown extra fields — allow traceability + optional fields
    allowed = {"id_canonical", "name", "github_login", "email"} | TRACEABILITY_FIELDS
    unknown = set(entity.keys()) - allowed
    if unknown:
        errors.extend(f"unknown_field:{u}" for u in sorted(unknown))

    # Traceability
    errors.extend(_check_traceability(entity))

    return True if not errors else errors


def validate_project(entity: dict) -> Union[bool, list[str]]:
    """Validate a Project entity."""
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("project:"):
        errors.append("id_canonical_prefix")

    if "name" not in entity:
        errors.append("name")

    # Traceability
    errors.extend(_check_traceability(entity))

    return True if not errors else errors


def validate_repo(entity: dict) -> Union[bool, list[str]]:
    """Validate a Repo entity."""
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("repo:"):
        errors.append("id_canonical_prefix")

    if "name" not in entity:
        errors.append("name")

    if "org" not in entity:
        errors.append("org")

    # Traceability
    errors.extend(_check_traceability(entity))

    return True if not errors else errors


def validate_meeting(entity: dict) -> Union[bool, list[str]]:
    """Validate a Meeting entity."""
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("meeting:"):
        errors.append("id_canonical_prefix")

    if "name" not in entity:
        errors.append("name")

    if "date" not in entity:
        errors.append("date")
    elif not is_iso_date(entity["date"]):
        errors.append("date_format")

    # Traceability
    errors.extend(_check_traceability(entity))

    return True if not errors else errors


def validate_card(entity: dict) -> Union[bool, list[str]]:
    """Validate a Card entity."""
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("card:"):
        errors.append("id_canonical_prefix")

    if "name" not in entity:
        errors.append("name")

    # Traceability
    errors.extend(_check_traceability(entity))

    return True if not errors else errors


def validate_decision(entity: dict) -> Union[bool, list[str]]:
    """Validate a Decision entity."""
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("decision:"):
        errors.append("id_canonical_prefix")

    if "title" not in entity:
        errors.append("title")

    if "evidence" not in entity:
        errors.append("evidence")
    elif not isinstance(entity["evidence"], list):
        errors.append("evidence_type")

    if "confidence" not in entity:
        errors.append("confidence")
    elif entity["confidence"] not in DECISION_CONFIDENCES:
        errors.append("confidence_allowed")

    # Traceability
    errors.extend(_check_traceability(entity))

    return True if not errors else errors


def validate_relationship(entity: dict) -> Union[bool, list[str]]:
    """Validate a Relationship edge."""
    errors: list[str] = []

    if "from" not in entity:
        errors.append("from")
    if "to" not in entity:
        errors.append("to")
    if "role" not in entity:
        errors.append("role")
    elif entity["role"] not in RELATIONSHIP_ROLES:
        errors.append("role_allowed")

    # Traceability
    errors.extend(_check_traceability(entity))

    return True if not errors else errors
