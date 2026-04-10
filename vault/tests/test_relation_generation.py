"""Tests for relationship builder — TDD RED phase.

Cases covered:
- PR author => person -> repo role=author
- reviewer/commenter => corresponding role edges
- repo/project mapping => repo -> project
- inferred person -> project via repo participation
- window_days stored as query-origin hint
- traceability fields in every generated edge
"""
from __future__ import annotations

import pytest

from vault.domain.relationship_builder import (
    build_pr_author_edge,
    build_reviewer_edge,
    build_commenter_edge,
    build_repo_project_edge,
    build_person_project_inference_edges,
    build_window_origin_hint,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _source() -> dict:
    return {
        "source_type": "github_api",
        "source_ref": "https://github.com/living/livy-memory-bot/pull/42",
        "retrieved_at": "2026-04-10T10:12:00Z",
        "mapper_version": "github-enrich-v1",
    }


# ---------------------------------------------------------------------------
# RED phase — tests should fail until builder is implemented
# ---------------------------------------------------------------------------

class TestBuildPrAuthorEdge:
    """PR author creates person -> repo edge with role=author."""

    def test_returns_dict(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert isinstance(result, dict)

    def test_from_is_person(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["from_id"] == "person:lincolnq"

    def test_to_is_repo(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["to_id"] == "repo:living/livy-memory-bot"

    def test_role_is_author(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["role"] == "author"

    def test_since_passthrough(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["since"] == "2026-04-01T00:00:00Z"

    def test_until_is_none(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["until"] is None

    def test_includes_source_record(self):
        source = _source()
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=source,
            lineage_run_id="run-2026-04-10",
        )
        assert "sources" in result
        assert result["sources"][0]["source_type"] == "github_api"
        assert result["sources"][0]["source_ref"] == source["source_ref"]

    def test_includes_lineage_run_id(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["lineage_run_id"] == "run-2026-04-10"


class TestBuildReviewerEdge:
    """Reviewer creates person -> repo edge with role=reviewer."""

    def test_role_is_reviewer(self):
        result = build_reviewer_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["role"] == "reviewer"

    def test_from_to_fields_set(self):
        result = build_reviewer_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["from_id"] == "person:lincolnq"
        assert result["to_id"] == "repo:living/livy-memory-bot"


class TestBuildCommenterEdge:
    """Commenter creates person -> repo edge with role=commenter."""

    def test_role_is_commenter(self):
        result = build_commenter_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["role"] == "commenter"

    def test_from_to_fields_set(self):
        result = build_commenter_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["from_id"] == "person:lincolnq"
        assert result["to_id"] == "repo:living/livy-memory-bot"


class TestBuildRepoProjectEdge:
    """Repo -> Project mapping edge."""

    def test_from_is_repo(self):
        result = build_repo_project_edge(
            repo_id="repo:living/livy-memory-bot",
            project_id="project:livy-memory",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["from_id"] == "repo:living/livy-memory-bot"

    def test_to_is_project(self):
        result = build_repo_project_edge(
            repo_id="repo:living/livy-memory-bot",
            project_id="project:livy-memory",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["to_id"] == "project:livy-memory"

    def test_role_is_participant(self):
        result = build_repo_project_edge(
            repo_id="repo:living/livy-memory-bot",
            project_id="project:livy-memory",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert result["role"] == "participant"


class TestBuildPersonProjectInference:
    """Inferred person -> project edges via repo participation."""

    def test_returns_list_of_edges(self):
        person_repos = [
            ("repo:living/livy-memory-bot", "2026-04-01T00:00:00Z"),
            ("repo:living/livy-bat-jobs", "2026-04-02T00:00:00Z"),
        ]
        repo_project_map = {
            "repo:living/livy-memory-bot": "project:livy-memory",
            "repo:living/livy-bat-jobs": "project:bat",
        }
        edges = build_person_project_inference_edges(
            person_id="person:lincolnq",
            person_repos=person_repos,
            repo_project_map=repo_project_map,
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert isinstance(edges, list)
        assert len(edges) == 2

    def test_each_edge_is_person_to_project(self):
        person_repos = [
            ("repo:living/livy-memory-bot", "2026-04-01T00:00:00Z"),
        ]
        repo_project_map = {
            "repo:living/livy-memory-bot": "project:livy-memory",
        }
        edges = build_person_project_inference_edges(
            person_id="person:lincolnq",
            person_repos=person_repos,
            repo_project_map=repo_project_map,
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        edge = edges[0]
        assert edge["from_id"] == "person:lincolnq"
        assert edge["to_id"] == "project:livy-memory"
        assert edge["role"] == "participant"

    def test_respects_since_from_earliest_repo_participation(self):
        person_repos = [
            ("repo:living/livy-memory-bot", "2026-04-01T00:00:00Z"),
            ("repo:living/livy-bat-jobs", "2026-04-15T00:00:00Z"),
        ]
        repo_project_map = {
            "repo:living/livy-memory-bot": "project:livy-memory",
            "repo:living/livy-bat-jobs": "project:bat",
        }
        edges = build_person_project_inference_edges(
            person_id="person:lincolnq",
            person_repos=person_repos,
            repo_project_map=repo_project_map,
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        # Should have 2 edges, one per project
        assert len(edges) == 2
        # Each edge should have a since date (earliest for that project)
        for edge in edges:
            assert "since" in edge

    def test_skips_repo_without_project_mapping(self):
        person_repos = [
            ("repo:living/livy-memory-bot", "2026-04-01T00:00:00Z"),
            ("repo:unknown/unknown", "2026-04-05T00:00:00Z"),
        ]
        repo_project_map = {
            "repo:living/livy-memory-bot": "project:livy-memory",
        }
        edges = build_person_project_inference_edges(
            person_id="person:lincolnq",
            person_repos=person_repos,
            repo_project_map=repo_project_map,
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert len(edges) == 1
        assert edges[0]["to_id"] == "project:livy-memory"


class TestWindowDaysOriginHint:
    """window_days stored as query-origin metadata on edge."""

    def test_window_days_included_in_edge(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
            window_days=30,
        )
        assert result.get("window_days") == 30

    def test_window_days_not_required(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        # Should not raise — window_days is optional
        assert "window_days" not in result or result.get("window_days") is None

    def test_build_window_origin_hint_creates_metadata(self):
        meta = build_window_origin_hint(window_days=90, date_mode="merged_at")
        assert meta["window_days"] == 90
        assert meta["date_mode"] == "merged_at"


class TestTraceabilityFields:
    """Every generated edge must carry full traceability stamp."""

    def test_edge_has_sources(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert "sources" in result

    def test_edge_has_lineage_run_id(self):
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        assert "lineage_run_id" in result

    def test_source_record_has_required_fields(self):
        source = _source()
        result = build_pr_author_edge(
            person_id="person:lincolnq",
            repo_id="repo:living/livy-memory-bot",
            since="2026-04-01T00:00:00Z",
            source=source,
            lineage_run_id="run-2026-04-10",
        )
        src = result["sources"][0]
        assert "source_type" in src
        assert "source_ref" in src
        assert "retrieved_at" in src
        assert "mapper_version" in src

    def test_inference_edges_have_sources_and_lineage(self):
        person_repos = [
            ("repo:living/livy-memory-bot", "2026-04-01T00:00:00Z"),
        ]
        repo_project_map = {
            "repo:living/livy-memory-bot": "project:livy-memory",
        }
        edges = build_person_project_inference_edges(
            person_id="person:lincolnq",
            person_repos=person_repos,
            repo_project_map=repo_project_map,
            source=_source(),
            lineage_run_id="run-2026-04-10",
        )
        edge = edges[0]
        assert "sources" in edge
        assert "lineage_run_id" in edge
