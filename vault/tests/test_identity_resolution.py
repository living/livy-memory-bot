"""Tests for conservative identity resolution — TDD RED phase."""
from __future__ import annotations

import pytest

from vault.domain.identity_resolution import (
    IdentityResult,
    MergeAction,
    resolve_identity,
    normalize_email,
)


class TestNormalizeEmail:
    """Email normalization for identity matching."""

    def test_lowercase_email_for_matching(self):
        assert normalize_email("User@Example.COM") == "user@example.com"

    def test_strip_whitespace(self):
        assert normalize_email("  user@example.com  ") == "user@example.com"

    def test_combined_normalization(self):
        assert normalize_email("  User@Example.COM  ") == "user@example.com"

    def test_already_normal(self):
        assert normalize_email("user@example.com") == "user@example.com"

    def test_plusAddressing_preserved(self):
        """Plus-addressing suffix is preserved in conservative normalization."""
        assert normalize_email("user+tag@example.com") == "user+tag@example.com"


class TestMergeOnExactGithubLogin:
    """Merge candidates when github_login matches exactly."""

    def test_exact_github_login_match_returns_merge(self):
        """Exact github_login match with multi-source evidence → auto-merge."""
        existing = {
            "id_canonical": "person:lincolnq",
            "github_login": "lincolnq",
            "email": "old@example.com",
            "source_keys": ["github:lincolnq", "tldv:lincoln@livingnet.com.br"],
        }
        incoming = {
            "id_canonical": "person:lincolnq-v2",
            "github_login": "lincolnq",  # exact match
            "email": "new@example.com",
        }
        result = resolve_identity(existing, incoming)
        assert isinstance(result, IdentityResult)
        assert result.action == MergeAction.MERGE

    def test_exact_match_with_single_source_key_returns_review(self):
        """Spec guardrail: unambiguous match with <2 source_keys must be review."""
        existing = {
            "id_canonical": "person:lincolnq",
            "github_login": "lincolnq",
            "source_keys": ["github:lincolnq"],
        }
        incoming = {"github_login": "lincolnq"}
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.REVIEW

    def test_github_login_case_sensitive(self):
        """GitHub login matching is case-sensitive."""
        existing = {"github_login": "LinColnQ"}
        incoming = {"github_login": "lincolnq"}
        result = resolve_identity(existing, incoming)
        # Different case → no merge
        assert result.action == MergeAction.NO_MATCH


class TestMergeOnNormalizedEmail:
    """Merge candidates when normalized email matches."""

    def test_email_case_insensitive_match_returns_merge(self):
        """Normalized email match (different case) + multi-source evidence → auto-merge."""
        existing = {
            "github_login": None,
            "email": "User@Example.COM",
            "source_keys": ["github:user", "tldv:user@example.com"],
        }
        incoming = {"github_login": None, "email": "user@example.com"}
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.MERGE

    def test_email_whitespace_stripped_match_returns_merge(self):
        """Normalized email match (whitespace) + multi-source evidence → auto-merge."""
        existing = {
            "email": "  user@example.com  ",
            "source_keys": ["github:user", "tldv:user@example.com"],
        }
        incoming = {"email": "user@example.com"}
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.MERGE

    def test_different_emails_no_match(self):
        """Different emails → no match."""
        existing = {"email": "user1@example.com"}
        incoming = {"email": "user2@example.com"}
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.NO_MATCH


class TestAmbiguousIdentity:
    """Ambiguous identity returns review item, not auto-merge."""

    def test_github_login_and_email_match_different_candidates_returns_review(self):
        """Conflicting identity signals across candidates → ambiguous REVIEW."""
        existing = [
            {
                "id_canonical": "person:lincoln-login",
                "github_login": "lincolnq",
                "email": "other@livingnet.com.br",
            },
            {
                "id_canonical": "person:lincoln-email",
                "github_login": "someoneelse",
                "email": "lincoln@livingnet.com.br",
            },
        ]
        incoming = {
            "id_canonical": "person:lincolnq-v2",
            "github_login": "lincolnq",
            "email": "LINCOLN@LivingNet.com.br",
        }
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.REVIEW

    def test_multiple_existing_candidates_returns_review(self):
        """Multiple potential matches → ambiguous, needs review."""
        # Simulating finding multiple people with same email domain
        candidates = [
            {"id_canonical": "person:alice", "github_login": None, "email": "alice@corp.com"},
            {"id_canonical": "person:alice2", "github_login": None, "email": "alice@corp.com"},
        ]
        incoming = {"github_login": None, "email": "ALICE@CORP.COM"}
        result = resolve_identity(candidates, incoming)
        # Multiple matches → ambiguous
        assert result.action == MergeAction.REVIEW

    def test_single_match_returns_merge(self):
        """Single unambiguous match + multi-source evidence → auto-merge."""
        existing = {
            "id_canonical": "person:lincolnq",
            "github_login": "lincolnq",
            "email": "lincoln@livingnet.com.br",
            "source_keys": ["github:lincolnq", "tldv:lincoln@livingnet.com.br"],
        }
        incoming = {
            "github_login": "lincolnq",
            "email": "different@example.com",
        }
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.MERGE


class TestNoMatchScenarios:
    """No match scenarios return NO_MATCH."""

    def test_no_github_login_no_email(self):
        """Neither github_login nor email present → no match."""
        existing = {}
        incoming = {}
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.NO_MATCH

    def test_github_login_in_one_only(self):
        """github_login in only one record → no match."""
        existing = {"github_login": "user1"}
        incoming = {"github_login": None, "email": "user1@example.com"}
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.NO_MATCH

    def test_email_in_one_only(self):
        """email in only one record → no match."""
        existing = {"email": "user@example.com"}
        incoming = {"github_login": "user"}
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.NO_MATCH


class TestIdentityResult:
    """IdentityResult structure and attributes."""

    def test_merge_result_has_canonical_id(self):
        """MERGE result includes the canonical id of existing entity."""
        existing = {
            "id_canonical": "person:lincolnq",
            "github_login": "lincolnq",
            "source_keys": ["github:lincolnq", "tldv:lincoln@livingnet.com.br"],
        }
        incoming = {"github_login": "lincolnq"}
        result = resolve_identity(existing, incoming)
        assert isinstance(result, IdentityResult)
        assert result.action == MergeAction.MERGE
        assert result.canonical_id == "person:lincolnq"

    def test_review_result_has_candidates(self):
        """REVIEW result includes ambiguous candidates."""
        existing = [
            {
                "id_canonical": "person:alice",
                "github_login": None,
                "email": "alice@corp.com",
            },
            {
                "id_canonical": "person:alice2",
                "github_login": None,
                "email": "ALICE@CORP.COM",
            },
        ]
        incoming = {"email": "alice@corp.com"}
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.REVIEW
        assert result.canonical_id is None
        assert len(result.candidates) == 2

    def test_no_match_result(self):
        """NO_MATCH result has no canonical_id or candidates."""
        existing = {}
        incoming = {}
        result = resolve_identity(existing, incoming)
        assert result.action == MergeAction.NO_MATCH
        assert result.canonical_id is None
        assert result.candidates == []


class TestResolveBySourceKey:
    """Generic resolver by exact source_key match (Wave C Phase C2)."""

    def test_resolve_meeting_exact_match_returns_merge(self):
        """Exact source_key match for meeting → MERGE (not MATCH)."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {
                "id_canonical": "meeting:daily-2026-04-10",
                "meeting_id_source": "daily-2026-04-10",
                "source_keys": ["tldv:daily-2026-04-10"],
                "confidence": "medium",
            }
        ]
        result = resolve_by_source_key(existing, "meeting", "tldv:daily-2026-04-10")
        assert result.action == MergeAction.MERGE
        assert result.canonical_id == "meeting:daily-2026-04-10"

    def test_resolve_meeting_no_match_returns_no_match(self):
        """Non-existent source_key → NO_MATCH."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {"id_canonical": "meeting:other", "source_keys": ["tldv:other"]}
        ]
        result = resolve_by_source_key(existing, "meeting", "tldv:nonexistent")
        assert result.action == MergeAction.NO_MATCH

    def test_resolve_card_exact_match_returns_merge(self):
        """Exact source_key match for card → MERGE (not MATCH)."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {
                "id_canonical": "card:b1:abc123",
                "card_id_source": "abc123",
                "source_keys": ["trello:b1:abc123"],
            }
        ]
        result = resolve_by_source_key(existing, "card", "trello:b1:abc123")
        assert result.action == MergeAction.MERGE
        assert result.canonical_id == "card:b1:abc123"

    def test_resolve_card_no_match_returns_no_match(self):
        """Non-existent card source_key → NO_MATCH."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {"id_canonical": "card:b1:xyz", "source_keys": ["trello:b1:xyz"]}
        ]
        result = resolve_by_source_key(existing, "card", "trello:b1:nonexistent")
        assert result.action == MergeAction.NO_MATCH

    def test_resolve_person_uses_exact_source_key_match(self):
        """Person lookup by source_key → MERGE when exact match exists."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {
                "id_canonical": "person:robert",
                "github_login": "robert",
                "source_keys": ["github:robert", "tldv:participant:daily:robert-p1"],
            }
        ]
        result = resolve_by_source_key(existing, "person", "github:robert")
        assert result.action == MergeAction.MERGE
        assert result.canonical_id == "person:robert"

    def test_resolve_repo_exact_match(self):
        """Repo lookup by source_key → MERGE."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {
                "id_canonical": "repo:living-forge",
                "source_keys": ["github:living/forge-platform"],
            }
        ]
        result = resolve_by_source_key(existing, "repo", "github:living/forge-platform")
        assert result.action == MergeAction.MERGE
        assert result.canonical_id == "repo:living-forge"

    def test_resolve_empty_existing_returns_no_match(self):
        """Empty existing list → NO_MATCH."""
        from vault.domain.identity_resolution import resolve_by_source_key
        result = resolve_by_source_key([], "meeting", "tldv:daily")
        assert result.action == MergeAction.NO_MATCH

    def test_resolve_person_single_source_key_guardrail_preserved(self):
        """Person with <2 source_keys → REVIEW (guardrail preserved)."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {
                "id_canonical": "person:robert",
                "github_login": "robert",
                "source_keys": ["github:robert"],  # only 1 source_key
            }
        ]
        result = resolve_by_source_key(existing, "person", "github:robert")
        assert result.action == MergeAction.REVIEW

    def test_resolve_duplicate_source_key_returns_review_with_candidates(self):
        """Duplicate source_key across entities is ambiguous and must be reviewed."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {
                "id_canonical": "meeting:daily-1",
                "source_keys": ["tldv:daily-duplicate"],
            },
            {
                "id_canonical": "meeting:daily-2",
                "source_keys": ["tldv:daily-duplicate"],
            },
        ]
        result = resolve_by_source_key(existing, "meeting", "tldv:daily-duplicate")
        assert result.action == MergeAction.REVIEW
        assert result.canonical_id is None
        assert len(result.candidates) == 2

    def test_resolve_invalid_entity_type_returns_review(self):
        """Unknown entity_type is a contract violation and requires review."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {
                "id_canonical": "meeting:daily-2026-04-10",
                "source_keys": ["tldv:daily-2026-04-10"],
            }
        ]
        result = resolve_by_source_key(existing, "unknown-type", "tldv:daily-2026-04-10")
        assert result.action == MergeAction.REVIEW
        assert result.canonical_id is None
        assert len(result.candidates) == 1

    def test_resolve_match_missing_id_canonical_returns_review(self):
        """Exact match without id_canonical must not auto-merge."""
        from vault.domain.identity_resolution import resolve_by_source_key
        existing = [
            {
                # id_canonical intentionally missing
                "source_keys": ["github:living/forge-platform"],
            }
        ]
        result = resolve_by_source_key(existing, "repo", "github:living/forge-platform")
        assert result.action == MergeAction.REVIEW
        assert result.canonical_id is None
        assert len(result.candidates) == 1
