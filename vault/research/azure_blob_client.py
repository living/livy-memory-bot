"""Azure Blob transcript loader for TLDV meetings.

This module provides the legacy `AzureBlobClient` class API used by
`tldv_client.py` and existing tests. For new segment-oriented code,
prefer `vault.capture.azure_blob_client.load_transcript_segments`.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_CONTAINER_NAME = "transcripts"


class AzureBlobClient:
    """Load meeting transcript blobs from Azure Storage."""

    DEFAULT_CONTAINER_NAME = "transcripts"

    def __init__(
        self,
        connection_string: str | None = None,
        container_name: str | None = None,
    ) -> None:
        self._connection_string = (
            connection_string
            if connection_string is not None
            else os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
        )
        self._container_name = container_name or self.DEFAULT_CONTAINER_NAME

    def _build_blob_path(self, meeting_id: str) -> str:
        clean_id = (meeting_id or "").lstrip("/")
        return f"meetings/{clean_id}.transcript.json"

    def fetch_transcript(self, meeting_id: str) -> str | None:
        """Download blob content and return raw text, or None if unavailable."""
        if not self._connection_string:
            return None

        try:
            from azure.storage.blob import BlobServiceClient
            from azure.core.exceptions import ResourceNotFoundError, AzureError
        except ImportError:
            return None

        blob_path = self._build_blob_path(meeting_id)
        try:
            service = BlobServiceClient.from_connection_string(self._connection_string)
            blob_client = service.get_blob_client(container=self._container_name, blob=blob_path)
            content = blob_client.download_blob().readall()

            if isinstance(content, bytes):
                return content.decode("utf-8", errors="replace")
            return str(content)
        except ResourceNotFoundError:
            return None
        except AzureError as exc:
            logger.warning(
                "azure_blob_transcript_fetch_failed meeting_id=%s err=%s",
                meeting_id,
                exc,
            )
            return None
