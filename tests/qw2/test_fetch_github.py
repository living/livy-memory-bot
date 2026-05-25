"""Tests for GitHub decision fetching."""
from unittest.mock import patch, MagicMock
from vault.qw2.fetch_github import fetch_github_decisions


@patch("vault.qw2.fetch_github.GitHubClient")
def test_fetches_merged_prs(mock_client_cls):
    """GitHubClient returns normalized events directly (no 'payload' wrapper)."""
    mock_client = MagicMock()
    mock_client.fetch_events_since.return_value = [
        {
            "repo": "living/livy-memory-bot",
            "title": "feat: adicionar nova feature",
            "pr_number": 42,
            "merged_at": "2026-05-24T12:00:00Z",
        }
    ]
    mock_client_cls.return_value = mock_client

    results, max_merged = fetch_github_decisions(since_days=7)
    assert len(results) == 1
    assert results[0]["source_ref"] == "github:living/livy-memory-bot#42"
    assert max_merged == "2026-05-24T12:00:00Z"
