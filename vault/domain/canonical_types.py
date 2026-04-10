"""Canonical domain contract validators — aligned 1:1 with final spec."""
from __future__ import annotations

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

# Allowed source_type values per spec
SOURCE_TYPES = frozenset([
    "github_api",
    "tldv_api",
    "trello_api",
    "supabase_rest",
    "signal_event",
    "exec",
    "openclaw_config",
    "api_direct",
    "curated_topic",
    "observation",
    "chat_history",
])

# Allowed relationship roles per spec
RELATIONSHIP_ROLES = frozenset([
    "author",
    "reviewer",
    "commenter",
    "participant",
    "assignee",
    "decision_maker",
])

# Confidence enum per spec
CONFIDENCE_LEVELS = frozenset([
    "high",
    "medium",
    "low",
    "unverified",
])

# Source record fields per spec
SOURCE_FIELDS = frozenset([
    "source_type",
    "source_ref",
    "retrieved_at",
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
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _unknown_fields(entity: dict, allowed: set) -> list[str]:
    """Return sorted list of unknown field error strings."""
    return [f"unknown_field:{f}" for f in sorted(set(entity.keys()) - allowed)]


def _check_source_record(source: Any, idx: int) -> list[str]:
    """Validate a single source record embedded in Decision or Relationship.

    Returns a list of error strings with idx prefix, or [] if valid.
    """
    errors: list[str] = []
    p = f"sources[{idx}]."

    if not isinstance(source, dict):
        errors.append(f"{p}record_type")
        return errors

    if "source_type" not in source:
        errors.append(f"{p}source_type")
    elif source["source_type"] not in SOURCE_TYPES:
        errors.append(f"{p}source_type_allowed")

    if "source_ref" not in source:
        errors.append(f"{p}source_ref")

    if "retrieved_at" not in source:
        errors.append(f"{p}retrieved_at")

    if "mapper_version" not in source:
        errors.append(f"{p}mapper_version")
    elif not isinstance(source["mapper_version"], str) or not source["mapper_version"].strip():
        errors.append(f"{p}mapper_version_type")

    return errors


# ---------------------------------------------------------------------------
# Entity validators — each returns True or list of error strings
# ---------------------------------------------------------------------------

def validate_person(entity: dict) -> Union[bool, list[str]]:
    """Validate a Person entity per spec.

    Required:  id_canonical, source_keys, first_seen_at, last_seen_at
    Optional:   display_name, github_login, email
    Optional:  confidence (enum: high|medium|low|unverified)
    """
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not is_valid_id_prefix(entity["id_canonical"]):
        errors.append("id_canonical_prefix")
    elif not entity["id_canonical"].startswith("person:"):
        errors.append("id_canonical_prefix")

    if "source_keys" not in entity:
        errors.append("source_keys")
    elif not isinstance(entity["source_keys"], list):
        errors.append("source_keys_type")

    if "first_seen_at" not in entity:
        errors.append("first_seen_at")
    elif not is_iso_date(entity["first_seen_at"]):
        errors.append("first_seen_at_format")

    if "last_seen_at" not in entity:
        errors.append("last_seen_at")
    elif not is_iso_date(entity["last_seen_at"]):
        errors.append("last_seen_at_format")

    if "confidence" in entity and entity["confidence"] not in CONFIDENCE_LEVELS:
        errors.append("confidence_allowed")

    allowed = {
        "id_canonical",
        "display_name",
        "github_login",
        "email",
        "source_keys",
        "first_seen_at",
        "last_seen_at",
        "confidence",
    }
    errors.extend(_unknown_fields(entity, allowed))

    return True if not errors else errors


def validate_project(entity: dict) -> Union[bool, list[str]]:
    """Validate a Project entity per spec.

    Required:  id_canonical, slug, name
    Optional:  status, aliases, confidence (enum)
    """
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("project:"):
        errors.append("id_canonical_prefix")

    if "slug" not in entity:
        errors.append("slug")
    elif not isinstance(entity["slug"], str):
        errors.append("slug_type")

    if "name" not in entity:
        errors.append("name")
    elif not isinstance(entity["name"], str):
        errors.append("name_type")

    if "confidence" in entity and entity["confidence"] not in CONFIDENCE_LEVELS:
        errors.append("confidence_allowed")

    allowed = {
        "id_canonical",
        "slug",
        "name",
        "status",
        "aliases",
        "confidence",
    }
    errors.extend(_unknown_fields(entity, allowed))

    return True if not errors else errors


def validate_repo(entity: dict) -> Union[bool, list[str]]:
    """Validate a Repo entity per spec.

    Required:  id_canonical, full_name, owner, name
    Optional:  default_branch, archived, project_ref, source_keys
    """
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("repo:"):
        errors.append("id_canonical_prefix")

    if "full_name" not in entity:
        errors.append("full_name")
    elif not isinstance(entity["full_name"], str):
        errors.append("full_name_type")

    if "owner" not in entity:
        errors.append("owner")
    elif not isinstance(entity["owner"], str):
        errors.append("owner_type")

    if "name" not in entity:
        errors.append("name")
    elif not isinstance(entity["name"], str):
        errors.append("name_type")

    if "source_keys" in entity and not isinstance(entity["source_keys"], list):
        errors.append("source_keys_type")

    allowed = {
        "id_canonical",
        "full_name",
        "owner",
        "name",
        "default_branch",
        "archived",
        "project_ref",
        "source_keys",
    }
    errors.extend(_unknown_fields(entity, allowed))

    return True if not errors else errors


def validate_meeting(entity: dict) -> Union[bool, list[str]]:
    """Validate a Meeting entity per spec.

    Required:  id_canonical, meeting_id_source
    Optional:  title, started_at, ended_at, project_ref
    """
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("meeting:"):
        errors.append("id_canonical_prefix")

    if "meeting_id_source" not in entity:
        errors.append("meeting_id_source")
    elif not isinstance(entity["meeting_id_source"], str):
        errors.append("meeting_id_source_type")

    if "started_at" in entity and not is_iso_date(entity["started_at"]):
        errors.append("started_at_format")

    if "ended_at" in entity and not is_iso_date(entity["ended_at"]):
        errors.append("ended_at_format")

    allowed = {
        "id_canonical",
        "meeting_id_source",
        "title",
        "started_at",
        "ended_at",
        "project_ref",
    }
    errors.extend(_unknown_fields(entity, allowed))

    return True if not errors else errors


def validate_card(entity: dict) -> Union[bool, list[str]]:
    """Validate a Card entity per spec.

    Required:  id_canonical, card_id_source, title
    Optional:  board, list, project_ref, status
    """
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("card:"):
        errors.append("id_canonical_prefix")

    if "card_id_source" not in entity:
        errors.append("card_id_source")
    elif not isinstance(entity["card_id_source"], str):
        errors.append("card_id_source_type")

    if "title" not in entity:
        errors.append("title")
    elif not isinstance(entity["title"], str):
        errors.append("title_type")

    allowed = {
        "id_canonical",
        "card_id_source",
        "title",
        "board",
        "list",
        "project_ref",
        "status",
    }
    errors.extend(_unknown_fields(entity, allowed))

    return True if not errors else errors


def validate_decision(entity: dict) -> Union[bool, list[str]]:
    """Validate a Decision entity per spec.

    Required:  id_canonical, summary, decision_date, sources, last_verified
    Optional:  project_ref, confidence (enum)
    """
    errors: list[str] = []

    if "id_canonical" not in entity:
        errors.append("id_canonical")
    elif not entity["id_canonical"].startswith("decision:"):
        errors.append("id_canonical_prefix")

    if "summary" not in entity:
        errors.append("summary")
    elif not isinstance(entity["summary"], str):
        errors.append("summary_type")

    if "decision_date" not in entity:
        errors.append("decision_date")
    elif not is_iso_date(entity["decision_date"]):
        errors.append("decision_date_format")

    if "sources" not in entity:
        errors.append("sources")
    elif not isinstance(entity["sources"], list):
        errors.append("sources_type")
    else:
        for idx, src in enumerate(entity["sources"]):
            errors.extend(_check_source_record(src, idx))

    if "last_verified" not in entity:
        errors.append("last_verified")
    elif not is_iso_date(entity["last_verified"]):
        errors.append("last_verified_format")

    if "confidence" in entity and entity["confidence"] not in CONFIDENCE_LEVELS:
        errors.append("confidence_allowed")

    allowed = {
        "id_canonical",
        "summary",
        "decision_date",
        "project_ref",
        "confidence",
        "sources",
        "last_verified",
    }
    errors.extend(_unknown_fields(entity, allowed))

    return True if not errors else errors


def validate_relationship(entity: dict) -> Union[bool, list[str]]:
    """Validate a Relationship edge per spec.

    Required:  from_id, to_id, role, confidence, sources, lineage_run_id
    Optional:  since, until, window_days
    """
    errors: list[str] = []

    if "from_id" not in entity:
        errors.append("from_id")
    elif not isinstance(entity["from_id"], str):
        errors.append("from_id_type")

    if "to_id" not in entity:
        errors.append("to_id")
    elif not isinstance(entity["to_id"], str):
        errors.append("to_id_type")

    if "role" not in entity:
        errors.append("role")
    elif entity["role"] not in RELATIONSHIP_ROLES:
        errors.append("role_allowed")

    if "confidence" not in entity:
        errors.append("confidence")
    elif entity["confidence"] not in CONFIDENCE_LEVELS:
        errors.append("confidence_allowed")

    if "sources" not in entity:
        errors.append("sources")
    elif not isinstance(entity["sources"], list):
        errors.append("sources_type")
    else:
        for idx, src in enumerate(entity["sources"]):
            errors.extend(_check_source_record(src, idx))

    if "lineage_run_id" not in entity:
        errors.append("lineage_run_id")
    elif not isinstance(entity["lineage_run_id"], str):
        errors.append("lineage_run_id_type")

    allowed = {
        "from_id",
        "to_id",
        "role",
        "since",
        "until",
        "window_days",
        "confidence",
        "sources",
        "lineage_run_id",
    }
    errors.extend(_unknown_fields(entity, allowed))

    return True if not errors else errors
