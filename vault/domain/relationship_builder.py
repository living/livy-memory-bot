"""Relationship builder — generates canonical relationship edges by role.

Generates:
- person -> repo edges: author, reviewer, commenter
- repo -> project edges: participant
- inferred person -> project edges via repo participation
- window_days as query-origin metadata
- full traceability stamps on every edge
"""
from __future__ import annotations

from typing import Any

from vault.domain.canonical_types import RELATIONSHIP_ROLES, SOURCE_FIELDS, SOURCE_TYPES


# Default confidence for generated edges (source-derived).
_DEFAULT_CONFIDENCE = "high"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _validate_source(source: dict) -> None:
    """Validate minimal source record requirements for traceability."""
    missing = [field for field in SOURCE_FIELDS if field not in source]
    if missing:
        raise ValueError(f"source missing required fields: {missing}")
    source_type = source.get("source_type")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"invalid source_type: {source_type!r}")


def _build_edge(
    from_id: str,
    to_id: str,
    role: str,
    source: dict,
    lineage_run_id: str,
    since: str | None = None,
    until: str | None = None,
    window_days: int | None = None,
    confidence: str = _DEFAULT_CONFIDENCE,
) -> dict:
    """Shared edge constructor with full traceability stamp.

    Required:
        from_id:  id_canonical of source entity (e.g. person:lincolnq)
        to_id:    id_canonical of target entity (e.g. repo:living/livy-memory-bot)
        role:     relationship role from RELATIONSHIP_ROLES
        source:   source record dict with source_type, source_ref, retrieved_at, mapper_version
        lineage_run_id:  run identifier for audit trail

    Optional:
        since:   ISO timestamp of first observed participation
        until:   ISO timestamp when participation ended (None = still active)
        window_days:  query window used to generate this edge
        confidence:  confidence level (default: high)
    """
    if role not in RELATIONSHIP_ROLES:
        raise ValueError(f"role must be one of {RELATIONSHIP_ROLES!r}, got {role!r}")

    _validate_source(source)

    # Embed source record as-is for traceability.
    sources = [dict(source)]

    edge: dict[str, Any] = {
        "from_id": from_id,
        "to_id": to_id,
        "role": role,
        "confidence": confidence,
        "sources": sources,
        "lineage_run_id": lineage_run_id,
        "until": until,
    }

    if since is not None:
        edge["since"] = since
    if window_days is not None:
        edge["window_days"] = window_days

    return edge


# ---------------------------------------------------------------------------
# Person -> Repo edges
# ---------------------------------------------------------------------------

def build_pr_author_edge(
    person_id: str,
    repo_id: str,
    since: str,
    source: dict,
    lineage_run_id: str,
    window_days: int | None = None,
) -> dict:
    """Build a person -> repo edge with role=author.

    This represents a PR author's relationship to a repository.
    """
    return _build_edge(
        from_id=person_id,
        to_id=repo_id,
        role="author",
        source=source,
        lineage_run_id=lineage_run_id,
        since=since,
        until=None,
        window_days=window_days,
    )


def build_reviewer_edge(
    person_id: str,
    repo_id: str,
    since: str,
    source: dict,
    lineage_run_id: str,
    window_days: int | None = None,
) -> dict:
    """Build a person -> repo edge with role=reviewer."""
    return _build_edge(
        from_id=person_id,
        to_id=repo_id,
        role="reviewer",
        source=source,
        lineage_run_id=lineage_run_id,
        since=since,
        until=None,
        window_days=window_days,
    )


def build_commenter_edge(
    person_id: str,
    repo_id: str,
    since: str,
    source: dict,
    lineage_run_id: str,
    window_days: int | None = None,
) -> dict:
    """Build a person -> repo edge with role=commenter."""
    return _build_edge(
        from_id=person_id,
        to_id=repo_id,
        role="commenter",
        source=source,
        lineage_run_id=lineage_run_id,
        since=since,
        until=None,
        window_days=window_days,
    )


# ---------------------------------------------------------------------------
# Repo -> Project edges
# ---------------------------------------------------------------------------

def build_repo_project_edge(
    repo_id: str,
    project_id: str,
    source: dict,
    lineage_run_id: str,
    window_days: int | None = None,
) -> dict:
    """Build a repo -> project edge with role=participant."""
    return _build_edge(
        from_id=repo_id,
        to_id=project_id,
        role="participant",
        source=source,
        lineage_run_id=lineage_run_id,
        since=None,
        until=None,
        window_days=window_days,
    )


# ---------------------------------------------------------------------------
# Inferred person -> project edges via repo participation
# ---------------------------------------------------------------------------

def build_person_project_inference_edges(
    person_id: str,
    person_repos: list[tuple[str, str]],
    repo_project_map: dict[str, str],
    source: dict,
    lineage_run_id: str,
    window_days: int | None = None,
) -> list[dict]:
    """Build inferred person -> project edges by joining repo participation.

    For each (repo_id, since) in person_repos, if repo_id has a mapping
    in repo_project_map, emit a person -> project edge with role=participant.

    The since date on each edge reflects the earliest participation in that repo.

    Args:
        person_id:       id_canonical of the person
        person_repos:    list of (repo_id, since_iso) tuples — repos the person
                         has participated in and when
        repo_project_map: mapping from repo_id to project_id
        source:          source record for traceability
        lineage_run_id:  run identifier for audit trail
        window_days:     optional query window hint

    Returns:
        List of relationship edges (may be empty if no repo has a project mapping).
    """
    edges: list[dict] = []

    for repo_id, since in person_repos:
        project_id = repo_project_map.get(repo_id)
        if project_id is None:
            # Skip repos that have no project mapping.
            continue

        edge = _build_edge(
            from_id=person_id,
            to_id=project_id,
            role="participant",
            source=source,
            lineage_run_id=lineage_run_id,
            since=since,
            until=None,
            window_days=window_days,
        )
        edges.append(edge)

    return edges


# ---------------------------------------------------------------------------
# Query-origin metadata helper
# ---------------------------------------------------------------------------

def build_window_origin_hint(
    window_days: int,
    date_mode: str = "merged_at",
) -> dict:
    """Build query-origin metadata dict for window context.

    Args:
        window_days:  number of days in the query window
        date_mode:    date selection mode — 'merged_at' or 'created_at'

    Returns:
        Metadata dict with window_days and date_mode.
    """
    return {
        "window_days": window_days,
        "date_mode": date_mode,
    }
