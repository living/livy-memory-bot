"""Tests for vault/research/github_rich_client.py — GitHub rich PR client.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.
"""
from unittest.mock import MagicMock, patch

import pytest


class TestGitHubRichClientSchema:
    """Tests for GitHubRichClient rich field fetching."""

    def test_fetches_pr_with_body_and_all_metadata(self):
        """fetch_rich_pr returns body, labels, milestone, assignees, requested_reviewers."""
        from vault.research.github_rich_client import GitHubRichClient

        full_pr_json = """{
            "number": 42,
            "title": "feat: rich PR body",
            "body": "Fixes #99 and references Trello card",
            "state": "closed",
            "draft": false,
            "merged": true,
            "merged_at": "2026-04-14T10:00:00Z",
            "created_at": "2026-04-13T09:00:00Z",
            "updated_at": "2026-04-14T10:00:00Z",
            "user": {"login": "lincolnq", "id": 445449},
            "base": {"ref": "main", "repo": {"full_name": "living/livy-memory-bot"}},
            "head": {"ref": "feat/rich", "repo": {"full_name": "living/livy-memory-bot"}},
            "labels": [
                {"name": "enhancement", "color": "84b6eb"}
            ],
            "milestone": {"number": 3, "title": "v1.2"},
            "assignees": [{"login": "alice"}],
            "requested_reviewers": [{"login": "bob"}]
        }"""

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=full_pr_json)):
            client = GitHubRichClient()
            pr = client.fetch_rich_pr(42, "living/livy-memory-bot")

        assert pr["body"] == "Fixes #99 and references Trello card"
        assert pr["labels"] == [{"name": "enhancement", "color": "84b6eb"}]
        assert pr["milestone"] == {"number": 3, "title": "v1.2"}
        assert pr["assignees"] == [{"login": "alice"}]
        assert pr["requested_reviewers"] == [{"login": "bob"}]

    def test_fetches_reviews_with_approval_state(self):
        """fetch_reviews returns all reviews with state (APPROVED, CHANGES_REQUESTED, etc)."""
        from vault.research.github_rich_client import GitHubRichClient

        reviews_json = """[
            {"id": 1, "state": "APPROVED", "user": {"login": "alice"}, "body": "LGTM!"},
            {"id": 2, "state": "CHANGES_REQUESTED", "user": {"login": "bob"}, "body": "nits"}
        ]"""

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=reviews_json)):
            client = GitHubRichClient()
            reviews = client.fetch_reviews(42, "living/livy-memory-bot")

        assert len(reviews) == 2
        states = {r["state"] for r in reviews}
        assert "APPROVED" in states
        assert "CHANGES_REQUESTED" in states

    def test_fetches_issue_comments(self):
        """fetch_issue_comments returns all issue-level comments."""
        from vault.research.github_rich_client import GitHubRichClient

        comments_json = """[
            {"id": 10, "user": {"login": "dev"}, "body": "Please add tests"},
            {"id": 11, "user": {"login": "alice"}, "body": "Done"}
        ]"""

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=comments_json)):
            client = GitHubRichClient()
            comments = client.fetch_issue_comments(42, "living/livy-memory-bot")

        assert len(comments) == 2
        assert comments[0]["id"] == 10

    def test_fetches_review_comments(self):
        """fetch_review_comments returns all PR review comments (line/file comments)."""
        from vault.research.github_rich_client import GitHubRichClient

        review_comments_json = """[
            {"id": 20, "user": {"login": "bob"}, "body": "use const"}
        ]"""

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=review_comments_json)):
            client = GitHubRichClient()
            comments = client.fetch_review_comments(42, "living/livy-memory-bot")

        assert len(comments) == 1
        assert comments[0]["id"] == 20

    def test_fetches_labels(self):
        """Labels are included in the rich PR response."""
        from vault.research.github_rich_client import GitHubRichClient

        pr_json = """{
            "number": 5, "title": "t", "body": "b",
            "user": {"login": "x"},
            "base": {"repo": {"full_name": "living/livy-memory-bot"}},
            "labels": [{"name": "p0", "color": "red"}, {"name": "bug", "color": "f00"}]
        }"""

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=pr_json)):
            client = GitHubRichClient()
            pr = client.fetch_rich_pr(5, "living/livy-memory-bot")

        assert len(pr["labels"]) == 2
        label_names = {l["name"] for l in pr["labels"]}
        assert "p0" in label_names
        assert "bug" in label_names

    def test_fetches_milestone(self):
        """Milestone is included when present, null when absent."""
        from vault.research.github_rich_client import GitHubRichClient

        pr_with_ms = '{"number":1,"title":"t","body":"b","user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"milestone":{"number":7,"title":"v2"}}'
        pr_without_ms = '{"number":2,"title":"t","body":"b","user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"milestone":null}'

        def run_side(cmd, *a, **kw):
            m = MagicMock(returncode=0)
            m.stdout = pr_with_ms if "pulls/1" in str(cmd) else pr_without_ms
            return m

        with patch("subprocess.run", side_effect=run_side):
            client = GitHubRichClient()
            pr1 = client.fetch_rich_pr(1, "living/livy-memory-bot")
            pr2 = client.fetch_rich_pr(2, "living/livy-memory-bot")

        assert pr1["milestone"] == {"number": 7, "title": "v2"}
        assert pr2["milestone"] is None

    def test_fetches_assignees_and_requested_reviewers(self):
        """Both assignees and requested_reviewers are captured."""
        from vault.research.github_rich_client import GitHubRichClient

        pr_json = """{
            "number": 6, "title": "t", "body": "b", "user": {"login": "x"},
            "base": {"repo": {"full_name": "living/livy-memory-bot"}},
            "assignees": [{"login": "alice"}, {"login": "bob"}],
            "requested_reviewers": [{"login": "carol"}]
        }"""

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=pr_json)):
            client = GitHubRichClient()
            pr = client.fetch_rich_pr(6, "living/livy-memory-bot")

        assert len(pr["assignees"]) == 2
        assert len(pr["requested_reviewers"]) == 1
        assert pr["requested_reviewers"][0]["login"] == "carol"

    def test_fetches_linked_issues_via_graphql(self):
        """fetch_linked_issues uses GraphQL crossReferences."""
        from vault.research.github_rich_client import GitHubRichClient

        graphql_response = """{
            "data": {
                "repository": {
                    "pullRequest": {
                        "crossReferences": {
                            "nodes": [
                                {"target": {"__typename": "Issue", "number": 99, "title": "Bug report"}}
                            ]
                        }
                    }
                }
            }
        }"""

        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=graphql_response)):
            client = GitHubRichClient()
            issues = client.fetch_linked_issues(42, "living/livy-memory-bot")

        assert len(issues) == 1
        assert issues[0]["number"] == 99
        assert issues[0]["title"] == "Bug report"

    def test_pr_event_includes_all_rich_fields(self):
        """normalize_rich_event produces complete event with all rich fields."""
        from vault.research.github_rich_client import GitHubRichClient

        pr_json = """{
            "number": 7, "title": "feat: all fields", "body": "Body text",
            "state": "closed", "draft": false, "merged": true,
            "merged_at": "2026-04-14T10:00:00Z",
            "created_at": "2026-04-13T09:00:00Z",
            "updated_at": "2026-04-14T10:00:00Z",
            "user": {"login": "dev"}, "base": {"repo": {"full_name": "living/livy-memory-bot"}},
            "labels": [{"name": "enhancement", "color": "84b6eb"}],
            "milestone": {"number": 1, "title": "v1"},
            "assignees": [{"login": "alice"}],
            "requested_reviewers": [{"login": "bob"}]
        }"""
        reviews_json = """[{"id": 1, "state": "APPROVED", "user": {"login": "alice"}, "body": "ok"}]"""
        issue_comments_json = """[{"id": 10, "user": {"login": "dev"}, "body": "comment"}]"""
        review_comments_json = """[{"id": 20, "user": {"login": "bob"}, "body": "review comment"}]"""
        linked_issues_json = """{"data": {"repository": {"pullRequest": {"crossReferences": {"nodes": [{"target": {"__typename": "Issue", "number": 99, "title": "Issue"}}]}}}}}"""

        def run_side(cmd, *a, **kw):
            m = MagicMock(returncode=0)
            cmd_str = str(cmd)
            if "pulls/7/comments" in cmd_str:
                m.stdout = review_comments_json
            elif "issues/7/comments" in cmd_str:
                m.stdout = issue_comments_json
            elif "reviews" in cmd_str:
                m.stdout = reviews_json
            elif "graphql" in cmd_str:
                m.stdout = linked_issues_json
            else:
                m.stdout = pr_json
            return m

        with patch("subprocess.run", side_effect=run_side):
            client = GitHubRichClient()
            event = client.normalize_rich_event(7, "living/livy-memory-bot")

        assert event["source"] == "github"
        assert event["event_type"] == "github:pr_rich"
        assert event["pr_number"] == 7
        assert event["body"] == "Body text"
        assert event["labels"] == [{"name": "enhancement", "color": "84b6eb"}]
        assert event["milestone"] == {"number": 1, "title": "v1"}
        assert len(event["reviews"]) == 1
        assert len(event["issue_comments"]) == 1
        assert len(event["review_comments"]) == 1
        assert len(event["linked_issues"]) == 1
        assert len(event["assignees"]) == 1
        assert len(event["requested_reviewers"]) == 1

    def test_raw_payload_is_preserved_intact(self):
        """raw_payload() returns immutable snapshot with all original data."""
        from vault.research.github_rich_client import GitHubRichClient

        pr_json = '{"number":8,"title":"raw test","body":"original body","user":{"login":"x"},"base":{"repo":{"full_name":"r"}}}'
        reviews_json = "[{\"id\":1,\"state\":\"APPROVED\"}]"
        issue_comments_json = "[{\"id\":10}]"
        review_comments_json = "[{\"id\":20}]"
        linked_issues_json = '{"data":{"repository":{"pullRequest":{"crossReferences":{"nodes":[]}}}}}'

        def run_side(cmd, *a, **kw):
            m = MagicMock(returncode=0)
            cmd_str = str(cmd)
            if "pulls/8/comments" in cmd_str:
                m.stdout = review_comments_json
            elif "issues/8/comments" in cmd_str:
                m.stdout = issue_comments_json
            elif "reviews" in cmd_str:
                m.stdout = reviews_json
            elif "graphql" in cmd_str:
                m.stdout = linked_issues_json
            else:
                m.stdout = pr_json
            return m

        with patch("subprocess.run", side_effect=run_side):
            client = GitHubRichClient()
            client.normalize_rich_event(8, "r")
            raw = client.raw_payload()

        assert "pr" in raw
        assert "reviews" in raw
        assert "issue_comments" in raw
        assert "review_comments" in raw
        assert "linked_issues" in raw
        assert "fetched_at" in raw
        assert "pr_number" in raw
        # Original data intact
        import json
        assert json.loads(raw["pr"])["body"] == "original body"

    def test_sanitized_view_removes_duplicates(self):
        """sanitized_view() deduplicates comments with same id+hash."""
        from vault.research.github_rich_client import GitHubRichClient

        pr_json = '{"number":9,"title":"dedup test","body":"b","user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"labels":[]}'
        # Two identical comments (simulate pagination dedup)
        reviews_json = """[
            {"id":1,"state":"APPROVED","user":{"login":"alice"},"body":"LGTM"},
            {"id":1,"state":"APPROVED","user":{"login":"alice"},"body":"LGTM"}
        ]"""
        issue_comments_json = """[
            {"id":10,"user":{"login":"dev"},"body":"same"},
            {"id":10,"user":{"login":"dev"},"body":"same"}
        ]"""
        review_comments_json = "[]"
        linked_issues_json = '{"data":{"repository":{"pullRequest":{"crossReferences":{"nodes":[]}}}}}'

        def run_side(cmd, *a, **kw):
            m = MagicMock(returncode=0)
            cmd_str = str(cmd)
            if "pulls/9/comments" in cmd_str:
                m.stdout = review_comments_json
            elif "issues/9/comments" in cmd_str:
                m.stdout = issue_comments_json
            elif "reviews" in cmd_str:
                m.stdout = reviews_json
            elif "graphql" in cmd_str:
                m.stdout = linked_issues_json
            else:
                m.stdout = pr_json
            return m

        with patch("subprocess.run", side_effect=run_side):
            client = GitHubRichClient()
            client.normalize_rich_event(9, "r")
            sanitized = client.sanitized_view()

        # Deduplicated: one of each
        assert len(sanitized["reviews"]) == 1
        assert len(sanitized["issue_comments"]) == 1

    def test_all_pr_states_are_fetched(self):
        """fetch_rich_pr works for open, closed, merged PR states."""
        from vault.research.github_rich_client import GitHubRichClient

        states = ["open", "closed", "merged"]
        expected_bodies = ["open body", "closed body", "merged body"]

        def run_side(cmd, *a, **kw):
            m = MagicMock(returncode=0)
            cmd_str = str(cmd)
            # Simulate each PR with correct state
            if "pulls/1" in cmd_str:
                m.stdout = '{"number":1,"title":"open PR","body":"open body","state":"open","user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"labels":[],"assignees":[],"requested_reviewers":[]}'
            elif "pulls/2" in cmd_str:
                m.stdout = '{"number":2,"title":"closed PR","body":"closed body","state":"closed","merged":false,"user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"labels":[],"assignees":[],"requested_reviewers":[]}'
            elif "pulls/3" in cmd_str:
                m.stdout = '{"number":3,"title":"merged PR","body":"merged body","state":"closed","merged":true,"merged_at":"2026-04-14T10:00:00Z","user":{"login":"x"},"base":{"repo":{"full_name":"r"}},"labels":[],"assignees":[],"requested_reviewers":[]}'
            else:
                m.stdout = "[]"
            return m

        with patch("subprocess.run", side_effect=run_side):
            client = GitHubRichClient()
            for i, (state, body) in enumerate(zip(states, expected_bodies), 1):
                pr = client.fetch_rich_pr(i, "r")
                assert pr["body"] == body


class TestGitHubRichClientHelpers:
    """Tests for helper methods on GitHubRichClient."""

    def test_sanitize_text_removes_signature(self):
        """_sanitize_text removes co-authored-by lines."""
        from vault.research.github_rich_client import GitHubRichClient

        client = GitHubRichClient()
        text = "Great work!\n\nCo-authored-by: Alice <alice@example.com>"
        result = client._sanitize_text(text)
        assert "Co-authored-by" not in result

    def test_sanitize_text_preserves_meaningful_content(self):
        """_sanitize_text keeps issue refs, Trello URLs, and prose."""
        from vault.research.github_rich_client import GitHubRichClient

        client = GitHubRichClient()
        text = "Fixes #99. See https://trello.com/c/ABC123 for context."
        result = client._sanitize_text(text)
        assert "#99" in result
        assert "trello.com" in result

    def test_sanitize_text_collapses_blank_lines(self):
        """_sanitize_text collapses repeated newlines."""
        from vault.research.github_rich_client import GitHubRichClient

        client = GitHubRichClient()
        text = "Line 1\n\n\n\n\nLine 2"
        result = client._sanitize_text(text)
        assert result.count("\n\n\n") == 0

    def test_extract_trello_urls(self):
        """_extract_trello_urls finds Trello card and board URLs."""
        from vault.research.github_rich_client import GitHubRichClient

        client = GitHubRichClient()
        text = "See trello.com/c/ABC123 and trello.com/b/BOARD456"
        urls = client._extract_trello_urls(text)
        assert "https://trello.com/c/ABC123" in urls
        assert "https://trello.com/b/BOARD456" in urls

    def test_extract_github_refs(self):
        """_extract_github_refs finds issue and PR references."""
        from vault.research.github_rich_client import GitHubRichClient

        client = GitHubRichClient()
        text = "Implements #42. Closes owner/repo#99. See github.com/living/repo/pull/7"
        refs = client._extract_github_refs(text)
        assert "#42" in refs
        assert "owner/repo#99" in refs

    def test_extract_github_refs_from_urls(self):
        """_extract_github_refs extracts from full GitHub issue/PR URLs."""
        from vault.research.github_rich_client import GitHubRichClient

        client = GitHubRichClient()
        text = "See https://github.com/living/livy-memory-bot/issues/42"
        refs = client._extract_github_refs(text)
        assert "issues/42" in refs
