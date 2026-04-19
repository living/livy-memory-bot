from unittest.mock import patch


from vault.capture.azure_blob_client import (
    load_transcript_segments,
    _candidate_blob_paths,
    _resolve_blob_pattern,
)


def test_load_transcript_segments_tries_two_patterns_and_returns_azure_segments():
    calls = []

    def fake_download_blob_json(**kwargs):
        calls.append(kwargs["blob_path"])
        if kwargs["blob_path"] == "meetings/m123.transcript.tldv.json":
            return {"segments": [{"text": "ok"}]}
        return None

    with patch.dict(
        "os.environ",
        {
            "AZURE_STORAGE_ACCOUNT_NAME": "acc",
            "AZURE_STORAGE_ACCOUNT_KEY": "key",
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

    assert calls == [
        "meetings/m123.transcript.json",
        "meetings/m123.transcript.tldv.json",
    ]
    assert segments == [{"text": "ok"}]


def test_load_transcript_segments_falls_back_to_supabase_when_azure_missing():
    with patch.dict(
        "os.environ",
        {
            "AZURE_STORAGE_ACCOUNT_NAME": "acc",
            "AZURE_STORAGE_ACCOUNT_KEY": "key",
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


def test_candidate_blob_paths_default_patterns():
    """Default: consolidated pattern first, then original pattern."""
    with patch.dict("os.environ", {}, clear=True):
        paths = _candidate_blob_paths("meet-abc")
    assert paths == [
        "meetings/meet-abc.transcript.json",
        "meetings/meet-abc.transcript.tldv.json",
    ]


def test_candidate_blob_paths_custom_consolidated_pattern():
    """AZURE_TRANSCRIPT_CONSOLIDATED_PATTERN overrides first path."""
    with patch.dict(
        "os.environ",
        {"AZURE_TRANSCRIPT_CONSOLIDATED_PATTERN": "raw/{meeting_id}/final.json"},
    ):
        paths = _candidate_blob_paths("meet-abc")
    assert paths[0] == "raw/meet-abc/final.json"
    assert paths[1] == "meetings/meet-abc.transcript.tldv.json"


def test_candidate_blob_paths_custom_original_pattern():
    """AZURE_TRANSCRIPT_ORIGINAL_PATTERN overrides second path."""
    with patch.dict(
        "os.environ",
        {"AZURE_TRANSCRIPT_ORIGINAL_PATTERN": "raw/{id}/original.json"},
    ):
        paths = _candidate_blob_paths("meet-abc")
    assert paths[0] == "meetings/meet-abc.transcript.json"
    assert paths[1] == "raw/meet-abc/original.json"


def test_candidate_blob_paths_both_custom():
    """Both pattern env vars can be overridden independently."""
    with patch.dict(
        "os.environ",
        {
            "AZURE_TRANSCRIPT_CONSOLIDATED_PATTERN": "processed/{meeting_id}/consolidated.json",
            "AZURE_TRANSCRIPT_ORIGINAL_PATTERN": "raw/{id}/raw.json",
        },
    ):
        paths = _candidate_blob_paths("xyz-99")
    assert paths == [
        "processed/xyz-99/consolidated.json",
        "raw/xyz-99/raw.json",
    ]


def test_resolve_blob_pattern_with_meeting_id_placeholder():
    assert _resolve_blob_pattern("meetings/{meeting_id}.json", "abc") == "meetings/abc.json"
    assert _resolve_blob_pattern("{meeting_id}/transcript.json", "abc") == "abc/transcript.json"


def test_resolve_blob_pattern_with_id_placeholder():
    assert _resolve_blob_pattern("meetings/{id}.json", "abc") == "meetings/abc.json"
    assert _resolve_blob_pattern("{id}/transcript.json", "abc") == "abc/transcript.json"


def test_resolve_blob_pattern_strips_leading_slash():
    assert _resolve_blob_pattern("meetings/{meeting_id}.json", "  /abc  ") == "meetings/abc.json"
