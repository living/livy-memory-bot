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

    def test_lowercase_domain(self):
        assert normalize_email("User@Example.COM") == "user@example.com"

    def test_strip_whitespace(self):
        assert normalize_email("  user@example.com  ") == "user@example.com"

    def test_combined_normalization(self):
        assert normalize_email("  User@Example.COM  ") == "user@example.com"

    def test_already_normal(self):
        assert normalize_email("user@example.com") == "user@example.com"

    def test_plusAddressing_stripped(self):
        """Plus-addressing variants should normalize to same address."""
        # Note: conservative approach - we normalize but don't strip +suffix
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
