from unittest.mock import patch


from vault.research.tldv_client import TLDVClient


def test_tldv_client_load_transcript_segments_delegates_to_capture_module():
    client = TLDVClient(supabase_url="https://example.supabase.co", supabase_key="k")

    with patch(
        "vault.research.tldv_client.load_transcript_segments",
        return_value=[{"text": "seg"}],
    ) as mock_loader:
        result = client.load_transcript_segments("meet_1")

    assert result == [{"text": "seg"}]
    mock_loader.assert_called_once_with("meet_1")
