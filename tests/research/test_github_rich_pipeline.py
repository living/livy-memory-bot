"""Tests for vault/research/pipeline.py — GitHub rich pipeline integration.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vault.research.state_store import load_state, save_state


@pytest.fixture
def tmp_pipeline_dir(tmp_path):
    d = tmp_path / ".research" / "github"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def tmp_state_file(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({
        "processed_event_keys": {"github": [], "tldv": []},
        "last_seen_at": {"github": None, "tldv": None},
        "version": 1,
    }))
    return p


def _make_rich_github_event(pr_number: int, body: str = "Fixes #99") -> dict:
    return {
        "source": "github",
        "event_type": "github:pr_rich",
        "id": f"living/livy-memory-bot#{pr_number}",
        "pr_number": pr_number,
        "repo": "living/livy-memory-bot",
        "title": f"PR #{pr_number}",
        "body": body,
        "state": "closed",
        "merged": True,
        "merged_at": "2026-04-14T10:00:00Z",
        "created_at": "2026-04-13T09:00:00Z",
        "updated_at": "2026-04-14T10:00:00Z",
        "author": {"login": "lincolnq", "id": 445449},
        "labels": [{"name": "enhancement", "color": "84b6eb"}],
        "milestone": {"number": 1, "title": "v1"},
        "assignees": [{"login": "alice"}],
        "requested_reviewers": [{"login": "bob"}],
        "reviews": [{"id": 1, "state": "APPROVED", "user": {"login": "alice"}, "body": "LGTM"}],
        "issue_comments": [],
        "review_comments": [],
        "linked_issues": [],
        "event_at": datetime(2026, 4, 14, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
    }


def _make_light_github_event(pr_number: int) -> dict:
    return {
        "source": "github",
        "event_type": "github:pr_merged",
        "id": f"living/livy-memory-bot#{pr_number}",
        "pr_number": pr_number,
        "repo": "living/livy-memory-bot",
        "title": f"PR #{pr_number}",
        "merged": True,
        "merged_at": "2026-04-14T10:00:00Z",
        "created_at": "2026-04-13T09:00:00Z",
        "author": {"login": "lincolnq", "id": 445449},
    }


class TestGitHubRichPipelineIntegration:
    """Tests for pipeline using GitHubRichClient for enrichment."""

    def test_pipeline_uses_rich_client_for_enrichment(self, tmp_state_file, tmp_pipeline_dir):
        """Pipeline calls GitHubRichClient.normalize_rich_event for github events."""
        from vault.research.pipeline import ResearchPipeline

        rich_client_mock = MagicMock()
        rich_client_mock.normalize_rich_event.return_value = _make_rich_github_event(42)

        with patch("vault.research.pipeline.GitHubClient") as mock_light, \
             patch("vault.research.pipeline.GitHubRichClient", return_value=rich_client_mock):

            mock_light_client = MagicMock()
            mock_light_client.fetch_events_since.return_value = [
                _make_light_github_event(42),
            ]
            mock_light_client.fetch_pr.return_value = {"number": 42, "author": {"login": "lincolnq"}}
            mock_light.return_value = mock_light_client

            pipeline = ResearchPipeline(
                source="github",
                state_path=tmp_state_file,
                research_dir=tmp_pipeline_dir,
            )
            pipeline.run()

        # Verify rich client was called with PR number + repo from lightweight event path
        rich_client_mock.normalize_rich_event.assert_called_once_with(42, "living/livy-memory-bot")

    def test_rich_payload_reaches_context_builder(self, tmp_state_file, tmp_pipeline_dir):
        """Rich payload flows through _build_context for enrichment."""
        from vault.research.pipeline import ResearchPipeline

        rich_event = _make_rich_github_event(42)

        with patch("vault.research.pipeline.GitHubClient") as mock_light, \
             patch("vault.research.pipeline.GitHubRichClient") as mock_rich:

            mock_light_client = MagicMock()
            mock_light_client.fetch_events_since.return_value = [rich_event]
            mock_light_client.fetch_pr.return_value = {"number": 42, "author": {"login": "lincolnq"}}
            mock_light.return_value = mock_light_client

            rich_instance = MagicMock()
            rich_instance.normalize_rich_event.return_value = rich_event
            mock_rich.return_value = rich_instance

            pipeline = ResearchPipeline(
                source="github",
                state_path=tmp_state_file,
                research_dir=tmp_pipeline_dir,
            )

            with patch.object(pipeline, "_build_context", wraps=pipeline._build_context) as mock_ctx:
                pipeline.run()
                # Context was called with the rich payload
                calls = [c for c in mock_ctx.call_args_list]
                assert len(calls) >= 1
                payloads = [call.args[0] for call in calls if call.args]
                assert any(isinstance(p, dict) and p.get("event_type") == "github:pr_rich" for p in payloads)
                assert any(isinstance(p, dict) and p.get("body") == rich_event["body"] for p in payloads)

    def test_crosslink_hypotheses_include_github_relations(self, tmp_state_file, tmp_pipeline_dir):
        """_build_github_hypothesis emits crosslink hypotheses for Trello and GitHub refs."""
        from vault.research.pipeline import ResearchPipeline

        # Event with Trello URL and GitHub issue reference
        rich_event = _make_rich_github_event(
            pr_number=42,
            body="Implements #99. See trello.com/c/ABC123 for design.",
        )

        with patch("vault.research.pipeline.GitHubClient") as mock_light, \
             patch("vault.research.pipeline.GitHubRichClient"):

            mock_light_client = MagicMock()
            mock_light_client.fetch_events_since.return_value = [rich_event]
            mock_light_client.fetch_pr.return_value = {"number": 42, "author": {"login": "lincolnq"}}
            mock_light.return_value = mock_light_client

            pipeline = ResearchPipeline(
                source="github",
                state_path=tmp_state_file,
                research_dir=tmp_pipeline_dir,
            )

            hypothesis = pipeline._build_github_hypothesis(rich_event)

        # Should produce at least one crosslink hypothesis
        assert "crosslinks" in hypothesis or "hypotheses" in hypothesis or "relations" in hypothesis

    def test_state_backfill_fetches_historical_prs(self, tmp_state_file, tmp_pipeline_dir):
        """Backfill mode fetches all PR states (open, closed, merged)."""
        from vault.research.pipeline import ResearchPipeline

        # Save a recent last_seen_at to trigger backfill behavior
        save_state({
            "processed_event_keys": {"github": []},
            "last_seen_at": {"github": "2026-04-01T00:00:00Z"},
            "version": 1,
        }, tmp_state_file)

        with patch("vault.research.pipeline.GitHubClient") as mock_light, \
             patch("vault.research.pipeline.GitHubRichClient"):

            mock_light_client = MagicMock()
            # Simulate no recent events (backfill needed)
            mock_light_client.fetch_events_since.return_value = []
            mock_light.return_value = mock_light_client

            pipeline = ResearchPipeline(
                source="github",
                state_path=tmp_state_file,
                research_dir=tmp_pipeline_dir,
            )
            result = pipeline.run()

        # Pipeline completes without error in backfill scenario
        assert result["status"] == "success"


class TestBuildGitHubHypothesis:
    """Tests for _build_github_hypothesis method."""

    def test_build_github_hypothesis_method_exists(self, tmp_state_file, tmp_pipeline_dir):
        """_build_github_hypothesis is defined on ResearchPipeline."""
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        assert hasattr(pipeline, "_build_github_hypothesis")
        assert callable(pipeline._build_github_hypothesis)

    def test_hypothesis_extracts_trello_urls(self, tmp_state_file, tmp_pipeline_dir):
        """Hypothesis contains Trello card references from body."""
        from vault.research.pipeline import ResearchPipeline

        event = _make_rich_github_event(
            pr_number=1,
            body="Design: https://trello.com/c/XYZ789",
        )

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        result = pipeline._build_github_hypothesis(event)

        # Check result structure
        assert isinstance(result, dict)
        # Either embedded in result or as a crosslinks list
        result_str = json.dumps(result)
        assert "XYZ789" in result_str

    def test_hypothesis_extracts_github_issue_refs(self, tmp_state_file, tmp_pipeline_dir):
        """Hypothesis contains GitHub issue references from body."""
        from vault.research.pipeline import ResearchPipeline

        event = _make_rich_github_event(
            pr_number=2,
            body="Closes #42 and fixes owner/repo#99",
        )

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        result = pipeline._build_github_hypothesis(event)

        result_str = json.dumps(result)
        assert "#42" in result_str or "42" in result_str
        assert "#99" in result_str or "99" in result_str

    def test_hypothesis_includes_review_approval(self, tmp_state_file, tmp_pipeline_dir):
        """Hypothesis reflects approval state from reviews."""
        from vault.research.pipeline import ResearchPipeline

        event = _make_rich_github_event(pr_number=3)
        event["reviews"] = [
            {"id": 1, "state": "APPROVED", "user": {"login": "alice"}, "body": "LGTM"}
        ]

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        result = pipeline._build_github_hypothesis(event)

        result_str = json.dumps(result)
        assert "APPROVED" in result_str or "approved" in result_str

    def test_hypothesis_creates_evidence_page(self, tmp_state_file, tmp_pipeline_dir):
        """Hypothesis produces a create_page action for the event."""
        from vault.research.pipeline import ResearchPipeline

        event = _make_rich_github_event(pr_number=5)

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        result = pipeline._build_github_hypothesis(event)

        assert result.get("action") in ("create_page", "upsert_page", "create_evidence")
        assert "path" in result
        assert "content" in result
