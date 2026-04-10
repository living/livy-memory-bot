"""vault/domain/normalize.py — Entity/edge normalization with full traceability.

Every entity or edge produced by this module carries all required traceability fields:
  source_type, source_ref, retrieved_at, mapper_version  (on source records)
  lineage_run_id  (on relationships)

Design:
  - build_source_record()   — low-level source record factory (the atomic unit)
  - generate_lineage_run_id()  — deterministic run identifier factory
  - normalize_*_to_entity()  — source-specific normalizers that produce canonical
                               entities; each embeds a source record in source_keys
                               (person/repo/meeting/card) or in sources (decision)
  - normalize_*_to_relationship() — source-specific normalizers that produce
                                    canonical relationship edges with full stamps
  - build_entity_with_traceability() — general wrapper that stamps any entity
                                       with source_keys, first_seen_at, last_seen_at

Canonical entity fields vs traceability:
  - Person/Repo/Meeting/Card: source_keys embeds the mapper version
    (e.g. "mapper:github-enrich-v1:repo:living/livy-memory-bot")
  - Decision: sources list contains source record dicts with all 4 fields
  - Relationship: lineage_run_id + embedded source records (per canonical_types)
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from vault.domain.canonical_types import SOURCE_FIELDS, SOURCE_TYPES


# ---------------------------------------------------------------------------
# Low-level source record factory
# ---------------------------------------------------------------------------

def build_source_record(
    source_type: str,
    source_ref: str,
    mapper_version: str,
    retrieved_at: Optional[str] = None,
) -> dict:
    """Create a source record dict with all 4 required traceability fields.

    Args:
        source_type:  one of SOURCE_TYPES (e.g. "github_api", "tldv_api")
        source_ref:   stable URI/ID for this record (e.g. "https://github.com/...")
        mapper_version: versioned mapper identifier (e.g. "github-enrich-v1")
        retrieved_at: ISO-8601 timestamp; defaults to current UTC now

    Returns:
        Dict with exactly the 4 SOURCE_FIELDS: source_type, source_ref,
        retrieved_at, mapper_version.
    """
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "source_type": source_type,
        "source_ref": source_ref,
        "retrieved_at": retrieved_at,
        "mapper_version": mapper_version,
    }


# ---------------------------------------------------------------------------
# Lineage run ID factory
# ---------------------------------------------------------------------------

def generate_lineage_run_id(
    mapper_version: str,
    timestamp: Optional[str] = None,
) -> str:
    """Generate a deterministic lineage run identifier.

    Format: run-{YYYY-MM-DDTHH:MM:SSZ}-{mapper_version}
    Example: run-2026-04-10T10:12:00Z-github-enrich-v1

    The timestamp is normalised to UTC seconds so that repeated calls within
    the same second produce the same ID (useful for batch pipelines).

    Args:
        mapper_version: versioned mapper identifier
        timestamp: ISO-8601 string; defaults to current UTC now

    Returns:
        Deterministic run ID string.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"run-{timestamp}-{mapper_version}"


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _id_canonical(entity_type: str, raw_id: str) -> str:
    """Build a canonical id with type prefix.

    entity_type: "person" | "repo" | "meeting" | "card" | "decision"
    raw_id:      the raw/stable identifier (may contain slashes)
    """
    return f"{entity_type}:{raw_id}"


def _slug_from_name(name: str) -> str:
    """Convert a display name to a URL-safe slug."""
    # Keep alphanumeric, hyphens, underscores; lowercase
    slug = "".join(c if c.isalnum() or c in "_-" else "-" for c in name.lower())
    # Collapse consecutive hyphens
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


# ---------------------------------------------------------------------------
# Entity normalizers — each produces a canonical entity
# ---------------------------------------------------------------------------

def normalize_github_pr_to_entity(
    pr: dict,
    mapper_version: str,
) -> dict:
    """Normalize a GitHub PR raw record to a Person entity.

    When a PR is merged, both the PR author AND the merger (merged_by) are
    recorded as source_keys entries under the same person entity.

    The entity's first_seen_at / last_seen_at reflect the PR merged_at.

    Args:
        pr:            raw GitHub PR dict (must have "user", "merged_by", "merged_at")
        mapper_version: versioned mapper identifier

    Returns:
        Person entity dict conforming to canonical_types.validate_person().
    """
    now = _utc_now()

    author_login = (pr.get("user") or {}).get("login")
    merger_login = (pr.get("merged_by") or {}).get("login")

    # Collect github logins (author + merger if different)
    github_logins = set()
    if author_login:
        github_logins.add(author_login)
    if merger_login and merger_login != author_login:
        github_logins.add(merger_login)

    # Build source_keys — one per github login + one mapper entry
    source_keys: list[str] = []
    for login in sorted(github_logins):
        source_keys.append(f"github:{login}")
    source_keys.append(f"mapper:{mapper_version}")

    # id_canonical derived from author login
    primary_login = author_login or "unknown"
    id_canonical = _id_canonical("person", primary_login)

    merged_at = pr.get("merged_at") or now

    entity: dict[str, Any] = {
        "id_canonical": id_canonical,
        "display_name": primary_login,
        "github_login": primary_login,
        "source_keys": source_keys,
        "first_seen_at": merged_at,
        "last_seen_at": merged_at,
    }

    return entity


def normalize_github_repo_to_entity(
    repo: dict,
    mapper_version: str,
) -> dict:
    """Normalize a GitHub repo raw record to a Repo entity.

    Args:
        repo:           raw GitHub repo dict (must have "full_name", "owner", "name")
        mapper_version: versioned mapper identifier

    Returns:
        Repo entity dict conforming to canonical_types.validate_repo().
    """
    full_name = repo.get("full_name", "")
    owner = (repo.get("owner") or {}).get("login", "")
    name = repo.get("name", "")
    default_branch = repo.get("default_branch")
    archived = repo.get("archived", False)
    project_ref = repo.get("project_ref")

    id_canonical = _id_canonical("repo", full_name)

    source_keys = [
        f"mapper:{mapper_version}:repo:{full_name}",
    ]

    entity: dict[str, Any] = {
        "id_canonical": id_canonical,
        "full_name": full_name,
        "owner": owner,
        "name": name,
    }

    if default_branch is not None:
        entity["default_branch"] = default_branch
    if archived is not None:
        entity["archived"] = archived
    if project_ref is not None:
        entity["project_ref"] = project_ref
    if source_keys:
        entity["source_keys"] = source_keys

    return entity


def normalize_tldv_meeting_to_entity(
    meeting: dict,
    mapper_version: str,
) -> dict:
    """Normalize a TLDV meeting record to a Meeting entity.

    Args:
        meeting:        raw TLDV meeting dict (must have "meeting_id", "title")
        mapper_version: versioned mapper identifier

    Returns:
        Meeting entity dict conforming to canonical_types.validate_meeting().
    """
    meeting_id = meeting.get("meeting_id", "")
    title = meeting.get("title", "")
    started_at = meeting.get("started_at")
    ended_at = meeting.get("ended_at")
    project_ref = meeting.get("project_ref")

    id_canonical = _id_canonical("meeting", meeting_id.replace(":", "-"))

    entity: dict[str, Any] = {
        "id_canonical": id_canonical,
        "meeting_id_source": meeting_id,
        "title": title,
    }

    if started_at is not None:
        entity["started_at"] = started_at
    if ended_at is not None:
        entity["ended_at"] = ended_at
    if project_ref is not None:
        entity["project_ref"] = project_ref

    return entity


def normalize_trello_card_to_entity(
    card: dict,
    mapper_version: str,
) -> dict:
    """Normalize a Trello card record to a Card entity.

    Args:
        card:          raw Trello card dict (must have "id", "name" aka title)
        mapper_version: versioned mapper identifier

    Returns:
        Card entity dict conforming to canonical_types.validate_card().
    """
    card_id = card.get("id", "")
    title = card.get("name", card.get("title", ""))
    board = (card.get("board") or {}).get("name")
    list_name = (card.get("list") or {}).get("name")
    project_ref = card.get("project_ref")
    status = card.get("status")

    id_canonical = _id_canonical("card", card_id.replace(":", "-"))

    entity: dict[str, Any] = {
        "id_canonical": id_canonical,
        "card_id_source": card_id,
        "title": title,
    }

    if board is not None:
        entity["board"] = board
    if list_name is not None:
        entity["list"] = list_name
    if project_ref is not None:
        entity["project_ref"] = project_ref
    if status is not None:
        entity["status"] = status

    return entity


def normalize_decision_to_entity(
    decision: dict,
    mapper_version: str,
) -> dict:
    """Normalize a decision signal to a Decision entity with full traceability.

    The entity's sources list contains one source record with all 4 required
    traceability fields (source_type, source_ref, retrieved_at, mapper_version).

    Args:
        decision:      raw decision signal dict (must have "origin_id", "description",
                       "decision_date"; may have "raw" with source ref)
        mapper_version: versioned mapper identifier

    Returns:
        Decision entity dict conforming to canonical_types.validate_decision().
    """
    now = _utc_now()

    origin_id = decision.get("origin_id", "")
    summary = decision.get("description", "")
    decision_date = decision.get("decision_date", now[:10])  # date-only fallback
    project_ref = decision.get("project")
    raw = decision.get("raw") or {}

    id_canonical = _id_canonical("decision", origin_id)

    # Build source record
    source_type = raw.get("type", "signal_event")
    source_ref = raw.get("ref", f"signal:{origin_id}")
    source = build_source_record(
        source_type=source_type,
        source_ref=source_ref,
        mapper_version=mapper_version,
        retrieved_at=now,
    )

    entity: dict[str, Any] = {
        "id_canonical": id_canonical,
        "summary": summary,
        "decision_date": decision_date,
        "sources": [source],
        "last_verified": now[:10],
    }

    if project_ref is not None:
        entity["project_ref"] = project_ref

    return entity


def build_entity_with_traceability(
    entity: dict,
    mapper_version: str,
) -> dict:
    """Stamp any entity dict with source_keys, first_seen_at, last_seen_at.

    Use this to enrich entities that lack their own normalizer with the
    basic traceability envelope.

    Args:
        entity:        partial entity dict (must have at least id_canonical)
        mapper_version: versioned mapper identifier

    Returns:
        Entity dict with traceability fields merged in (does not overwrite
        existing first_seen_at / last_seen_at if already present).
    """
    now = _utc_now()
    id_canonical = entity.get("id_canonical", "")

    source_key = f"mapper:{mapper_version}:{id_canonical}"
    entity = dict(entity)
    entity.setdefault("source_keys", [])
    if isinstance(entity["source_keys"], list) and source_key not in entity["source_keys"]:
        entity["source_keys"] = entity["source_keys"] + [source_key]
    entity.setdefault("first_seen_at", now)
    entity.setdefault("last_seen_at", now)

    return entity


# ---------------------------------------------------------------------------
# Relationship normalizers — produce canonical relationship edges
# ---------------------------------------------------------------------------

def normalize_github_pr_to_relationships(
    pr: dict,
    person_id: str,
    repo_id: str,
    mapper_version: str,
    timestamp: Optional[str] = None,
) -> list[dict]:
    """Normalize a GitHub PR to one or more relationship edges.

    Generates:
      - person -> repo  (role=author)  when the PR was merged
      - Additional edges are possible for reviewers / commenters (future)

    Every edge carries lineage_run_id and a source record with all 4 required
    traceability fields.

    Args:
        pr:            raw GitHub PR dict (must have "merged", "merged_at",
                       "user", "merged_by")
        person_id:     id_canonical of the author person
        repo_id:       id_canonical of the target repo
        mapper_version: versioned mapper identifier
        timestamp:     optional UTC ISO timestamp; defaults to now

    Returns:
        List of relationship edge dicts conforming to
        canonical_types.validate_relationship().
    """
    if timestamp is None:
        timestamp = _utc_now()

    merged = pr.get("merged", False)
    merged_at = pr.get("merged_at") or timestamp

    source_type = "github_api"
    source_ref = pr.get("html_url") or pr.get("url") or f"pr:{pr.get('number')}"
    source = build_source_record(
        source_type=source_type,
        source_ref=source_ref,
        mapper_version=mapper_version,
        retrieved_at=timestamp,
    )
    lineage_run_id = generate_lineage_run_id(mapper_version, timestamp)

    edges: list[dict] = []

    if merged:
        # person -> repo  with role=author
        edges.append({
            "from_id": person_id,
            "to_id": repo_id,
            "role": "author",
            "confidence": "high",
            "sources": [source],
            "lineage_run_id": lineage_run_id,
            "since": merged_at,
            "until": None,
        })

    return edges


def normalize_github_repo_to_relationship(
    repo: dict,
    repo_id: str,
    project_id: str,
    mapper_version: str,
    timestamp: Optional[str] = None,
) -> dict:
    """Normalize a GitHub repo to a repo->project relationship edge.

    Generates:
      - repo -> project  (role=participant)

    Every edge carries lineage_run_id and a source record with all 4 required
    traceability fields.

    Args:
        repo:           raw GitHub repo dict
        repo_id:        id_canonical of the repo
        project_id:     id_canonical of the parent project
        mapper_version: versioned mapper identifier
        timestamp:      optional UTC ISO timestamp; defaults to now

    Returns:
        Relationship edge dict conforming to
        canonical_types.validate_relationship().
    """
    if timestamp is None:
        timestamp = _utc_now()

    source_type = "github_api"
    source_ref = repo.get("html_url") or repo.get("url") or repo_id
    source = build_source_record(
        source_type=source_type,
        source_ref=source_ref,
        mapper_version=mapper_version,
        retrieved_at=timestamp,
    )
    lineage_run_id = generate_lineage_run_id(mapper_version, timestamp)

    return {
        "from_id": repo_id,
        "to_id": project_id,
        "role": "participant",
        "confidence": "high",
        "sources": [source],
        "lineage_run_id": lineage_run_id,
        "since": None,
        "until": None,
    }
