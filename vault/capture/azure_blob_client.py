"""Azure Blob transcript segment loader with Supabase fallback.

API:
    load_transcript_segments(meeting_id) -> list[dict]

Behavior:
- Uses AZURE_STORAGE_ACCOUNT and AZURE_STORAGE_KEY from env.
- Container defaults to AZURE_STORAGE_CONTAINER or "meetings".
- Tries two blob naming patterns.
- Falls back to Supabase segment loader when Azure content is missing.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from vault.capture.supabase_transcript import load_segments_from_supabase

logger = logging.getLogger(__name__)


DEFAULT_CONTAINER = "meetings"


def _candidate_blob_paths(meeting_id: str) -> list[str]:
    clean = meeting_id.strip().lstrip("/")
    return [
        f"meetings/{clean}.transcript.json",
        f"{clean}/transcript.json",
    ]


def _extract_segments(payload: Any) -> list[dict[str, Any]]:
    """Normalize Azure payload to segment list[dict]."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("segments", "transcript", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def _download_blob_json(
    *, account: str, key: str, container: str, blob_path: str
) -> Any | None:
    """Download and decode JSON payload from Azure blob path.

    Lazy-import azure dependencies to avoid import-time hard dependency.
    """
    try:
        from azure.storage.blob import BlobServiceClient
        from azure.core.exceptions import ResourceNotFoundError, AzureError
    except ImportError:
        return None

    account_url = f"https://{account}.blob.core.windows.net"

    try:
        service = BlobServiceClient(account_url=account_url, credential=key)
        blob_client = service.get_blob_client(container=container, blob=blob_path)
        content = blob_client.download_blob().readall()

        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        if isinstance(content, str):
            return json.loads(content)

        return None
    except ResourceNotFoundError:
        return None
    except (AzureError, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning(
            "azure_blob_segments_fetch_failed meeting_id_path=%s err=%s",
            blob_path,
            exc,
        )
        return None


def load_transcript_segments(meeting_id: str | None) -> list[dict[str, Any]]:
    """Load transcript segments from Azure blob, with Supabase fallback."""
    if not meeting_id or not str(meeting_id).strip():
        return []

    account = os.environ.get("AZURE_STORAGE_ACCOUNT", "").strip()
    key = os.environ.get("AZURE_STORAGE_KEY", "").strip()
    container = os.environ.get("AZURE_STORAGE_CONTAINER", DEFAULT_CONTAINER).strip() or DEFAULT_CONTAINER

    if account and key:
        for blob_path in _candidate_blob_paths(str(meeting_id)):
            payload = _download_blob_json(
                account=account,
                key=key,
                container=container,
                blob_path=blob_path,
            )
            if payload is None:
                continue

            segments = _extract_segments(payload)
            if segments:
                return segments

    return load_segments_from_supabase(str(meeting_id))
