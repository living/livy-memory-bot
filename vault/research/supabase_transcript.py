"""Supabase transcript fallback loader for TLDV meetings."""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


class SupabaseTranscriptClient:
    """Fetch transcript fields from Supabase meetings table."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
    ) -> None:
        self.supabase_url = (
            supabase_url if supabase_url is not None else os.environ.get("SUPABASE_URL", "")
        )
        self.supabase_key = (
            supabase_key
            if supabase_key is not None
            else os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        )

    def fetch_transcript(self, meeting_id: str) -> str | None:
        if not self.supabase_url or not self.supabase_key or not meeting_id:
            return None

        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
        params: dict[str, Any] = {
            "select": "id,whisper_transcript,whisper_transcript_json,transcript_blob_path",
            "id": f"eq.{meeting_id}",
            "limit": 1,
        }

        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/meetings",
                headers=headers,
                params=params,
                timeout=15,
            )
            if resp.status_code != 200:
                return None

            rows = resp.json() or []
            if not rows:
                return None

            return self._extract_transcript(rows[0])
        except requests.RequestException as exc:
            logger.warning("supabase_transcript_fetch_failed meeting_id=%s err=%s", meeting_id, exc)
            return None

    def _extract_transcript(self, row: dict[str, Any]) -> str | None:
        whisper_text = row.get("whisper_transcript")
        if isinstance(whisper_text, str) and whisper_text.strip():
            return whisper_text.strip()

        whisper_json = row.get("whisper_transcript_json")
        if isinstance(whisper_json, list) and whisper_json:
            lines: list[str] = []
            for item in whisper_json:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        lines.append(text.strip())
            if lines:
                return "\n".join(lines)

        blob_path = row.get("transcript_blob_path")
        if isinstance(blob_path, str) and blob_path.strip():
            return f"blob_ref:{blob_path.strip()}"

        return None
