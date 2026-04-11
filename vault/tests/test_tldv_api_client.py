from unittest.mock import patch, MagicMock


class TestFetchParticipantsFromApi:
    """TDD RED: Tests define the expected contract for fetch_participants_from_tldv_api."""

    def test_returns_participants_and_speakers(self):
        """API returns participants + transcript speakers → both extracted."""
        from vault.ingest.tldv_api_client import fetch_participants_from_tldv_api

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meeting": {
                "participants": [
                    {"id": "u1", "name": "Alice", "email": "alice@example.com"},
                    {"id": "u2", "name": "Bob", "email": "bob@example.com"},
                ],
                "video": {
                    "transcript": {
                        "data": [
                            {"speaker": "Alice"},
                            {"speaker": "Bob"},
                            {"speaker": "Alice"},
                        ]
                    }
                },
            }
        }

        with patch("vault.ingest.tldv_api_client.requests.get", return_value=mock_response):
            result = fetch_participants_from_tldv_api("meeting-123", "token-abc")

        assert result["participants"] == [
            {"id": "u1", "name": "Alice", "email": "alice@example.com"},
            {"id": "u2", "name": "Bob", "email": "bob@example.com"},
        ]
        # Speakers should be distinct
        assert sorted(result["speakers"]) == ["Alice", "Bob"]
        assert result["token_expired"] is False

    def test_returns_empty_on_api_error(self):
        """API returns 500 → returns empty lists, no exception."""
        from vault.ingest.tldv_api_client import fetch_participants_from_tldv_api

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("vault.ingest.tldv_api_client.requests.get", return_value=mock_response):
            result = fetch_participants_from_tldv_api("meeting-123", "token-abc")

        assert result["participants"] == []
        assert result["speakers"] == []
        assert result["token_expired"] is False

    def test_returns_empty_on_missing_transcript(self):
        """API returns 200 but no transcript → empty speakers, still has participants."""
        from vault.ingest.tldv_api_client import fetch_participants_from_tldv_api

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meeting": {
                "participants": [
                    {"id": "u1", "name": "Alice", "email": "alice@example.com"},
                ],
                "video": {
                    # no transcript
                },
            }
        }

        with patch("vault.ingest.tldv_api_client.requests.get", return_value=mock_response):
            result = fetch_participants_from_tldv_api("meeting-123", "token-abc")

        assert result["participants"] == [
            {"id": "u1", "name": "Alice", "email": "alice@example.com"},
        ]
        assert result["speakers"] == []

    def test_returns_empty_on_connection_error(self):
        """Connection error → returns empty lists, no exception."""
        from vault.ingest.tldv_api_client import fetch_participants_from_tldv_api
        import requests

        with patch("vault.ingest.tldv_api_client.requests.get", side_effect=requests.ConnectionError()):
            result = fetch_participants_from_tldv_api("meeting-123", "token-abc")

        assert result["participants"] == []
        assert result["speakers"] == []
        assert result["token_expired"] is False


class TestTokenRefresh:
    """TDD RED: Tests for token refresh behavior."""

    def test_refreshes_on_401_and_retries(self):
        """First call → 401 → refresh token → second call → 200."""
        from vault.ingest.tldv_api_client import fetch_participants_from_tldv_api

        # First call: 401
        mock_401 = MagicMock()
        mock_401.status_code = 401

        # Second call after refresh: 200
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {
            "meeting": {
                "participants": [{"id": "u1", "name": "Alice", "email": "alice@example.com"}],
                "video": {"transcript": {"data": []}},
            }
        }

        mock_refresh_response = MagicMock()
        mock_refresh_response.status_code = 200
        mock_refresh_response.json.return_value = {"token": "new-refreshed-token"}

        get_calls = []

        def mock_get(*args, **kwargs):
            get_calls.append((args, kwargs))
            if len(get_calls) == 1:
                return mock_401
            return mock_200

        with patch("vault.ingest.tldv_api_client.requests.get", side_effect=mock_get):
            with patch("vault.ingest.tldv_api_client.refresh_tldv_token", return_value="new-refreshed-token"):
                result = fetch_participants_from_tldv_api("meeting-123", "old-token")

        assert result["participants"] == [{"id": "u1", "name": "Alice", "email": "alice@example.com"}]
        assert result["token_expired"] is False

    def test_returns_empty_if_refresh_fails(self):
        """401 → refresh fails → returns empty with token_expired=True."""
        from vault.ingest.tldv_api_client import fetch_participants_from_tldv_api

        mock_401 = MagicMock()
        mock_401.status_code = 401

        with patch("vault.ingest.tldv_api_client.requests.get", return_value=mock_401):
            with patch(
                "vault.ingest.tldv_api_client.refresh_tldv_token",
                return_value=None,
            ):
                result = fetch_participants_from_tldv_api("meeting-123", "old-token")

        assert result["participants"] == []
        assert result["speakers"] == []
        assert result["token_expired"] is True

    def test_refresh_tldv_token_returns_new_token_on_success(self):
        """Successful refresh returns new token and sets env var."""
        from vault.ingest.tldv_api_client import refresh_tldv_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "new-jwt-token"}

        with patch.dict("os.environ", {"TLDV_REFRESH_TOKEN": "my-refresh-token"}):
            with patch("vault.ingest.tldv_api_client.requests.post", return_value=mock_response) as mock_post:
                result = refresh_tldv_token()

        assert result == "new-jwt-token"
        mock_post.assert_called_once()

    def test_refresh_tldv_token_returns_none_on_failure(self):
        """Failed refresh (non-200) returns None."""
        from vault.ingest.tldv_api_client import refresh_tldv_token

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.dict("os.environ", {"TLDV_REFRESH_TOKEN": "my-refresh-token"}):
            with patch("vault.ingest.tldv_api_client.requests.post", return_value=mock_response):
                result = refresh_tldv_token()

        assert result is None
