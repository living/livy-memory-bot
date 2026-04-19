"""Tests for vault/research/github_parsers.py — GitHub PR parsers and claim extraction.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_pr_payload(
    number: int = 42,
    title: str = "feat: implement something",
    body: str = "Closes #99",
    state: str = "closed",
    merged: bool = True,
    merged_at: str = "2026-04-14T10:00:00Z",
    created_at: str = "2026-04-13T09:00:00Z",
    user_login: str = "lincolnq",
    repo: str = "living/livy-memory-bot",
    labels: list = None,
    milestone: dict = None,
    assignees: list = None,
    reviewers: list = None,
) -> dict:
    """Build a realistic GitHub PR payload dict."""
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "merged": merged,
        "merged_at": merged_at,
        "created_at": created_at,
        "user": {"login": user_login, "id": 445449},
        "base": {"ref": "main", "repo": {"full_name": repo}},
        "html_url": f"https://github.com/{repo}/pull/{number}",
        "labels": labels or [],
        "milestone": milestone,
        "assignees": assignees or [],
        "requested_reviewers": reviewers or [],
    }


def _make_review(state: str, user_login: str, body: str = "") -> dict:
    return {"state": state, "user": {"login": user_login}, "body": body}


# ---------------------------------------------------------------------------
# Test: fetch_pr_with_reviews
# ---------------------------------------------------------------------------

class TestFetchPrWithReviews:
    """fetch_pr_with_reviews fetches PR + reviews and merges them."""

    def test_fetches_pr_and_reviews_via_gh_cli(self):
        """gh CLI is called for PR endpoint and reviews endpoint."""
        from vault.research.github_parsers import GitHubParsers

        pr_json = '{"number":42,"title":"t","body":"b","merged":true,"user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"state":"closed","labels":[],"merged_at":"2026-04-14T10:00:00Z","created_at":"2026-04-13T09:00:00Z"}'
        reviews_json = '[{"state":"APPROVED","user":{"login":"alice"},"body":"LGTM"}]'

        calls: list = []

        def run_side(cmd, *a, **kw):
            m = MagicMock(returncode=0)
            cmd_str = str(cmd)
            if "reviews" in cmd_str:
                m.stdout = reviews_json
            else:
                m.stdout = pr_json
            calls.append(cmd_str)
            return m

        with patch("subprocess.run", side_effect=run_side):
            result = GitHubParsers.fetch_pr_with_reviews(42, "living/livy-memory-bot")

        assert result["pr"]["number"] == 42
        assert len(result["reviews"]) == 1
        assert result["reviews"][0]["state"] == "APPROVED"
        assert result["reviews"][0]["user"]["login"] == "alice"

    def test_returns_empty_reviews_on_failure(self):
        """If gh CLI fails, returns empty reviews list (graceful degradation)."""
        from vault.research.github_parsers import GitHubParsers

        def run_side(cmd, *a, **kw):
            m = MagicMock(returncode=1, stdout="")
            return m

        with patch("subprocess.run", side_effect=run_side):
            result = GitHubParsers.fetch_pr_with_reviews(99, "living/test")

        assert result["reviews"] == []
        assert "pr" in result

    def test_reviews_parsed_as_list(self):
        """reviews field is always a list, never None or empty-dict."""
        from vault.research.github_parsers import GitHubParsers

        pr_json = '{"number":1,"title":"t","body":"","merged":true,"user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"state":"closed","labels":[],"merged_at":"1Z","created_at":"1Z"}'

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=pr_json)):
            result = GitHubParsers.fetch_pr_with_reviews(1, "r")

        assert isinstance(result["reviews"], list)

    def test_handles_empty_pr_body(self):
        """Empty/null body does not raise."""
        from vault.research.github_parsers import GitHubParsers

        pr_json = '{"number":2,"title":"t","body":null,"merged":true,"user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"state":"closed","labels":[],"merged_at":"2Z","created_at":"2Z"}'

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=pr_json)):
            result = GitHubParsers.fetch_pr_with_reviews(2, "r")

        assert result["pr"].get("body") in ("", None)

    def test_approvers_extracted_from_reviews(self):
        """Result includes list of approvers (unique logins with APPROVED state)."""
        from vault.research.github_parsers import GitHubParsers

        pr_json = '{"number":3,"title":"t","body":"","merged":true,"user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"state":"closed","labels":[],"merged_at":"3Z","created_at":"3Z"}'
        reviews_json = """[
            {"state":"APPROVED","user":{"login":"alice"},"body":"ok"},
            {"state":"CHANGES_REQUESTED","user":{"login":"bob"},"body":"nits"},
            {"state":"APPROVED","user":{"login":"alice"},"body":"still ok"}
        ]"""

        with patch("subprocess.run") as mock_run:
            def side(cmd, *a, **kw):
                m = MagicMock(returncode=0)
                m.stdout = reviews_json if "reviews" in str(cmd) else pr_json
                return m
            mock_run.side_effect = side
            result = GitHubParsers.fetch_pr_with_reviews(3, "r")

        assert "approvers" in result
        assert "alice" in result["approvers"]
        assert "bob" not in result["approvers"]  # CHANGES_REQUESTED

    def test_returns_pr_number_and_repo(self):
        """Result exposes pr_number and repo fields for downstream use."""
        from vault.research.github_parsers import GitHubParsers

        pr_json = '{"number":4,"title":"t","body":"","merged":true,"user":{"login":"x"},"base":{"repo":{"full_name":"living/livy-forge"}},"state":"closed","labels":[],"merged_at":"4Z","created_at":"4Z"}'

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=pr_json)):
            result = GitHubParsers.fetch_pr_with_reviews(4, "living/livy-forge")

        assert result["pr_number"] == 4
        assert result["repo"] == "living/livy-forge"


# ---------------------------------------------------------------------------
# Test: pr_to_claims
# ---------------------------------------------------------------------------

class TestPrToClaims:
    """pr_to_claims generates normalized claim dicts from parsed PR data."""

    def test_claim_types_are_valid(self):
        """Generated claims use valid claim_type values."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload()
        result = pr_to_claims(pr_payload, [])

        assert len(result) > 0
        for claim in result:
            assert "claim_type" in claim
            assert isinstance(claim["claim_type"], str)

    def test_every_claim_has_source_github(self):
        """All claims have source = 'github'."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload()
        reviews = [_make_review("APPROVED", "alice")]
        claims = pr_to_claims(pr_payload, reviews)

        for claim in claims:
            assert claim["source"] == "github"

    def test_every_claim_has_source_ref(self):
        """All claims carry a source_ref with the PR URL."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(number=55, repo="living/test")
        claims = pr_to_claims(pr_payload, [])

        assert len(claims) > 0
        for claim in claims:
            assert "source_ref" in claim
            assert "living/test" in str(claim["source_ref"])

    def test_claim_has_event_timestamp(self):
        """Claims carry event_timestamp from merged_at or created_at."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(merged_at="2026-04-14T10:00:00Z")
        claims = pr_to_claims(pr_payload, [])

        assert len(claims) > 0
        for claim in claims:
            assert "event_timestamp" in claim

    def test_approver_claim_generated_for_approved_review(self):
        """A review with APPROVED state produces an 'approval' claim."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(number=10)
        reviews = [_make_review("APPROVED", "alice", "LGTM")]
        claims = pr_to_claims(pr_payload, reviews)

        approval_claims = [c for c in claims if c.get("claim_type") == "approval"]
        assert len(approval_claims) >= 1
        assert approval_claims[0]["metadata"]["approver"] == "alice"

    def test_no_approval_claim_for_changes_requested(self):
        """CHANGES_REQUESTED review does NOT produce approval claim."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(number=11)
        reviews = [_make_review("CHANGES_REQUESTED", "bob")]
        claims = pr_to_claims(pr_payload, reviews)

        approval_claims = [c for c in claims if c.get("claim_type") == "approval"]
        assert len(approval_claims) == 0

    def test_status_claim_contains_title_and_state(self):
        """PR status claim includes title and merged state."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(
            number=20,
            title="feat: new feature",
            state="closed",
            merged=True,
        )
        claims = pr_to_claims(pr_payload, [])

        status_claims = [c for c in claims if c.get("claim_type") == "status"]
        assert len(status_claims) >= 1
        status = status_claims[0]
        assert "new feature" in status["text"]
        assert status["metadata"]["merged"] is True

    def test_merges_repeated_approvers(self):
        """Same approver with multiple APPROVED reviews produces one claim."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(number=30)
        reviews = [
            _make_review("APPROVED", "alice", "LGTM"),
            _make_review("APPROVED", "alice", "looks good to me"),
        ]
        claims = pr_to_claims(pr_payload, reviews)

        approval_claims = [c for c in claims if c.get("claim_type") == "approval"]
        alice_claims = [c for c in approval_claims if c["metadata"].get("approver") == "alice"]
        assert len(alice_claims) == 1  # deduplicated

    def test_gh_refs_in_body_produce_linkage_claims(self):
        """PR body with GitHub refs (#99) produces linkage claims."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(
            number=40,
            body="Closes #99 and implements #100",
        )
        claims = pr_to_claims(pr_payload, [])

        linkage_claims = [c for c in claims if c.get("claim_type") == "linkage"]
        assert len(linkage_claims) >= 1

    def test_gh_refs_parsed_as_mentions_and_implements(self):
        """References preceded by 'closes/fixes' are tagged as 'implements'."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(
            number=41,
            body="Closes #99",
        )
        claims = pr_to_claims(pr_payload, [])

        linkage_claims = [c for c in claims if c.get("claim_type") == "linkage"]
        assert len(linkage_claims) >= 1
        impl_claims = [c for c in linkage_claims if c["metadata"].get("relation") == "implements"]
        assert len(impl_claims) >= 1

    def test_labels_produce_tag_claims(self):
        """Labels on the PR produce tag claims."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(
            number=50,
            labels=[
                {"name": "enhancement", "color": "84b6eb"},
                {"name": "p0", "color": "red"},
            ],
        )
        claims = pr_to_claims(pr_payload, [])

        tag_claims = [c for c in claims if c.get("claim_type") == "tag"]
        label_names = {c["metadata"].get("label") for c in tag_claims}
        assert "enhancement" in label_names
        assert "p0" in label_names

    def test_milestone_produces_context_claim(self):
        """When milestone is set, a context claim is produced."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(
            number=60,
            milestone={"number": 3, "title": "v1.2"},
        )
        claims = pr_to_claims(pr_payload, [])

        ctx_claims = [c for c in claims if c.get("claim_type") == "context"]
        assert len(ctx_claims) >= 1
        assert "v1.2" in str(ctx_claims[0]["text"])

    def test_empty_body_does_not_raise(self):
        """Empty/null body is handled gracefully."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(body="")
        claims = pr_to_claims(pr_payload, [])

        assert isinstance(claims, list)

    def test_claims_ordered_stable(self):
        """Claim order is deterministic (always same order for same input)."""
        from vault.research.github_parsers import pr_to_claims

        pr_payload = _make_pr_payload(
            number=70,
            labels=[{"name": "bug", "color": "f00"}],
        )
        reviews = [_make_review("APPROVED", "alice")]
        claims1 = pr_to_claims(pr_payload, reviews)
        claims2 = pr_to_claims(pr_payload, reviews)

        assert [c["claim_type"] for c in claims1] == [c["claim_type"] for c in claims2]


# ---------------------------------------------------------------------------
# Test: GitHubParsers high-level integration
# ---------------------------------------------------------------------------

class TestGitHubParsersIntegration:
    """Full round-trip: fetch → parse → claims."""

    def test_full_pipeline_produces_claims(self):
        """fetch_pr_with_reviews → pr_to_claims produces non-empty claims."""
        from vault.research.github_parsers import GitHubParsers, pr_to_claims

        pr_json = '{"number":80,"title":"feat: full round-trip","body":"Closes #1","merged":true,"user":{"login":"dev"},"base":{"repo":{"full_name":"living/test"}},"state":"closed","labels":[{"name":"enhancement","color":"84b6eb"}],"merged_at":"2026-04-14T10:00:00Z","created_at":"2026-04-13T09:00:00Z"}'
        reviews_json = '[{"state":"APPROVED","user":{"login":"alice"},"body":"LGTM"}]'

        def run_side(cmd, *a, **kw):
            m = MagicMock(returncode=0)
            m.stdout = reviews_json if "reviews" in str(cmd) else pr_json
            return m

        with patch("subprocess.run", side_effect=run_side):
            fetched = GitHubParsers.fetch_pr_with_reviews(80, "living/test")
            claims = pr_to_claims(fetched["pr"], fetched["reviews"])

        assert len(claims) > 0
        assert all(c["source"] == "github" for c in claims)
        assert any(c.get("claim_type") == "approval" for c in claims)
