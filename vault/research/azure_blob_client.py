"""Azure Blob transcript loader for TLDV meetings."""
from __future__ import annotations

import logging
import os

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)


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
        if not self._connection_string:
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
        except Exception as exc:
            logger.warning("azure_blob_transcript_fetch_failed meeting_id=%s err=%s", meeting_id, exc)
            return None
