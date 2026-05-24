from unittest.mock import patch, MagicMock
from vault.qw2.fetch_github import fetch_github_decisions

@patch("vault.qw2.fetch_github.GitHubClient")
def test_fetches_merged_prs(mock_client_cls):
    mock_client = MagicMock()
    mock_client.fetch_events_since.return_value = [
        {
            "repo": "living/livy-memory-bot",
            "payload": {
                "title": "feat: adicionar nova feature",
                "body": "Esta PR implementa o sistema de decisions.",
                "number": 42,
                "merged_at": "2026-05-24T12:00:00Z",
                "url": "https://github.com/living/livy-memory-bot/pull/42",
            }
        }
    ]
    mock_client_cls.return_value = mock_client

    results, max_merged = fetch_github_decisions(since_days=7)
    assert len(results) == 1
    assert results[0]["source_ref"] == "github:living/livy-memory-bot#42"
    assert max_merged == "2026-05-24T12:00:00Z"
