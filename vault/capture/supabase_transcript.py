"""Supabase transcript fallback loader (segment-oriented).

This module exposes `load_segments_from_supabase(meeting_id)` to return a
normalized list[dict] of transcript segments.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _segments_from_json_payload(payload: Any) -> list[dict[str, Any]]:
    """Normalize whisper_transcript_json payload to list[dict]."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            return []
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]

    return []


def _segments_from_plain_text(text: str) -> list[dict[str, Any]]:
    """Fallback conversion from plain transcript text to segment list."""
    if not text or not text.strip():
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    return [{"text": line} for line in lines]


def load_segments_from_supabase(meeting_id: str | None) -> list[dict[str, Any]]:
    """Load transcript segments from Supabase meetings table.

    Returns list[dict], empty list when unavailable.
    """
    if not meeting_id or not str(meeting_id).strip():
        return []

    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not supabase_key:
        return []

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    params: dict[str, Any] = {
        "select": "id,whisper_transcript,whisper_transcript_json,transcript_blob_path",
        "id": f"eq.{meeting_id}",
        "limit": 1,
    }

    try:
        resp = requests.get(
            f"{supabase_url}/rest/v1/meetings",
            headers=headers,
            params=params,
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning(
            "supabase_segments_request_failed meeting_id=%s err=%s",
            meeting_id,
            exc,
        )
        return []

    if resp.status_code != 200:
        return []

    rows = resp.json() or []
    if not rows:
        return []

    row = rows[0]

    json_segments = _segments_from_json_payload(row.get("whisper_transcript_json"))
    if json_segments:
        return json_segments

    whisper_text = row.get("whisper_transcript")
    if isinstance(whisper_text, str):
        return _segments_from_plain_text(whisper_text)

    return []
