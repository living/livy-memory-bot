"""Tests for vault/research/github_client.py — GitHub polling client.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestGitHubClientFetchEventsSince:
    def test_returns_normalized_pr_merged_events(self):
        """fetch_events_since returns github:pr_merged events from gh api search."""
        from vault.research.github_client import GitHubClient

        fake_pr_json = (
            '{"number":42,"title":"fix: pipeline","state":"closed",'
            '"merged_at":"2026-04-14T10:00:00Z","created_at":"2026-04-13T09:00:00Z",'
            '"user":{"login":"lincolnqjunior","id":445449},"merged":true,'
            '"repository":{"full_name":"living/livy-memory-bot"}}\n'
        )

        fake_run = MagicMock(returncode=0, stdout=fake_pr_json)

        with patch("subprocess.run", return_value=fake_run):
            # Scope to single repo so mock returns exactly 1 event
            client = GitHubClient(repos=["living/livy-memory-bot"])
            events = client.fetch_events_since("2026-04-13T00:00:00Z")

        assert len(events) == 1
        assert events[0]["event_type"] == "github:pr_merged"
        assert events[0]["pr_number"] == 42
        assert events[0]["author"]["login"] == "lincolnqjunior"
        assert events[0]["repo"] == "living/livy-memory-bot"
        assert events[0]["merged"] is True

    def test_no_last_seen_uses_default_7day_lookback(self):
        """When last_seen_at is None, uses default 7-day lookback."""
        from vault.research.github_client import GitHubClient

        fake_run = MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", return_value=fake_run) as mock_run:
            client = GitHubClient()
            client.fetch_events_since(None)
            # Should have called gh api with a date cutoff 7 days ago
            call_str = str(mock_run.call_args[0][0])
            assert "gh" in call_str
            assert "merged:>" in call_str

    def test_returns_empty_list_on_gh_failure(self):
        """On non-zero return code, returns empty list (graceful degradation)."""
        from vault.research.github_client import GitHubClient

        fake_run = MagicMock(returncode=1, stdout="", stderr="rate limit exceeded")

        with patch("subprocess.run", return_value=fake_run):
            client = GitHubClient()
            events = client.fetch_events_since("2026-04-13T00:00:00Z")

        assert events == []

    def test_returns_empty_list_on_exception(self):
        """On exception (e.g., gh not found), returns empty list."""
        from vault.research.github_client import GitHubClient

        with patch("subprocess.run", side_effect=FileNotFoundError("gh not found")):
            client = GitHubClient()
            events = client.fetch_events_since("2026-04-13T00:00:00Z")

        assert events == []

    def test_sorts_events_by_merged_at(self):
        """Events are sorted by merged_at ascending."""
        from vault.research.github_client import GitHubClient

        newer = (
            '{"number":43,"title":"newer PR","state":"closed","merged_at":"2026-04-15T10:00:00Z",'
            '"created_at":"2026-04-14T09:00:00Z","user":{"login":"lincolnq","id":1},"merged":true,'
            '"repository":{"full_name":"living/livy-memory-bot"}}\n'
        )
        older = (
            '{"number":42,"title":"older PR","state":"closed","merged_at":"2026-04-13T10:00:00Z",'
            '"created_at":"2026-04-12T09:00:00Z","user":{"login":"lincolnq","id":1},"merged":true,'
            '"repository":{"full_name":"living/livy-memory-bot"}}\n'
        )

        fake_run = MagicMock(returncode=0, stdout=newer + older)

        with patch("subprocess.run", return_value=fake_run):
            # Scope to single repo to avoid duplication
            client = GitHubClient(repos=["living/livy-memory-bot"])
            events = client.fetch_events_since("2026-04-12T00:00:00Z")

        assert len(events) == 2
        assert events[0]["pr_number"] == 42  # older first
        assert events[1]["pr_number"] == 43  # newer second

    def test_scopes_to_living_org_repos(self):
        """Search query scopes to org:living repos."""
        from vault.research.github_client import GitHubClient

        fake_run = MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", return_value=fake_run) as mock_run:
            client = GitHubClient(repos=["living/livy-memory-bot", "living/livy-bat-jobs"])
            client.fetch_events_since(None)
            # Check the first repo call has org:living and repo:living
            first_call_args = mock_run.call_args_list[0][0][0]
            q_arg = next(arg for arg in first_call_args if str(arg).startswith("q="))
            assert "org:living" in q_arg
            assert "repo:living/livy-memory-bot" in q_arg

    def test_normalize_pr_includes_all_required_fields(self):
        """Normalized event has all fields required by pipeline."""
        from vault.research.github_client import GitHubClient

        fake_pr_json = (
            '{"number":99,"title":"feat: everything","state":"closed",'
            '"merged_at":"2026-04-14T08:00:00Z","created_at":"2026-04-13T07:00:00Z",'
            '"user":{"login":"dev","id":999},"merged":true,'
            '"repository":{"full_name":"living/livy-tldv-jobs"}}\n'
        )

        fake_run = MagicMock(returncode=0, stdout=fake_pr_json)

        with patch("subprocess.run", return_value=fake_run):
            client = GitHubClient(repos=["living/livy-tldv-jobs"])
            events = client.fetch_events_since(None)

        ev = events[0]
        assert ev["source"] == "github"
        assert ev["event_type"] == "github:pr_merged"
        assert ev["pr_number"] == 99
        assert ev["title"] == "feat: everything"
        assert ev["merged_at"] == "2026-04-14T08:00:00Z"
        assert ev["created_at"] == "2026-04-13T07:00:00Z"
        assert ev["author"]["login"] == "dev"
        assert ev["repo"] == "living/livy-tldv-jobs"
        assert ev["merged"] is True


class TestGitHubClientCutoffComputation:
    def test_cutoff_from_last_seen_at(self):
        """When last_seen_at is provided, use it as cutoff (not days lookback)."""
        from vault.research.github_client import GitHubClient

        fake_run = MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", return_value=fake_run) as mock_run:
            client = GitHubClient()
            client.fetch_events_since("2026-04-13T00:00:00Z")
            # The gh api call should include merged:>2026-04-13
            call_args_str = str(mock_run.call_args)
            assert "2026-04-13" in call_args_str

    def test_cutoff_from_last_seen_at_with_z_suffix(self):
        """last_seen_at with Z suffix is handled correctly (no crash)."""
        from vault.research.github_client import GitHubClient

        fake_run = MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", return_value=fake_run) as mock_run:
            client = GitHubClient()
            # Should not raise — Z suffix parsed correctly
            client.fetch_events_since("2026-04-13T00:00:00Z")
            assert mock_run.call_count == 4  # 4 repos
