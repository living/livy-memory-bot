"""
Test vault/ingest/github_ingest.py — org/repo allowlist enforcement.
RED: module does not exist yet.
GREEN: implement is_repo_in_scope and build_pr_query.
REFACTOR: extract helper constants, clean up.
"""
import pytest
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Module import (fails until RED step is complete)
# ---------------------------------------------------------------------------

@pytest.fixture
def gh():
    import importlib.util
    from pathlib import Path

    module_path = Path(__file__).resolve().parents[1] / "ingest" / "github_ingest.py"
    spec = importlib.util.spec_from_file_location("github_ingest", module_path)
    gh_mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(gh_mod)
    return gh_mod


# ---------------------------------------------------------------------------
# is_repo_in_scope
# ---------------------------------------------------------------------------

class TestIsRepoInScope:

    # org_allowlist only
    def test_repo_in_org_allowlist_is_allowed(self, gh):
        result = gh.is_repo_in_scope(
            "living/livy-tldv-jobs",
            org_allowlist=["living"],
            repo_allowlist=None,
            repo_denylist=None,
        )
        assert result is True

    def test_repo_not_in_org_allowlist_is_rejected(self, gh):
        result = gh.is_repo_in_scope(
            "other-org/some-repo",
            org_allowlist=["living"],
            repo_allowlist=None,
            repo_denylist=None,
        )
        assert result is False

    def test_case_insensitive_org_match(self, gh):
        result = gh.is_repo_in_scope(
            "LIVING/livy-tldv-jobs",
            org_allowlist=["living"],
            repo_allowlist=None,
            repo_denylist=None,
        )
        assert result is True

    # repo_allowlist takes priority over org_allowlist
    def test_repo_allowlist_overrides_org_allowlist(self, gh):
        # living/tldv-jobs is in repo_allowlist but not in org_allowlist
        # repo_allowlist is higher priority → allow
        result = gh.is_repo_in_scope(
            "not-living/tldv-jobs",
            org_allowlist=["living"],
            repo_allowlist=["not-living/tldv-jobs"],
            repo_denylist=None,
        )
        assert result is True

    def test_repo_not_in_repo_allowlist_is_rejected(self, gh):
        result = gh.is_repo_in_scope(
            "living/livy-tldv-jobs",
            org_allowlist=["living"],
            repo_allowlist=["other/repo"],
            repo_denylist=None,
        )
        assert result is False

    def test_repo_allowlist_case_insensitive(self, gh):
        result = gh.is_repo_in_scope(
            "LIVING/livy-tldv-jobs",
            org_allowlist=None,
            repo_allowlist=["living/livy-tldv-jobs"],
            repo_denylist=None,
        )
        assert result is True

    # repo_denylist always applies
    def test_denylist_removes_allowed_repo(self, gh):
        result = gh.is_repo_in_scope(
            "living/livy-tldv-jobs",
            org_allowlist=["living"],
            repo_allowlist=None,
            repo_denylist=["living/livy-tldv-jobs"],
        )
        assert result is False

    def test_denylist_case_insensitive(self, gh):
        result = gh.is_repo_in_scope(
            "living/livy-tldv-jobs",
            org_allowlist=["living"],
            repo_allowlist=None,
            repo_denylist=["LIVING/livy-tldv-jobs"],
        )
        assert result is False

    def test_denylist_wins_over_repo_allowlist(self, gh):
        # denylist explicitly blocks something also in repo_allowlist
        result = gh.is_repo_in_scope(
            "living/livy-tldv-jobs",
            org_allowlist=None,
            repo_allowlist=["living/livy-tldv-jobs"],
            repo_denylist=["living/livy-tldv-jobs"],
        )
        assert result is False

    def test_empty_allowlists_reject_all(self, gh):
        # No org, no repo allowlist → nothing is in scope
        result = gh.is_repo_in_scope(
            "living/livy-tldv-jobs",
            org_allowlist=[],
            repo_allowlist=[],
            repo_denylist=None,
        )
        assert result is False

    def test_none_allowlists_reject_all(self, gh):
        result = gh.is_repo_in_scope(
            "living/livy-tldv-jobs",
            org_allowlist=None,
            repo_allowlist=None,
            repo_denylist=None,
        )
        assert result is False

    def test_multiple_orgs_in_allowlist(self, gh):
        result = gh.is_repo_in_scope(
            "bat-project/core",
            org_allowlist=["living", "bat-project"],
            repo_allowlist=None,
            repo_denylist=None,
        )
        assert result is True

    def test_multiple_repos_in_repo_allowlist(self, gh):
        result = gh.is_repo_in_scope(
            "living/livy-delphos-jobs",
            org_allowlist=None,
            repo_allowlist=["living/livy-tldv-jobs", "living/livy-delphos-jobs"],
            repo_denylist=None,
        )
        assert result is True

    def test_repo_denylist_wins_over_org_allowlist(self, gh):
        result = gh.is_repo_in_scope(
            "living/livy-tldv-jobs",
            org_allowlist=["living"],
            repo_allowlist=None,
            repo_denylist=["living/livy-tldv-jobs"],
        )
        assert result is False


# ---------------------------------------------------------------------------
# build_pr_query
# ---------------------------------------------------------------------------

class TestBuildPrQuery:

    def test_default_window_30_days(self, gh):
        query = gh.build_pr_query(window_days=30, date_mode="merged_at")
        assert "is:pr" in query
        assert "merged:>" in query
        # date should be ~30 days ago
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        assert cutoff in query

    def test_90_day_window(self, gh):
        query = gh.build_pr_query(window_days=90, date_mode="merged_at")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
        assert cutoff in query

    def test_180_day_window(self, gh):
        query = gh.build_pr_query(window_days=180, date_mode="merged_at")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
        assert cutoff in query

    def test_355_day_window(self, gh):
        query = gh.build_pr_query(window_days=355, date_mode="merged_at")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=355)).strftime("%Y-%m-%d")
        assert cutoff in query

    def test_created_at_date_mode(self, gh):
        query_created = gh.build_pr_query(window_days=30, date_mode="created_at")
        query_merged = gh.build_pr_query(window_days=30, date_mode="merged_at")
        assert query_created != query_merged
        assert "created:>" in query_created
        assert "merged:>" in query_merged

    def test_repo_filter_included_when_specified(self, gh):
        query = gh.build_pr_query(
            window_days=30,
            date_mode="merged_at",
            repo="living/livy-tldv-jobs",
        )
        assert "repo:living/livy-tldv-jobs" in query

    def test_query_includes_is_pr(self, gh):
        query = gh.build_pr_query(window_days=30, date_mode="merged_at")
        assert "is:pr" in query

    def test_window_days_must_be_positive(self, gh):
        with pytest.raises(ValueError):
            gh.build_pr_query(window_days=0, date_mode="merged_at")
        with pytest.raises(ValueError):
            gh.build_pr_query(window_days=-5, date_mode="merged_at")

    def test_date_mode_must_be_valid(self, gh):
        with pytest.raises(ValueError):
            gh.build_pr_query(window_days=30, date_mode="invalid_mode")

    def test_query_is_string(self, gh):
        result = gh.build_pr_query(window_days=30, date_mode="merged_at")
        assert isinstance(result, str)
        assert len(result) > 0
