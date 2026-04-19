"""Tests for vault/research/tldv_client.py — TLDV polling client.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.
"""
from unittest.mock import MagicMock, patch

import pytest


class TestTLDVClientFetchEventsSince:
    def test_returns_normalized_meeting_events(self):
        """fetch_events_since returns normalized tldv:meeting events."""
        from vault.research.tldv_client import TLDVClient

        fake_rows = [
            {
                "id": "meet_abc123",
                "name": "Daily 2026-04-14",
                "created_at": "2026-04-14T10:00:00Z",
                "updated_at": "2026-04-14T11:00:00Z",
            }
        ]

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = fake_rows

        with patch("requests.get", return_value=fake_response):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            events = client.fetch_events_since("2026-04-13T00:00:00Z")

        assert len(events) == 1
        ev = events[0]
        assert ev["source"] == "tldv"
        assert ev["event_type"] == "tldv:meeting"
        assert ev["meeting_id"] == "meet_abc123"
        assert ev["name"] == "Daily 2026-04-14"

    def test_returns_empty_if_supabase_env_missing(self):
        """Without URL/key configured, returns empty list."""
        from vault.research.tldv_client import TLDVClient

        # Empty strings explicitly disable credentials and must not fallback to env.
        client = TLDVClient(supabase_url="", supabase_key="")
        assert client.fetch_events_since("2026-04-13T00:00:00Z") == []

    def test_returns_empty_on_non_200_response(self):
        """Non-200 from Supabase returns empty list."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=500)
        fake_response.json.return_value = {"error": "boom"}

        with patch("requests.get", return_value=fake_response):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_events_since("2026-04-13T00:00:00Z") == []

    def test_returns_empty_on_request_exception(self):
        """Request exceptions are handled gracefully with empty list."""
        from vault.research.tldv_client import TLDVClient

        with patch("requests.get", side_effect=RuntimeError("network")):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_events_since("2026-04-13T00:00:00Z") == []

    def test_uses_updated_at_cursor_param(self):
        """When last_seen_at provided, request includes updated_at gte filter."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = []

        with patch("requests.get", return_value=fake_response) as mock_get:
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            client.fetch_events_since("2026-04-13T00:00:00Z")

        kwargs = mock_get.call_args.kwargs
        params = kwargs["params"]
        assert "updated_at" in params
        assert params["updated_at"].startswith("gte.")

    def test_no_last_seen_applies_updated_at_lookback_filter(self):
        """If no last_seen_at, client still applies updated_at gte from default lookback."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = []

        with patch("requests.get", return_value=fake_response) as mock_get:
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            client.fetch_events_since(None)

        kwargs = mock_get.call_args.kwargs
        params = kwargs["params"]
        assert "updated_at" in params
        assert params["updated_at"].startswith("gte.")


class TestTLDVClientFetchMeeting:
    def test_fetch_meeting_returns_single_normalized_item(self):
        """fetch_meeting returns one normalized meeting by id."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = [
            {
                "id": "meet_abc123",
                "name": "Daily",
                "created_at": "2026-04-14T10:00:00Z",
                "updated_at": "2026-04-14T11:00:00Z",
            }
        ]

        with patch("requests.get", return_value=fake_response):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            item = client.fetch_meeting("meet_abc123")

        assert item["meeting_id"] == "meet_abc123"
        assert item["event_type"] == "tldv:meeting"

    def test_fetch_meeting_returns_empty_when_not_found(self):
        """fetch_meeting returns empty dict when not found."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = []

        with patch("requests.get", return_value=fake_response):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_meeting("nope") == {}


class TestTLDVClientFetchMeetingTranscript:
    def test_prefers_azure_blob_transcript_when_available(self):
        """fetch_meeting_transcript should return Azure blob text first."""
        from vault.research.tldv_client import TLDVClient

        with patch(
            "vault.research.azure_blob_client.AzureBlobClient"
        ) as mock_az_cls, patch(
            "vault.research.supabase_transcript.SupabaseTranscriptClient"
        ) as mock_sb_cls:
            mock_az = mock_az_cls.return_value
            mock_sb = mock_sb_cls.return_value
            mock_az.fetch_transcript.return_value = "blob transcript"
            mock_sb.fetch_transcript.return_value = "supabase transcript"

            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            transcript = client.fetch_meeting_transcript("meet_abc")

        assert transcript == "blob transcript"
        mock_az.fetch_transcript.assert_called_once_with("meet_abc")
        mock_sb.fetch_transcript.assert_not_called()

    def test_falls_back_to_supabase_when_blob_missing(self):
        """If Azure returns None, fallback to Supabase transcript client."""
        from vault.research.tldv_client import TLDVClient

        with patch(
            "vault.research.azure_blob_client.AzureBlobClient"
        ) as mock_az_cls, patch(
            "vault.research.supabase_transcript.SupabaseTranscriptClient"
        ) as mock_sb_cls:
            mock_az = mock_az_cls.return_value
            mock_sb = mock_sb_cls.return_value
            mock_az.fetch_transcript.return_value = None
            mock_sb.fetch_transcript.return_value = "supabase transcript"

            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            transcript = client.fetch_meeting_transcript("meet_abc")

        assert transcript == "supabase transcript"
        mock_az.fetch_transcript.assert_called_once_with("meet_abc")
        mock_sb.fetch_transcript.assert_called_once_with("meet_abc")

    def test_returns_none_when_both_sources_unavailable(self):
        """If Azure and Supabase fail, returns None."""
        from vault.research.tldv_client import TLDVClient

        with patch(
            "vault.research.azure_blob_client.AzureBlobClient"
        ) as mock_az_cls, patch(
            "vault.research.supabase_transcript.SupabaseTranscriptClient"
        ) as mock_sb_cls:
            mock_az_cls.return_value.fetch_transcript.return_value = None
            mock_sb_cls.return_value.fetch_transcript.return_value = None

            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_meeting_transcript("meet_abc") is None

    def test_returns_none_when_meeting_id_empty(self):
        """Empty meeting_id returns None without calling any transcript source."""
        from vault.research.tldv_client import TLDVClient

        with patch(
            "vault.research.azure_blob_client.AzureBlobClient"
        ) as mock_az_cls, patch(
            "vault.research.supabase_transcript.SupabaseTranscriptClient"
        ) as mock_sb_cls:
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_meeting_transcript("") is None
            assert client.fetch_meeting_transcript("  ") is None

            # Neither client should be called for empty meeting_id
            mock_az_cls.assert_not_called()
            mock_sb_cls.assert_not_called()
