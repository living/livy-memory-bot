"""Tests for canonical domain contract validators aligned 1:1 with final spec."""
from __future__ import annotations


def _source() -> dict:
    return {
        "source_type": "github_api",
        "source_ref": "https://github.com/living/livy-memory-bot/pull/10",
        "retrieved_at": "2026-04-10T10:12:00Z",
        "mapper_version": "github-enrich-v1",
    }


def minimal_person() -> dict:
    return {
        "id_canonical": "person:lincolnqjunior",
        "display_name": "Lincoln Quinan Junior",
        "github_login": "lincolnqjunior",
        "email": "lincoln@livingnet.com.br",
        "source_keys": ["github:lincolnqjunior", "tldv:email:lincoln@livingnet.com.br"],
        "first_seen_at": "2026-03-01T10:00:00Z",
        "last_seen_at": "2026-04-10T10:00:00Z",
        "confidence": "high",
    }


def minimal_project() -> dict:
    return {
        "id_canonical": "project:livy-memory",
        "slug": "livy-memory",
        "name": "Livy Memory",
        "status": "active",
        "aliases": ["Livy"],
        "confidence": "medium",
    }


def minimal_repo() -> dict:
    return {
        "id_canonical": "repo:living/livy-memory-bot",
        "full_name": "living/livy-memory-bot",
        "owner": "living",
        "name": "livy-memory-bot",
        "default_branch": "main",
        "archived": False,
        "project_ref": "project:livy-memory",
    }


def minimal_meeting() -> dict:
    return {
        "id_canonical": "meeting:tldv-12345",
        "meeting_id_source": "tldv:12345",
        "title": "Daily Status",
        "started_at": "2026-04-10T09:00:00Z",
        "ended_at": "2026-04-10T10:00:00Z",
        "project_ref": "project:livy-memory",
    }


def minimal_card() -> dict:
    return {
        "id_canonical": "card:trello-abc123",
        "card_id_source": "trello:abc123",
        "title": "Implement canonical model",
        "board": "MEM",
        "list": "Doing",
        "project_ref": "project:livy-memory",
        "status": "in_progress",
    }


def minimal_decision() -> dict:
    return {
        "id_canonical": "decision:arch-001",
        "summary": "Adopt domain-first memory graph.",
        "decision_date": "2026-04-10",
        "project_ref": "project:livy-memory",
        "confidence": "high",
        "sources": [_source()],
        "last_verified": "2026-04-10",
    }


def minimal_relationship() -> dict:
    return {
        "from_id": "person:lincolnqjunior",
        "to_id": "repo:living/livy-memory-bot",
        "role": "author",
        "since": "2026-04-01T00:00:00Z",
        "until": None,
        "window_days": 30,
        "confidence": "high",
        "sources": [_source()],
        "lineage_run_id": "run-2026-04-10T10:12:00Z-github-enrich-v1",
    }


def test_module_imports():
    import vault.domain.canonical_types as ct  # noqa: F401


class TestPerson:
    def test_valid_person(self):
        from vault.domain.canonical_types import validate_person

        assert validate_person(minimal_person()) is True

    def test_person_requires_source_keys(self):
        from vault.domain.canonical_types import validate_person

        entity = minimal_person()
        entity.pop("source_keys")
        errors = validate_person(entity)
        assert "source_keys" in errors

    def test_person_rejects_legacy_name_field(self):
        from vault.domain.canonical_types import validate_person

        entity = minimal_person()
        entity.pop("display_name")
        entity["name"] = "Legacy"
        errors = validate_person(entity)
        assert "unknown_field:name" in errors

    def test_person_confidence_enum(self):
        from vault.domain.canonical_types import validate_person

        entity = minimal_person()
        entity["confidence"] = "super-high"
        errors = validate_person(entity)
        assert "confidence_allowed" in errors


class TestProject:
    def test_valid_project(self):
        from vault.domain.canonical_types import validate_project

        assert validate_project(minimal_project()) is True

    def test_project_requires_slug(self):
        from vault.domain.canonical_types import validate_project

        entity = minimal_project()
        entity.pop("slug")
        errors = validate_project(entity)
        assert "slug" in errors

    def test_project_rejects_wrong_field_key(self):
        from vault.domain.canonical_types import validate_project

        entity = minimal_project()
        entity["project_name"] = "x"
        errors = validate_project(entity)
        assert "unknown_field:project_name" in errors

    def test_project_confidence_enum(self):
        from vault.domain.canonical_types import validate_project

        entity = minimal_project()
        entity["confidence"] = "unknown"
        errors = validate_project(entity)
        assert "confidence_allowed" in errors


class TestRepo:
    def test_valid_repo(self):
        from vault.domain.canonical_types import validate_repo

        assert validate_repo(minimal_repo()) is True

    def test_repo_requires_owner(self):
        from vault.domain.canonical_types import validate_repo

        entity = minimal_repo()
        entity.pop("owner")
        errors = validate_repo(entity)
        assert "owner" in errors

    def test_repo_rejects_legacy_org_field(self):
        from vault.domain.canonical_types import validate_repo

        entity = minimal_repo()
        entity["org"] = "living"
        errors = validate_repo(entity)
        assert "unknown_field:org" in errors


class TestMeeting:
    def test_valid_meeting(self):
        from vault.domain.canonical_types import validate_meeting

        assert validate_meeting(minimal_meeting()) is True

    def test_meeting_requires_meeting_id_source(self):
        from vault.domain.canonical_types import validate_meeting

        entity = minimal_meeting()
        entity.pop("meeting_id_source")
        errors = validate_meeting(entity)
        assert "meeting_id_source" in errors

    def test_meeting_rejects_legacy_date_field(self):
        from vault.domain.canonical_types import validate_meeting

        entity = minimal_meeting()
        entity["date"] = "2026-04-10"
        errors = validate_meeting(entity)
        assert "unknown_field:date" in errors


class TestCard:
    def test_valid_card(self):
        from vault.domain.canonical_types import validate_card

        assert validate_card(minimal_card()) is True

    def test_card_requires_card_id_source(self):
        from vault.domain.canonical_types import validate_card

        entity = minimal_card()
        entity.pop("card_id_source")
        errors = validate_card(entity)
        assert "card_id_source" in errors

    def test_card_rejects_legacy_name_field(self):
        from vault.domain.canonical_types import validate_card

        entity = minimal_card()
        entity["name"] = "legacy"
        errors = validate_card(entity)
        assert "unknown_field:name" in errors


class TestDecision:
    def test_valid_decision(self):
        from vault.domain.canonical_types import validate_decision

        assert validate_decision(minimal_decision()) is True

    def test_decision_requires_sources(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity.pop("sources")
        errors = validate_decision(entity)
        assert "sources" in errors

    def test_decision_rejects_legacy_evidence_field(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity["evidence"] = ["legacy"]
        errors = validate_decision(entity)
        assert "unknown_field:evidence" in errors

    def test_decision_confidence_enum(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity["confidence"] = "very_high"
        errors = validate_decision(entity)
        assert "confidence_allowed" in errors


class TestRelationship:
    def test_valid_relationship(self):
        from vault.domain.canonical_types import validate_relationship

        assert validate_relationship(minimal_relationship()) is True

    def test_relationship_requires_from_id(self):
        from vault.domain.canonical_types import validate_relationship

        edge = minimal_relationship()
        edge.pop("from_id")
        errors = validate_relationship(edge)
        assert "from_id" in errors

    def test_relationship_allowed_roles_only(self):
        from vault.domain.canonical_types import validate_relationship

        edge = minimal_relationship()
        edge["role"] = "owner"
        errors = validate_relationship(edge)
        assert "role_allowed" in errors

    def test_relationship_rejects_wrong_field_names(self):
        from vault.domain.canonical_types import validate_relationship

        edge = minimal_relationship()
        edge["from"] = edge.pop("from_id")
        errors = validate_relationship(edge)
        assert "from_id" in errors
        assert "unknown_field:from" in errors

    def test_relationship_requires_lineage_run_id(self):
        from vault.domain.canonical_types import validate_relationship

        edge = minimal_relationship()
        edge.pop("lineage_run_id")
        errors = validate_relationship(edge)
        assert "lineage_run_id" in errors


class TestSourceValidation:
    def test_source_type_allowed_values(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity["sources"][0]["source_type"] = "github"
        errors = validate_decision(entity)
        assert "sources[0].source_type_allowed" in errors

    def test_source_requires_source_ref(self):
        from vault.domain.canonical_types import validate_relationship

        edge = minimal_relationship()
        edge["sources"][0].pop("source_ref")
        errors = validate_relationship(edge)
        assert "sources[0].source_ref" in errors

    def test_source_requires_mapper_version(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity["sources"][0].pop("mapper_version")
        errors = validate_decision(entity)
        assert "sources[0].mapper_version" in errors


class TestRegression:
    def test_person_confidence_is_optional(self):
        from vault.domain.canonical_types import validate_person

        entity = minimal_person()
        entity.pop("confidence")
        assert validate_person(entity) is True

    def test_person_confidence_enum_rejects_invalid(self):
        from vault.domain.canonical_types import validate_person

        entity = minimal_person()
        entity["confidence"] = "medium-high"
        errors = validate_person(entity)
        assert "confidence_allowed" in errors

    def test_person_rejects_invalid_source_keys_type(self):
        from vault.domain.canonical_types import validate_person

        entity = minimal_person()
        entity["source_keys"] = "not-an-array"
        errors = validate_person(entity)
        assert "source_keys_type" in errors

    def test_project_aliases_is_optional(self):
        from vault.domain.canonical_types import validate_project

        entity = minimal_project()
        entity.pop("aliases")
        entity.pop("status")
        assert validate_project(entity) is True

    def test_repo_archived_is_optional_bool(self):
        from vault.domain.canonical_types import validate_repo

        entity = minimal_repo()
        entity.pop("archived")
        entity.pop("default_branch")
        assert validate_repo(entity) is True

    def test_repo_project_ref_is_optional(self):
        from vault.domain.canonical_types import validate_repo

        entity = minimal_repo()
        entity.pop("project_ref")
        assert validate_repo(entity) is True

    def test_relationship_since_until_optional(self):
        from vault.domain.canonical_types import validate_relationship

        edge = minimal_relationship()
        edge.pop("since")
        edge.pop("until")
        edge.pop("window_days")
        assert validate_relationship(edge) is True

    def test_relationship_confidence_required(self):
        from vault.domain.canonical_types import validate_relationship

        edge = minimal_relationship()
        edge.pop("confidence")
        errors = validate_relationship(edge)
        assert "confidence" in errors

    def test_relationship_role_invalid(self):
        from vault.domain.canonical_types import validate_relationship

        edge = minimal_relationship()
        edge["role"] = "contributor"
        errors = validate_relationship(edge)
        assert "role_allowed" in errors

    def test_decision_project_ref_is_optional(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity.pop("project_ref")
        assert validate_decision(entity) is True

    def test_decision_confidence_is_optional(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity.pop("confidence")
        assert validate_decision(entity) is True

    def test_decision_last_verified_required(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity.pop("last_verified")
        errors = validate_decision(entity)
        assert "last_verified" in errors

    def test_decision_multiple_sources_all_validated(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity["sources"].append(_source())
        entity["sources"][1]["source_type"] = "tldv_api"
        assert validate_decision(entity) is True

    def test_decision_second_source_invalid(self):
        from vault.domain.canonical_types import validate_decision

        entity = minimal_decision()
        entity["sources"].append(_source())
        entity["sources"][1]["source_type"] = "unknown_api"
        errors = validate_decision(entity)
        assert "sources[1].source_type_allowed" in errors


class TestHelpers:
    def test_is_iso_date_valid_formats(self):
        from vault.domain.canonical_types import is_iso_date

        assert is_iso_date("2026-04-10")
        assert is_iso_date("2026-04-10T10:00:00Z")
        assert is_iso_date("2026-04-10T10:00:00+00:00")
        assert is_iso_date("2026-04-10T10:00:00+01:00")

    def test_is_iso_date_rejects_invalid(self):
        from vault.domain.canonical_types import is_iso_date

        assert not is_iso_date("not-a-date")
        assert not is_iso_date("10/04/2026")
        assert not is_iso_date("2026-13-01")
        assert not is_iso_date(123)
        assert not is_iso_date(None)

    def test_is_valid_id_prefix_all_entity_types(self):
        from vault.domain.canonical_types import is_valid_id_prefix

        assert is_valid_id_prefix("person:lincolnqjunior")
        assert is_valid_id_prefix("project:livy-memory")
        assert is_valid_id_prefix("repo:living/livy-memory-bot")
        assert is_valid_id_prefix("meeting:tldv-12345")
        assert is_valid_id_prefix("card:trello-abc123")
        assert is_valid_id_prefix("decision:arch-001")
        assert not is_valid_id_prefix("user:lincoln")
        assert not is_valid_id_prefix("person-lincoln")
        assert not is_valid_id_prefix("")
        assert not is_valid_id_prefix(None)
