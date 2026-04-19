from unittest.mock import patch


from vault.capture.azure_blob_client import load_transcript_segments


def test_load_transcript_segments_tries_two_patterns_and_returns_azure_segments():
    calls = []

    def fake_download_blob_json(**kwargs):
        calls.append(kwargs["blob_path"])
        if kwargs["blob_path"] == "m123/transcript.json":
            return {"segments": [{"text": "ok"}]}
        return None

    with patch.dict(
        "os.environ",
        {
            "AZURE_STORAGE_ACCOUNT": "acc",
            "AZURE_STORAGE_KEY": "key",
            "AZURE_STORAGE_CONTAINER": "meetings",
        },
    ), patch(
        "vault.capture.azure_blob_client._download_blob_json",
        side_effect=fake_download_blob_json,
    ), patch(
        "vault.capture.azure_blob_client.load_segments_from_supabase",
        return_value=[{"text": "fallback"}],
    ):
        segments = load_transcript_segments("m123")

    assert calls == ["meetings/m123.transcript.json", "m123/transcript.json"]
    assert segments == [{"text": "ok"}]


def test_load_transcript_segments_falls_back_to_supabase_when_azure_missing():
    with patch.dict(
        "os.environ",
        {
            "AZURE_STORAGE_ACCOUNT": "acc",
            "AZURE_STORAGE_KEY": "key",
            "AZURE_STORAGE_CONTAINER": "meetings",
        },
    ), patch(
        "vault.capture.azure_blob_client._download_blob_json",
        return_value=None,
    ), patch(
        "vault.capture.azure_blob_client.load_segments_from_supabase",
        return_value=[{"text": "from supabase"}],
    ) as mock_fallback:
        segments = load_transcript_segments("m123")

    assert segments == [{"text": "from supabase"}]
    mock_fallback.assert_called_once_with("m123")


def test_load_transcript_segments_no_azure_config_goes_direct_to_supabase():
    with patch.dict("os.environ", {}, clear=True), patch(
        "vault.capture.azure_blob_client.load_segments_from_supabase",
        return_value=[{"text": "from supabase"}],
    ) as mock_fallback:
        segments = load_transcript_segments("m123")

    assert segments == [{"text": "from supabase"}]
    mock_fallback.assert_called_once_with("m123")


def test_load_transcript_segments_empty_meeting_id_returns_empty_list():
    assert load_transcript_segments("") == []
