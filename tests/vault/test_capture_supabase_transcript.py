from unittest.mock import MagicMock, patch


from vault.capture.supabase_transcript import load_segments_from_supabase


def test_load_segments_from_supabase_prefers_json_segments():
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = [
        {
            "id": "m1",
            "whisper_transcript": "linha ignorada",
            "whisper_transcript_json": [{"text": "a"}, {"text": "b"}],
            "transcript_blob_path": "meetings/m1.transcript.json",
        }
    ]

    with patch.dict("os.environ", {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}), patch(
        "vault.capture.supabase_transcript.requests.get", return_value=fake_response
    ):
        segments = load_segments_from_supabase("m1")

    assert segments == [{"text": "a"}, {"text": "b"}]


def test_load_segments_from_supabase_falls_back_to_plain_text_lines():
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = [
        {
            "id": "m1",
            "whisper_transcript": "linha 1\n\nlinha 2",
            "whisper_transcript_json": None,
            "transcript_blob_path": None,
        }
    ]

    with patch.dict("os.environ", {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}), patch(
        "vault.capture.supabase_transcript.requests.get", return_value=fake_response
    ):
        segments = load_segments_from_supabase("m1")

    assert segments == [{"text": "linha 1"}, {"text": "linha 2"}]


def test_load_segments_from_supabase_returns_empty_on_empty_meeting_id():
    assert load_segments_from_supabase("") == []


def test_load_segments_from_supabase_returns_empty_on_request_exception():
    with patch.dict("os.environ", {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}), patch(
        "vault.capture.supabase_transcript.requests.get", side_effect=RuntimeError("boom")
    ):
        segments = load_segments_from_supabase("m1")

    assert segments == []
