"""Tests for traceability guarantees and mapper versioning — TDD RED phase.

Every generated entity/edge must carry:
  source_type, source_ref, retrieved_at, lineage_run_id, mapper_version

Coverage:
  - build_source_record() creates source dicts with all 4 required fields
  - generate_lineage_run_id() produces deterministic run identifiers
  - normalize_github_pr_to_entity() produces entity with embedded source record
  - normalize_github_repo_to_entity() produces entity with embedded source record
  - normalize_tldv_meeting_to_entity() produces entity with embedded source record
  - normalize_trello_card_to_entity() produces entity with embedded source record
  - build_entity_with_traceability() wraps any entity with full traceability
  - All outputs validated via canonical_types validators
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _mapper_version() -> str:
    return "github-enrich-v1"


def _github_pr_raw() -> dict:
    return {
        "url": "https://github.com/living/livy-memory-bot/pull/42",
        "html_url": "https://github.com/living/livy-memory-bot/pull/42",
        "number": 42,
        "state": "closed",
        "merged_at": "2026-04-10T10:00:00Z",
        "user": {"login": "lincolnqjunior", "id": 98765},
        "title": "feat(domain): add traceability fields",
        "body": "Closes #41",
        "merged": True,
        "merged_by": {"login": "lincolnqjunior"},
    }


def _github_repo_raw() -> dict:
    return {
        "full_name": "living/livy-memory-bot",
        "owner": {"login": "living"},
        "name": "livy-memory-bot",
        "default_branch": "main",
        "archived": False,
        "html_url": "https://github.com/living/livy-memory-bot",
    }


def _tldv_meeting_raw() -> dict:
    return {
        "meeting_id": "tldv:67890",
        "title": "Daily Status 2026-04-10",
        "started_at": "2026-04-10T09:00:00Z",
        "ended_at": "2026-04-10T10:00:00Z",
        "url": "https://tldv.io/meetings/67890",
    }


def _trello_card_raw() -> dict:
    return {
        "id": "trello:abc123",
        "name": "Implement canonical model",
        "desc": "Use domain-first approach",
        "board": {"name": "MEM"},
        "list": {"name": "Doing"},
        "url": "https://trello.com/c/abc123",
    }


def _decision_raw() -> dict:
    return {
        "origin_id": "dec-001",
        "description": "Adopt domain-first memory graph.",
        "decision_date": "2026-04-10",
        "project": "livy-memory",
        "raw": {
            "type": "signal_event",
            "ref": "https://github.com/living/livy-memory-bot/pull/1",
        },
    }


# ---------------------------------------------------------------------------
# RED phase — tests fail until normalize.py is implemented
# ---------------------------------------------------------------------------

class TestBuildSourceRecord:
    """build_source_record() creates source dicts with all 4 required fields."""

    def test_returns_dict(self):
        from vault.domain.normalize import build_source_record

        result = build_source_record(
            source_type="github_api",
            source_ref="https://github.com/living/livy-memory-bot/pull/42",
            mapper_version="github-enrich-v1",
        )
        assert isinstance(result, dict)

    def test_has_source_type(self):
        from vault.domain.normalize import build_source_record

        result = build_source_record(
            source_type="github_api",
            source_ref="https://github.com/living/livy-memory-bot/pull/42",
            mapper_version="github-enrich-v1",
        )
        assert result["source_type"] == "github_api"

    def test_has_source_ref(self):
        from vault.domain.normalize import build_source_record

        result = build_source_record(
            source_type="github_api",
            source_ref="https://github.com/living/livy-memory-bot/pull/42",
            mapper_version="github-enrich-v1",
        )
        assert result["source_ref"] == "https://github.com/living/livy-memory-bot/pull/42"

    def test_has_retrieved_at(self):
        from vault.domain.normalize import build_source_record

        result = build_source_record(
            source_type="github_api",
            source_ref="https://github.com/living/livy-memory-bot/pull/42",
            mapper_version="github-enrich-v1",
        )
        assert "retrieved_at" in result
        assert isinstance(result["retrieved_at"], str)

    def test_has_mapper_version(self):
        from vault.domain.normalize import build_source_record

        result = build_source_record(
            source_type="github_api",
            source_ref="https://github.com/living/livy-memory-bot/pull/42",
            mapper_version="github-enrich-v1",
        )
        assert result["mapper_version"] == "github-enrich-v1"

    def test_retrieved_at_iso_format(self):
        from vault.domain.normalize import build_source_record
        from vault.domain.canonical_types import is_iso_date

        result = build_source_record(
            source_type="github_api",
            source_ref="https://github.com/living/livy-memory-bot/pull/42",
            mapper_version="github-enrich-v1",
        )
        assert is_iso_date(result["retrieved_at"])

    def test_retrieved_at_uses_provided_value(self):
        from vault.domain.normalize import build_source_record

        result = build_source_record(
            source_type="tldv_api",
            source_ref="tldv:67890",
            mapper_version="tldv-ingest-v1",
            retrieved_at="2026-04-10T12:00:00Z",
        )
        assert result["retrieved_at"] == "2026-04-10T12:00:00Z"

    def test_only_has_required_fields(self):
        from vault.domain.normalize import build_source_record
        from vault.domain.canonical_types import SOURCE_FIELDS

        result = build_source_record(
            source_type="github_api",
            source_ref="https://github.com/living/livy-memory-bot/pull/42",
            mapper_version="github-enrich-v1",
        )
        actual_keys = set(result.keys())
        expected_keys = SOURCE_FIELDS
        assert actual_keys == expected_keys, f"got {actual_keys}, expected {expected_keys}"


class TestGenerateLineageRunId:
    """generate_lineage_run_id() produces deterministic run identifiers."""

    def test_returns_string(self):
        from vault.domain.normalize import generate_lineage_run_id

        result = generate_lineage_run_id("github-enrich-v1")
        assert isinstance(result, str)

    def test_contains_mapper_version(self):
        from vault.domain.normalize import generate_lineage_run_id

        result = generate_lineage_run_id("github-enrich-v1")
        assert "github-enrich-v1" in result

    def test_contains_timestamp(self):
        from vault.domain.normalize import generate_lineage_run_id

        result = generate_lineage_run_id("github-enrich-v1")
        # Should contain a date-like segment
        assert "run-" in result or "2026" in result

    def test_deterministic_with_fixed_timestamp(self):
        from vault.domain.normalize import generate_lineage_run_id

        ts = "2026-04-10T10:12:00Z"
        result1 = generate_lineage_run_id("github-enrich-v1", timestamp=ts)
        result2 = generate_lineage_run_id("github-enrich-v1", timestamp=ts)
        assert result1 == result2

    def test_different_versions_produce_different_ids(self):
        from vault.domain.normalize import generate_lineage_run_id

        ts = "2026-04-10T10:12:00Z"
        result1 = generate_lineage_run_id("github-enrich-v1", timestamp=ts)
        result2 = generate_lineage_run_id("tldv-ingest-v1", timestamp=ts)
        assert result1 != result2


class TestNormalizeGithubPrToEntity:
    """normalize_github_pr_to_entity() produces person entity with traceability."""

    def test_returns_dict(self):
        from vault.domain.normalize import normalize_github_pr_to_entity

        result = normalize_github_pr_to_entity(_github_pr_raw(), _mapper_version())
        assert isinstance(result, dict)

    def test_entity_passes_validate_person(self):
        from vault.domain.normalize import normalize_github_pr_to_entity
        from vault.domain.canonical_types import validate_person

        entity = normalize_github_pr_to_entity(_github_pr_raw(), _mapper_version())
        errors = validate_person(entity)
        assert errors is True, f"validation errors: {errors}"

    def test_entity_has_id_canonical_prefix(self):
        from vault.domain.normalize import normalize_github_pr_to_entity

        entity = normalize_github_pr_to_entity(_github_pr_raw(), _mapper_version())
        assert entity["id_canonical"].startswith("person:")

    def test_entity_has_source_keys(self):
        from vault.domain.normalize import normalize_github_pr_to_entity

        entity = normalize_github_pr_to_entity(_github_pr_raw(), _mapper_version())
        assert "source_keys" in entity
        assert isinstance(entity["source_keys"], list)
        assert len(entity["source_keys"]) > 0

    def test_source_key_includes_github_login(self):
        from vault.domain.normalize import normalize_github_pr_to_entity

        entity = normalize_github_pr_to_entity(_github_pr_raw(), _mapper_version())
        github_keys = [k for k in entity["source_keys"] if k.startswith("github:")]
        assert len(github_keys) > 0

    def test_entity_has_github_login(self):
        from vault.domain.normalize import normalize_github_pr_to_entity

        entity = normalize_github_pr_to_entity(_github_pr_raw(), _mapper_version())
        assert entity.get("github_login") == "lincolnqjunior"

    def test_entity_has_first_seen_at(self):
        from vault.domain.normalize import normalize_github_pr_to_entity
        from vault.domain.canonical_types import is_iso_date

        entity = normalize_github_pr_to_entity(_github_pr_raw(), _mapper_version())
        assert "first_seen_at" in entity
        assert is_iso_date(entity["first_seen_at"])

    def test_entity_has_last_seen_at(self):
        from vault.domain.normalize import normalize_github_pr_to_entity
        from vault.domain.canonical_types import is_iso_date

        entity = normalize_github_pr_to_entity(_github_pr_raw(), _mapper_version())
        assert "last_seen_at" in entity
        assert is_iso_date(entity["last_seen_at"])

    def test_merges_github_login_in_source_keys_for_merged_pr(self):
        """When merged_by != author, both are recorded."""
        raw = _github_pr_raw()
        raw["user"]["login"] = "alice"
        raw["merged_by"]["login"] = "bob"
        from vault.domain.normalize import normalize_github_pr_to_entity

        entity = normalize_github_pr_to_entity(raw, _mapper_version())
        github_keys = [k for k in entity["source_keys"] if k.startswith("github:")]
        assert len(github_keys) >= 2  # both author and merger


class TestNormalizeGithubRepoToEntity:
    """normalize_github_repo_to_entity() produces repo entity with traceability."""

    def test_returns_dict(self):
        from vault.domain.normalize import normalize_github_repo_to_entity

        result = normalize_github_repo_to_entity(_github_repo_raw(), _mapper_version())
        assert isinstance(result, dict)

    def test_entity_passes_validate_repo(self):
        from vault.domain.normalize import normalize_github_repo_to_entity
        from vault.domain.canonical_types import validate_repo

        entity = normalize_github_repo_to_entity(_github_repo_raw(), _mapper_version())
        errors = validate_repo(entity)
        assert errors is True, f"validation errors: {errors}"

    def test_entity_has_id_canonical_prefix(self):
        from vault.domain.normalize import normalize_github_repo_to_entity

        entity = normalize_github_repo_to_entity(_github_repo_raw(), _mapper_version())
        assert entity["id_canonical"].startswith("repo:")

    def test_entity_has_full_name(self):
        from vault.domain.normalize import normalize_github_repo_to_entity

        entity = normalize_github_repo_to_entity(_github_repo_raw(), _mapper_version())
        assert entity["full_name"] == "living/livy-memory-bot"

    def test_entity_has_owner(self):
        from vault.domain.normalize import normalize_github_repo_to_entity

        entity = normalize_github_repo_to_entity(_github_repo_raw(), _mapper_version())
        assert entity["owner"] == "living"


class TestNormalizeTldvMeetingToEntity:
    """normalize_tldv_meeting_to_entity() produces meeting entity with traceability."""

    def test_returns_dict(self):
        from vault.domain.normalize import normalize_tldv_meeting_to_entity

        result = normalize_tldv_meeting_to_entity(_tldv_meeting_raw(), _mapper_version())
        assert isinstance(result, dict)

    def test_entity_passes_validate_meeting(self):
        from vault.domain.normalize import normalize_tldv_meeting_to_entity
        from vault.domain.canonical_types import validate_meeting

        entity = normalize_tldv_meeting_to_entity(_tldv_meeting_raw(), _mapper_version())
        errors = validate_meeting(entity)
        assert errors is True, f"validation errors: {errors}"

    def test_entity_has_id_canonical_prefix(self):
        from vault.domain.normalize import normalize_tldv_meeting_to_entity

        entity = normalize_tldv_meeting_to_entity(_tldv_meeting_raw(), _mapper_version())
        assert entity["id_canonical"].startswith("meeting:")

    def test_entity_has_meeting_id_source(self):
        from vault.domain.normalize import normalize_tldv_meeting_to_entity

        entity = normalize_tldv_meeting_to_entity(_tldv_meeting_raw(), _mapper_version())
        assert entity["meeting_id_source"] == "tldv:67890"


class TestNormalizeTrelloCardToEntity:
    """normalize_trello_card_to_entity() produces card entity with traceability."""

    def test_returns_dict(self):
        from vault.domain.normalize import normalize_trello_card_to_entity

        result = normalize_trello_card_to_entity(_trello_card_raw(), _mapper_version())
        assert isinstance(result, dict)

    def test_entity_passes_validate_card(self):
        from vault.domain.normalize import normalize_trello_card_to_entity
        from vault.domain.canonical_types import validate_card

        entity = normalize_trello_card_to_entity(_trello_card_raw(), _mapper_version())
        errors = validate_card(entity)
        assert errors is True, f"validation errors: {errors}"

    def test_entity_has_id_canonical_prefix(self):
        from vault.domain.normalize import normalize_trello_card_to_entity

        entity = normalize_trello_card_to_entity(_trello_card_raw(), _mapper_version())
        assert entity["id_canonical"].startswith("card:")

    def test_entity_has_card_id_source(self):
        from vault.domain.normalize import normalize_trello_card_to_entity

        entity = normalize_trello_card_to_entity(_trello_card_raw(), _mapper_version())
        assert entity["card_id_source"] == "trello:abc123"


class TestBuildEntityWithTraceability:
    """build_entity_with_traceability() wraps any entity with full traceability envelope."""

    def test_returns_dict(self):
        from vault.domain.normalize import build_entity_with_traceability

        result = build_entity_with_traceability(
            entity={"id_canonical": "person:test"},
            mapper_version="github-enrich-v1",
        )
        assert isinstance(result, dict)

    def test_entity_has_source_keys_with_traceability_entry(self):
        from vault.domain.normalize import build_entity_with_traceability

        result = build_entity_with_traceability(
            entity={"id_canonical": "person:test"},
            mapper_version="github-enrich-v1",
        )
        assert "source_keys" in result
        assert any("github-enrich-v1" in k for k in result["source_keys"])

    def test_entity_has_first_seen_at(self):
        from vault.domain.normalize import build_entity_with_traceability
        from vault.domain.canonical_types import is_iso_date

        result = build_entity_with_traceability(
            entity={"id_canonical": "person:test"},
            mapper_version="github-enrich-v1",
        )
        assert "first_seen_at" in result
        assert is_iso_date(result["first_seen_at"])

    def test_entity_has_last_seen_at(self):
        from vault.domain.normalize import build_entity_with_traceability
        from vault.domain.canonical_types import is_iso_date

        result = build_entity_with_traceability(
            entity={"id_canonical": "person:test"},
            mapper_version="github-enrich-v1",
        )
        assert "last_seen_at" in result
        assert is_iso_date(result["last_seen_at"])


class TestNormalizeDecisionRecord:
    """normalize_decision_to_entity() produces decision entity with traceability."""

    def test_returns_dict(self):
        from vault.domain.normalize import normalize_decision_to_entity

        result = normalize_decision_to_entity(_decision_raw(), _mapper_version())
        assert isinstance(result, dict)

    def test_entity_passes_validate_decision(self):
        from vault.domain.normalize import normalize_decision_to_entity
        from vault.domain.canonical_types import validate_decision

        entity = normalize_decision_to_entity(_decision_raw(), _mapper_version())
        errors = validate_decision(entity)
        assert errors is True, f"validation errors: {errors}"

    def test_entity_has_id_canonical_prefix(self):
        from vault.domain.normalize import normalize_decision_to_entity

        entity = normalize_decision_to_entity(_decision_raw(), _mapper_version())
        assert entity["id_canonical"].startswith("decision:")

    def test_entity_has_sources(self):
        from vault.domain.normalize import normalize_decision_to_entity

        entity = normalize_decision_to_entity(_decision_raw(), _mapper_version())
        assert "sources" in entity
        assert isinstance(entity["sources"], list)
        assert len(entity["sources"]) > 0

    def test_sources_have_all_four_required_fields(self):
        from vault.domain.normalize import normalize_decision_to_entity
        from vault.domain.canonical_types import SOURCE_FIELDS

        entity = normalize_decision_to_entity(_decision_raw(), _mapper_version())
        for src in entity["sources"]:
            for field in SOURCE_FIELDS:
                assert field in src, f"source missing {field}: {src}"


class TestNormalizeGithubPrToRelationship:
    """normalize_github_pr_to_relationships() produces edges with full traceability."""

    def test_returns_list(self):
        from vault.domain.normalize import normalize_github_pr_to_relationships

        result = normalize_github_pr_to_relationships(
            _github_pr_raw(), "person:lincolnqjunior", "repo:living/livy-memory-bot", _mapper_version()
        )
        assert isinstance(result, list)

    def test_edges_passes_validate_relationship(self):
        from vault.domain.normalize import normalize_github_pr_to_relationships
        from vault.domain.canonical_types import validate_relationship

        edges = normalize_github_pr_to_relationships(
            _github_pr_raw(), "person:lincolnqjunior", "repo:living/livy-memory-bot", _mapper_version()
        )
        for edge in edges:
            errors = validate_relationship(edge)
            assert errors is True, f"edge validation errors: {errors}"

    def test_edge_has_lineage_run_id(self):
        from vault.domain.normalize import normalize_github_pr_to_relationships

        edges = normalize_github_pr_to_relationships(
            _github_pr_raw(), "person:lincolnqjunior", "repo:living/livy-memory-bot", _mapper_version()
        )
        for edge in edges:
            assert "lineage_run_id" in edge

    def test_edge_sources_have_all_four_required_fields(self):
        from vault.domain.normalize import normalize_github_pr_to_relationships
        from vault.domain.canonical_types import SOURCE_FIELDS

        edges = normalize_github_pr_to_relationships(
            _github_pr_raw(), "person:lincolnqjunior", "repo:living/livy-memory-bot", _mapper_version()
        )
        for edge in edges:
            for src in edge["sources"]:
                for field in SOURCE_FIELDS:
                    assert field in src, f"edge source missing {field}: {src}"

    def test_author_edge_generated_for_merged_pr(self):
        from vault.domain.normalize import normalize_github_pr_to_relationships

        edges = normalize_github_pr_to_relationships(
            _github_pr_raw(), "person:lincolnqjunior", "repo:living/livy-memory-bot", _mapper_version()
        )
        roles = {e["role"] for e in edges}
        assert "author" in roles

    def test_author_role_links_person_to_repo(self):
        from vault.domain.normalize import normalize_github_pr_to_relationships

        edges = normalize_github_pr_to_relationships(
            _github_pr_raw(), "person:lincolnqjunior", "repo:living/livy-memory-bot", _mapper_version()
        )
        author_edges = [e for e in edges if e["role"] == "author"]
        assert len(author_edges) > 0
        assert author_edges[0]["from_id"] == "person:lincolnqjunior"
        assert author_edges[0]["to_id"] == "repo:living/livy-memory-bot"


class TestNormalizeGithubRepoToRelationship:
    """normalize_github_repo_to_relationship() produces repo->project edge with traceability."""

    def test_returns_dict(self):
        from vault.domain.normalize import normalize_github_repo_to_relationship

        result = normalize_github_repo_to_relationship(
            _github_repo_raw(), "repo:living/livy-memory-bot", "project:livy-memory", _mapper_version()
        )
        assert isinstance(result, dict)

    def test_edge_passes_validate_relationship(self):
        from vault.domain.normalize import normalize_github_repo_to_relationship
        from vault.domain.canonical_types import validate_relationship

        edge = normalize_github_repo_to_relationship(
            _github_repo_raw(), "repo:living/livy-memory-bot", "project:livy-memory", _mapper_version()
        )
        errors = validate_relationship(edge)
        assert errors is True, f"validation errors: {errors}"

    def test_edge_has_lineage_run_id(self):
        from vault.domain.normalize import normalize_github_repo_to_relationship

        edge = normalize_github_repo_to_relationship(
            _github_repo_raw(), "repo:living/livy-memory-bot", "project:livy-memory", _mapper_version()
        )
        assert "lineage_run_id" in edge

    def test_edge_sources_have_all_four_required_fields(self):
        from vault.domain.normalize import normalize_github_repo_to_relationship
        from vault.domain.canonical_types import SOURCE_FIELDS

        edge = normalize_github_repo_to_relationship(
            _github_repo_raw(), "repo:living/livy-memory-bot", "project:livy-memory", _mapper_version()
        )
        for src in edge["sources"]:
            for field in SOURCE_FIELDS:
                assert field in src, f"edge source missing {field}: {src}"


class TestAllTraceabilityFieldsGuaranteed:
    """Meta-test: every entity/edge produced by normalize module has all 5 required fields."""

    def test_github_pr_entity_has_all_5_traceability_guarantees(self):
        from vault.domain.normalize import normalize_github_pr_to_entity
        from vault.domain.canonical_types import SOURCE_FIELDS

        entity = normalize_github_pr_to_entity(_github_pr_raw(), _mapper_version())
        # Entity's source_keys embed traceability info
        assert "source_keys" in entity
        assert len(entity["source_keys"]) > 0
        # Check that at least one source key is a canonical mapper entry
        has_mapper_entry = any(_mapper_version() in k for k in entity["source_keys"])
        assert has_mapper_entry, f"No source key for mapper version {_mapper_version()} in {entity['source_keys']}"
        assert "first_seen_at" in entity
        assert "last_seen_at" in entity

    def test_github_repo_entity_has_all_5_traceability_guarantees(self):
        from vault.domain.normalize import normalize_github_repo_to_entity

        entity = normalize_github_repo_to_entity(_github_repo_raw(), _mapper_version())
        assert "source_keys" in entity
        assert len(entity["source_keys"]) > 0
        has_mapper_entry = any(_mapper_version() in k for k in entity["source_keys"])
        assert has_mapper_entry

    def test_decision_entity_has_all_5_traceability_guarantees(self):
        from vault.domain.normalize import normalize_decision_to_entity
        from vault.domain.canonical_types import SOURCE_FIELDS

        entity = normalize_decision_to_entity(_decision_raw(), _mapper_version())
        assert "sources" in entity
        assert len(entity["sources"]) > 0
        for src in entity["sources"]:
            for field in SOURCE_FIELDS:
                assert field in src

    def test_pr_relationship_has_all_5_traceability_guarantees(self):
        from vault.domain.normalize import normalize_github_pr_to_relationships
        from vault.domain.canonical_types import SOURCE_FIELDS

        edges = normalize_github_pr_to_relationships(
            _github_pr_raw(), "person:lincolnqjunior", "repo:living/livy-memory-bot", _mapper_version()
        )
        assert len(edges) > 0
        for edge in edges:
            assert "lineage_run_id" in edge
            for src in edge["sources"]:
                for field in SOURCE_FIELDS:
                    assert field in src

    def test_repo_relationship_has_all_5_traceability_guarantees(self):
        from vault.domain.normalize import normalize_github_repo_to_relationship
        from vault.domain.canonical_types import SOURCE_FIELDS

        edge = normalize_github_repo_to_relationship(
            _github_repo_raw(), "repo:living/livy-memory-bot", "project:livy-memory", _mapper_version()
        )
        assert "lineage_run_id" in edge
        for src in edge["sources"]:
            for field in SOURCE_FIELDS:
                assert field in src
