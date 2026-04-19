"""Tests for vault/research/supabase_transcript.py — Supabase transcript fallback loader.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.

Coverage:
- fetch transcript field from Supabase meetings table
- fallback priority: whisper_transcript -> whisper_transcript_json -> transcript_blob_path ref
- returns None when no transcript data
- handles non-200 / request exceptions gracefully
"""
from unittest.mock import MagicMock, patch


class TestSupabaseTranscriptClient:
    def test_returns_whisper_transcript_when_present(self):
        """Uses whisper_transcript as primary text fallback source."""
        from vault.research.supabase_transcript import SupabaseTranscriptClient

        fake_rows = [
            {
                "id": "meet_abc123",
                "whisper_transcript": "Olá pessoal, iniciando a daily.",
                "whisper_transcript_json": [{"text": "segmento"}],
                "transcript_blob_path": "meetings/meet_abc123.transcript.json",
            }
        ]

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = fake_rows

        with patch("requests.get", return_value=fake_response):
            client = SupabaseTranscriptClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            transcript = client.fetch_transcript("meet_abc123")

        assert transcript == "Olá pessoal, iniciando a daily."

    def test_falls_back_to_whisper_transcript_json_text_concat(self):
        """If whisper_transcript is empty, joins whisper_transcript_json text fields."""
        from vault.research.supabase_transcript import SupabaseTranscriptClient

        fake_rows = [
            {
                "id": "meet_abc123",
                "whisper_transcript": "",
                "whisper_transcript_json": [
                    {"text": "Olá pessoal."},
                    {"text": "Vamos revisar os blockers."},
                ],
                "transcript_blob_path": "meetings/meet_abc123.transcript.json",
            }
        ]

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = fake_rows

        with patch("requests.get", return_value=fake_response):
            client = SupabaseTranscriptClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            transcript = client.fetch_transcript("meet_abc123")

        assert transcript == "Olá pessoal.\nVamos revisar os blockers."

    def test_returns_blob_path_ref_when_only_blob_path_exists(self):
        """If only transcript_blob_path exists, returns reference marker."""
        from vault.research.supabase_transcript import SupabaseTranscriptClient

        fake_rows = [
            {
                "id": "meet_abc123",
                "whisper_transcript": None,
                "whisper_transcript_json": None,
                "transcript_blob_path": "meetings/meet_abc123.transcript.json",
            }
        ]

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = fake_rows

        with patch("requests.get", return_value=fake_response):
            client = SupabaseTranscriptClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            transcript = client.fetch_transcript("meet_abc123")

        assert transcript == "blob_ref:meetings/meet_abc123.transcript.json"

    def test_returns_none_when_not_found(self):
        """No rows for meeting_id returns None."""
        from vault.research.supabase_transcript import SupabaseTranscriptClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = []

        with patch("requests.get", return_value=fake_response):
            client = SupabaseTranscriptClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            transcript = client.fetch_transcript("meet_not_found")

        assert transcript is None

    def test_returns_none_when_supabase_not_configured(self):
        """Missing URL/key should return None."""
        from vault.research.supabase_transcript import SupabaseTranscriptClient

        client = SupabaseTranscriptClient(supabase_url="", supabase_key="")
        assert client.fetch_transcript("meet_abc123") is None

    def test_returns_none_on_non_200_response(self):
        """Supabase non-200 returns None."""
        from vault.research.supabase_transcript import SupabaseTranscriptClient

        fake_response = MagicMock(status_code=500)
        fake_response.json.return_value = {"error": "boom"}

        with patch("requests.get", return_value=fake_response):
            client = SupabaseTranscriptClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_transcript("meet_abc123") is None

    def test_returns_none_on_request_exception(self):
        """Request exceptions are handled gracefully."""
        from vault.research.supabase_transcript import SupabaseTranscriptClient

        with patch("requests.get", side_effect=RuntimeError("network")):
            client = SupabaseTranscriptClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_transcript("meet_abc123") is None

    def test_requests_expected_columns(self):
        """Query selects transcript fields needed for fallback logic."""
        from vault.research.supabase_transcript import SupabaseTranscriptClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = []

        with patch("requests.get", return_value=fake_response) as mock_get:
            client = SupabaseTranscriptClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            client.fetch_transcript("meet_abc123")

        params = mock_get.call_args.kwargs["params"]
        assert "select" in params
        assert "whisper_transcript" in params["select"]
        assert "whisper_transcript_json" in params["select"]
        assert "transcript_blob_path" in params["select"]
