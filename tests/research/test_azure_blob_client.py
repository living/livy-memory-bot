"""Tests for vault/research/azure_blob_client.py — Azure Blob transcript loader.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.

Coverage:
- Azure Blob Storage connection using connection string
- Download transcript blob for a given meeting_id
- Blob path construction from meeting_id
- Graceful handling when blob does not exist (return None)
- Graceful handling on connection errors (return None)
"""
from unittest.mock import MagicMock, patch

import pytest


class TestAzureBlobClientInit:
    def test_stores_connection_string_from_env(self):
        """Connection string is read from AZURE_STORAGE_CONNECTION_STRING env var."""
        with patch.dict("os.environ", {"AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key==;"}):
            from vault.research.azure_blob_client import AzureBlobClient

            client = AzureBlobClient()
            assert client._connection_string == "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key==;"

    def test_stores_container_name_default(self):
        """Default container name is 'transcripts'."""
        from vault.research.azure_blob_client import AzureBlobClient
        assert AzureBlobClient.DEFAULT_CONTAINER_NAME == "transcripts"

    def test_accepts_explicit_connection_string_and_container(self):
        """Can override connection string and container name via constructor."""
        from vault.research.azure_blob_client import AzureBlobClient

        client = AzureBlobClient(
            connection_string="DefaultEndpointsProtocol=https;AccountName=explicit;AccountKey=key==;",
            container_name="custom-container",
        )
        assert client._container_name == "custom-container"


class TestAzureBlobClientBlobPath:
    def test_builds_blob_path_for_meeting_id(self):
        """Blob path format: meetings/{meeting_id}.transcript.json"""
        from vault.research.azure_blob_client import AzureBlobClient

        client = AzureBlobClient(connection_string="conn_str", container_name="transcripts")
        path = client._build_blob_path("meet_abc123")
        assert path == "meetings/meet_abc123.transcript.json"

    def test_builds_blob_path_strips_leading_slash(self):
        """If meeting_id starts with /, it is stripped before building path."""
        from vault.research.azure_blob_client import AzureBlobClient

        client = AzureBlobClient(connection_string="conn_str", container_name="transcripts")
        path = client._build_blob_path("/meet_abc123")
        assert path == "meetings/meet_abc123.transcript.json"


class TestAzureBlobClientFetchTranscript:
    def test_returns_transcript_text_on_success(self):
        """When blob exists, download_blob().readall() returns the blob text."""
        from vault.research.azure_blob_client import AzureBlobClient

        fake_blob_content = '{"transcript": "Hello everyone."}'
        client = AzureBlobClient(connection_string="conn_str", container_name="transcripts")

        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value.readall.return_value = fake_blob_content.encode("utf-8")

        # Patch _load_azure_clients to return our mock classes
        fake_blob_service_cls = MagicMock()
        fake_blob_service_cls.from_connection_string.return_value.get_blob_client.return_value = mock_blob_client

        with patch.object(client, "_load_azure_clients", return_value=(fake_blob_service_cls, (Exception,))):
            result = client.fetch_transcript("meet_abc123")

        assert result == fake_blob_content

    def test_returns_none_when_blob_not_found(self):
        """Azure ResourceNotFoundError returns None."""
        from vault.research.azure_blob_client import AzureBlobClient

        client = AzureBlobClient(connection_string="conn_str", container_name="transcripts")
        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.side_effect = FileNotFoundError("not found")

        fake_blob_service_cls = MagicMock()
        fake_blob_service_cls.from_connection_string.return_value.get_blob_client.return_value = mock_blob_client

        # Patch _load_azure_clients with azure_exceptions tuple containing our test exception
        with patch.object(client, "_load_azure_clients", return_value=(fake_blob_service_cls, (FileNotFoundError,))):
            result = client.fetch_transcript("meet_not_exist")

        assert result is None

    def test_returns_none_on_connection_error(self):
        """Connection errors (e.g. invalid creds) return None."""
        from vault.research.azure_blob_client import AzureBlobClient

        client = AzureBlobClient(connection_string="invalid_conn_str", container_name="transcripts")

        fake_blob_service_cls = MagicMock()
        fake_blob_service_cls.from_connection_string.side_effect = RuntimeError("connection failed")

        with patch.object(client, "_load_azure_clients", return_value=(fake_blob_service_cls, (Exception,))):
            result = client.fetch_transcript("meet_abc123")

        assert result is None

    def test_returns_none_when_connection_string_empty(self):
        """Empty connection string returns None without calling Azure."""
        from vault.research.azure_blob_client import AzureBlobClient

        client = AzureBlobClient(connection_string="", container_name="transcripts")
        result = client.fetch_transcript("meet_abc123")
        assert result is None

    def test_returns_none_when_meeting_id_empty(self):
        """Empty meeting_id returns None without calling Azure."""
        from vault.research.azure_blob_client import AzureBlobClient

        client = AzureBlobClient(connection_string="conn_str", container_name="transcripts")
        with patch.object(client, "_load_azure_clients") as mock_loader:
            assert client.fetch_transcript("") is None
            assert client.fetch_transcript("   ") is None
            mock_loader.assert_not_called()

    def test_passes_correct_container_to_blob_service(self):
        """BlobServiceClient is initialized with correct container."""
        from vault.research.azure_blob_client import AzureBlobClient

        client = AzureBlobClient(
            connection_string="conn_str",
            container_name="my-transcripts",
        )

        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value.readall.return_value = b'{"x":1}'

        fake_blob_service_cls = MagicMock()
        fake_blob_service_cls.from_connection_string.return_value.get_blob_client.return_value = mock_blob_client

        with patch.object(client, "_load_azure_clients", return_value=(fake_blob_service_cls, (Exception,))):
            client.fetch_transcript("meet_abc")

        # Verify from_connection_string was called with the connection string
        fake_blob_service_cls.from_connection_string.assert_called_once_with("conn_str")
        # Verify get_blob_client called with correct container and blob path
        fake_blob_service_cls.from_connection_string.return_value.get_blob_client.assert_called_once_with(
            container="my-transcripts",
            blob="meetings/meet_abc.transcript.json",
        )
