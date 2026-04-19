"""TLDV polling client for research pipeline.

Uses Supabase REST to fetch meetings updated within lookback window.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

DEFAULT_LOOKBACK_DAYS = 7


class TLDVClient:
    """Client for polling TLDV meeting events from Supabase."""

    def __init__(
        self,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
    ) -> None:
        self.lookback_days = lookback_days
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    def fetch_events_since(self, last_seen_at: str | None) -> list[dict[str, Any]]:
        """Fetch normalized tldv:meeting events since last_seen_at."""
        if not self.supabase_url or not self.supabase_key:
            return []

        cutoff = self._compute_cutoff(last_seen_at)
        headers = self._headers()
        params: dict[str, Any] = {
            "select": "id,name,created_at,updated_at,meeting_id",
            "order": "updated_at.desc",
            "limit": 100,
        }

        if last_seen_at:
            params["updated_at"] = f"gte.{cutoff.isoformat()}"

        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/meetings",
                headers=headers,
                params=params,
                timeout=30,
            )
            if resp.status_code != 200:
                return []
            rows = resp.json() or []
            return [self._normalize_meeting(row) for row in rows]
        except Exception:
            return []

    def fetch_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Fetch one meeting by ID and normalize it."""
        if not self.supabase_url or not self.supabase_key:
            return {}

        headers = self._headers()
        params = {
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
                return {}
            rows = resp.json() or []
            if not rows:
                return {}
            return self._normalize_meeting(rows[0])
        except Exception:
            return {}

    def _compute_cutoff(self, last_seen_at: str | None) -> datetime:
        if last_seen_at:
            return datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - timedelta(days=self.lookback_days)

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }

    def _normalize_meeting(self, row: dict[str, Any]) -> dict[str, Any]:
        meeting_id = row.get("id") or row.get("meeting_id")
        return {
            "source": "tldv",
            "event_type": "tldv:meeting",
            "meeting_id": meeting_id,
            "name": row.get("name"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "raw": row,
        }
