"""Tests for TLDV decision fetching."""
from unittest.mock import patch, MagicMock
from vault.qw2.fetch_tldv import fetch_tldv_decisions


@patch("vault.qw2.fetch_tldv.TLDVClient")
def test_fetch_tldv_extracts_decisions(mock_client_cls):
    """TLDVClient.fetch_events_since returns meetings; fetch_summaries returns decisions."""
    mock_client = MagicMock()
    mock_client.fetch_events_since.return_value = [
        {
            "id": "m1",
            "meeting_id": "m1",
            "name": "Daily Bot",
            "created_at": "2026-05-24T12:00:00Z",
            "updated_at": "2026-05-24T14:00:00Z",
        }
    ]
    mock_client.fetch_summaries.return_value = [
        {"decisions": ["Usar GPT-4"], "tags": ["llm"]}
    ]
    mock_client_cls.return_value = mock_client

    results, max_updated = fetch_tldv_decisions(since_days=7)
    assert len(results) == 1
    assert results[0]["text"] == "Usar GPT-4"
    assert results[0]["source_ref"] == "tldv:m1"
    assert max_updated == "2026-05-24T14:00:00Z"
