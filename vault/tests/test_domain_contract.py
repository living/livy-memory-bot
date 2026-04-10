"""
Tests for vault/domain/canonical_types.py — canonical domain contract validators.

Implements strict TDD: RED -> GREEN -> REFACTOR.
Tests validate that each canonical entity type has required fields and valid structure.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Fixtures — shared entity builders for convenience
# ---------------------------------------------------------------------------

def minimal_person() -> dict:
    return {
        "id_canonical": "person:lincoln",
        "name": "Lincoln Quinan Junior",
        "github_login": "lincolnq",
        "email": "lincoln@livingnet.com.br",
        "source_type": "tldv",
        "source_ref": "meeting-123",
        "retrieved_at": "2026-04-10T10:00:00+00:00",
        "lineage_run_id": "run-001",
        "mapper_version": "1.0.0",
    }


def minimal_project() -> dict:
    return {
        "id_canonical": "project:livy-memory",
        "name": "Livy Memory Bot",
        "source_type": "tldv",
        "source_ref": "meeting-456",
        "retrieved_at": "2026-04-10T10:00:00+00:00",
        "lineage_run_id": "run-001",
        "mapper_version": "1.0.0",
    }


def minimal_repo() -> dict:
    return {
        "id_canonical": "repo:living/livy-memory-bot",
        "name": "livy-memory-bot",
        "org": "living",
        "full_name": "living/livy-memory-bot",
        "source_type": "github",
        "source_ref": "pr-789",
        "retrieved_at": "2026-04-10T10:00:00+00:00",
        "lineage_run_id": "run-001",
        "mapper_version": "1.0.0",
    }


def minimal_meeting() -> dict:
    return {
        "id_canonical": "meeting:tldv-12345",
        "name": "Daily Status",
        "date": "2026-04-10",
        "participants": ["person:lincoln"],
        "source_type": "tldv",
        "source_ref": "meeting-12345",
        "retrieved_at": "2026-04-10T10:00:00+00:00",
        "lineage_run_id": "run-001",
        "mapper_version": "1.0.0",
    }


def minimal_card() -> dict:
    return {
        "id_canonical": "card:trello-abc123",
        "name": "Implement domain model",
        "board_ref": "project:livy-memory",
        "source_type": "trello",
        "source_ref": "card-abc123",
        "retrieved_at": "2026-04-10T10:00:00+00:00",
        "lineage_run_id": "run-001",
        "mapper_version": "1.0.0",
    }


def minimal_decision() -> dict:
    return {
        "id_canonical": "decision:arch-001",
        "title": "Use domain-first architecture",
        "evidence": ["https://tldv.io/meeting/123"],
        "confidence": "medium",
        "source_type": "tldv",
        "source_ref": "meeting-123",
        "retrieved_at": "2026-04-10T10:00:00+00:00",
        "lineage_run_id": "run-001",
        "mapper_version": "1.0.0",
    }


def minimal_relationship() -> dict:
    return {
        "from": "person:lincoln",
        "to": "repo:living/livy-memory-bot",
        "role": "author",
        "source_type": "github",
        "source_ref": "pr-101",
        "retrieved_at": "2026-04-10T10:00:00+00:00",
        "lineage_run_id": "run-001",
        "mapper_version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Import — tests should fail here until module is created
# ---------------------------------------------------------------------------

def test_module_imports():
    """Module must exist and be importable."""
    import vault.domain.canonical_types as ct  # noqa: F401


# ---------------------------------------------------------------------------
# Person validator
# ---------------------------------------------------------------------------

class TestValidatePerson:
    def test_valid_person_passes(self):
        from vault.domain.canonical_types import validate_person
        assert validate_person(minimal_person()) is True

    def test_person_requires_id_canonical(self):
        from vault.domain.canonical_types import validate_person
        p = minimal_person()
        del p["id_canonical"]
        errors = validate_person(p)
        assert errors  # returns list of field errors

    def test_person_requires_name(self):
        from vault.domain.canonical_types import validate_person
        p = minimal_person()
        del p["name"]
        errors = validate_person(p)
        assert errors

    def test_person_id_must_start_with_person_prefix(self):
        from vault.domain.canonical_types import validate_person
        p = minimal_person()
        p["id_canonical"] = "user:wrong-prefix"
        errors = validate_person(p)
        assert errors

    def test_person_accepts_optional_github_login(self):
        from vault.domain.canonical_types import validate_person
        p = minimal_person()
        assert validate_person(p) is True

    def test_person_accepts_optional_email(self):
        from vault.domain.canonical_types import validate_person
        p = minimal_person()
        assert validate_person(p) is True

    def test_person_rejects_unknown_field(self):
        from vault.domain.canonical_types import validate_person
        p = minimal_person()
        p["unknown_field"] = "should-reject"
        errors = validate_person(p)
        assert errors

    def test_person_requires_traceability_fields(self):
        from vault.domain.canonical_types import validate_person
        p = minimal_person()
        for field in ("source_type", "source_ref", "retrieved_at", "lineage_run_id", "mapper_version"):
            del p[field]
        errors = validate_person(p)
        assert errors


# ---------------------------------------------------------------------------
# Project validator
# ---------------------------------------------------------------------------

class TestValidateProject:
    def test_valid_project_passes(self):
        from vault.domain.canonical_types import validate_project
        assert validate_project(minimal_project()) is True

    def test_project_requires_id_canonical(self):
        from vault.domain.canonical_types import validate_project
        pj = minimal_project()
        del pj["id_canonical"]
        errors = validate_project(pj)
        assert errors

    def test_project_requires_name(self):
        from vault.domain.canonical_types import validate_project
        pj = minimal_project()
        del pj["name"]
        errors = validate_project(pj)
        assert errors

    def test_project_id_must_start_with_project_prefix(self):
        from vault.domain.canonical_types import validate_project
        pj = minimal_project()
        pj["id_canonical"] = "proj:wrong-prefix"
        errors = validate_project(pj)
        assert errors

    def test_project_requires_traceability_fields(self):
        from vault.domain.canonical_types import validate_project
        pj = minimal_project()
        for field in ("source_type", "source_ref", "retrieved_at", "lineage_run_id", "mapper_version"):
            del pj[field]
        errors = validate_project(pj)
        assert errors


# ---------------------------------------------------------------------------
# Repo validator
# ---------------------------------------------------------------------------

class TestValidateRepo:
    def test_valid_repo_passes(self):
        from vault.domain.canonical_types import validate_repo
        assert validate_repo(minimal_repo()) is True

    def test_repo_requires_id_canonical(self):
        from vault.domain.canonical_types import validate_repo
        r = minimal_repo()
        del r["id_canonical"]
        errors = validate_repo(r)
        assert errors

    def test_repo_requires_name(self):
        from vault.domain.canonical_types import validate_repo
        r = minimal_repo()
        del r["name"]
        errors = validate_repo(r)
        assert errors

    def test_repo_requires_org(self):
        from vault.domain.canonical_types import validate_repo
        r = minimal_repo()
        del r["org"]
        errors = validate_repo(r)
        assert errors

    def test_repo_id_must_start_with_repo_prefix(self):
        from vault.domain.canonical_types import validate_repo
        r = minimal_repo()
        r["id_canonical"] = "repository:wrong-prefix"
        errors = validate_repo(r)
        assert errors

    def test_repo_requires_traceability_fields(self):
        from vault.domain.canonical_types import validate_repo
        r = minimal_repo()
        for field in ("source_type", "source_ref", "retrieved_at", "lineage_run_id", "mapper_version"):
            del r[field]
        errors = validate_repo(r)
        assert errors


# ---------------------------------------------------------------------------
# Meeting validator
# ---------------------------------------------------------------------------

class TestValidateMeeting:
    def test_valid_meeting_passes(self):
        from vault.domain.canonical_types import validate_meeting
        assert validate_meeting(minimal_meeting()) is True

    def test_meeting_requires_id_canonical(self):
        from vault.domain.canonical_types import validate_meeting
        m = minimal_meeting()
        del m["id_canonical"]
        errors = validate_meeting(m)
        assert errors

    def test_meeting_requires_name(self):
        from vault.domain.canonical_types import validate_meeting
        m = minimal_meeting()
        del m["name"]
        errors = validate_meeting(m)
        assert errors

    def test_meeting_requires_date(self):
        from vault.domain.canonical_types import validate_meeting
        m = minimal_meeting()
        del m["date"]
        errors = validate_meeting(m)
        assert errors

    def test_meeting_date_must_be_iso_format(self):
        from vault.domain.canonical_types import validate_meeting
        m = minimal_meeting()
        m["date"] = "not-a-date"
        errors = validate_meeting(m)
        assert errors

    def test_meeting_id_must_start_with_meeting_prefix(self):
        from vault.domain.canonical_types import validate_meeting
        m = minimal_meeting()
        m["id_canonical"] = "mtg:wrong-prefix"
        errors = validate_meeting(m)
        assert errors

    def test_meeting_requires_traceability_fields(self):
        from vault.domain.canonical_types import validate_meeting
        m = minimal_meeting()
        for field in ("source_type", "source_ref", "retrieved_at", "lineage_run_id", "mapper_version"):
            del m[field]
        errors = validate_meeting(m)
        assert errors


# ---------------------------------------------------------------------------
# Card validator
# ---------------------------------------------------------------------------

class TestValidateCard:
    def test_valid_card_passes(self):
        from vault.domain.canonical_types import validate_card
        assert validate_card(minimal_card()) is True

    def test_card_requires_id_canonical(self):
        from vault.domain.canonical_types import validate_card
        c = minimal_card()
        del c["id_canonical"]
        errors = validate_card(c)
        assert errors

    def test_card_requires_name(self):
        from vault.domain.canonical_types import validate_card
        c = minimal_card()
        del c["name"]
        errors = validate_card(c)
        assert errors

    def test_card_id_must_start_with_card_prefix(self):
        from vault.domain.canonical_types import validate_card
        c = minimal_card()
        c["id_canonical"] = "item:wrong-prefix"
        errors = validate_card(c)
        assert errors

    def test_card_requires_traceability_fields(self):
        from vault.domain.canonical_types import validate_card
        c = minimal_card()
        for field in ("source_type", "source_ref", "retrieved_at", "lineage_run_id", "mapper_version"):
            del c[field]
        errors = validate_card(c)
        assert errors


# ---------------------------------------------------------------------------
# Decision validator
# ---------------------------------------------------------------------------

class TestValidateDecision:
    def test_valid_decision_passes(self):
        from vault.domain.canonical_types import validate_decision
        assert validate_decision(minimal_decision()) is True

    def test_decision_requires_id_canonical(self):
        from vault.domain.canonical_types import validate_decision
        d = minimal_decision()
        del d["id_canonical"]
        errors = validate_decision(d)
        assert errors

    def test_decision_requires_title(self):
        from vault.domain.canonical_types import validate_decision
        d = minimal_decision()
        del d["title"]
        errors = validate_decision(d)
        assert errors

    def test_decision_requires_evidence_as_list(self):
        from vault.domain.canonical_types import validate_decision
        d = minimal_decision()
        d["evidence"] = "not-a-list"
        errors = validate_decision(d)
        assert errors

    def test_decision_requires_confidence_in_allowed_set(self):
        from vault.domain.canonical_types import validate_decision
        d = minimal_decision()
        d["confidence"] = "super-high"
        errors = validate_decision(d)
        assert errors

    def test_decision_id_must_start_with_decision_prefix(self):
        from vault.domain.canonical_types import validate_decision
        d = minimal_decision()
        d["id_canonical"] = "dec:wrong-prefix"
        errors = validate_decision(d)
        assert errors

    def test_decision_requires_traceability_fields(self):
        from vault.domain.canonical_types import validate_decision
        d = minimal_decision()
        for field in ("source_type", "source_ref", "retrieved_at", "lineage_run_id", "mapper_version"):
            del d[field]
        errors = validate_decision(d)
        assert errors


# ---------------------------------------------------------------------------
# Relationship validator
# ---------------------------------------------------------------------------

class TestValidateRelationship:
    def test_valid_relationship_passes(self):
        from vault.domain.canonical_types import validate_relationship
        assert validate_relationship(minimal_relationship()) is True

    def test_relationship_requires_from(self):
        from vault.domain.canonical_types import validate_relationship
        r = minimal_relationship()
        del r["from"]
        errors = validate_relationship(r)
        assert errors

    def test_relationship_requires_to(self):
        from vault.domain.canonical_types import validate_relationship
        r = minimal_relationship()
        del r["to"]
        errors = validate_relationship(r)
        assert errors

    def test_relationship_requires_role(self):
        from vault.domain.canonical_types import validate_relationship
        r = minimal_relationship()
        del r["role"]
        errors = validate_relationship(r)
        assert errors

    def test_relationship_role_must_be_allowed(self):
        from vault.domain.canonical_types import validate_relationship
        r = minimal_relationship()
        r["role"] = "unknown-role"
        errors = validate_relationship(r)
        assert errors

    def test_relationship_requires_traceability_fields(self):
        from vault.domain.canonical_types import validate_relationship
        r = minimal_relationship()
        for field in ("source_type", "source_ref", "retrieved_at", "lineage_run_id", "mapper_version"):
            del r[field]
        errors = validate_relationship(r)
        assert errors


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

class TestIsValidIdPrefix:
    def test_valid_prefix_person(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert is_valid_id_prefix("person:lincoln")

    def test_valid_prefix_project(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert is_valid_id_prefix("project:livy-memory")

    def test_valid_prefix_repo(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert is_valid_id_prefix("repo:living/livy-memory-bot")

    def test_valid_prefix_meeting(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert is_valid_id_prefix("meeting:tldv-12345")

    def test_valid_prefix_card(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert is_valid_id_prefix("card:trello-abc123")

    def test_valid_prefix_decision(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert is_valid_id_prefix("decision:arch-001")

    def test_invalid_prefix(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert not is_valid_id_prefix("user:lincoln")

    def test_invalid_format_no_colon(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert not is_valid_id_prefix("person-lincoln")

    def test_empty_id(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert not is_valid_id_prefix("")

    def test_none_id(self):
        from vault.domain.canonical_types import is_valid_id_prefix
        assert not is_valid_id_prefix(None)


class TestIsIsoDate:
    def test_valid_iso_date(self):
        from vault.domain.canonical_types import is_iso_date
        assert is_iso_date("2026-04-10")

    def test_valid_iso_datetime(self):
        from vault.domain.canonical_types import is_iso_date
        assert is_iso_date("2026-04-10T10:00:00+00:00")

    def test_invalid_date(self):
        from vault.domain.canonical_types import is_iso_date
        assert not is_iso_date("not-a-date")

    def test_invalid_format(self):
        from vault.domain.canonical_types import is_iso_date
        assert not is_iso_date("10/04/2026")
