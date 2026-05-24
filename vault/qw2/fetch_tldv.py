"""Fetch decisions from TLDV meetings."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from vault.research.tldv_client import TLDVClient

logger = logging.getLogger(__name__)

STATUS_MEETING_RE = re.compile(r"^Status\s+(KABA|BAT|BOT)", re.IGNORECASE)

def fetch_tldv_decisions(since_days: int = 7) -> tuple[list[dict[str, Any]], str | None]:
    """
    Fetch meetings updated in last N days, extract decisions.
    Returns (decisions, max_updated_at) where max_updated_at is the latest
    meeting.updated_at for cursor update.
    """
    try:
        client = TLDVClient(lookback_days=since_days)
    except Exception as e:
        logger.warning(f"TLDV not configured: {e}")
        return [], None

    meetings = client.fetch_events_since(None)
    decisions = []
    max_updated: str | None = None

    for meeting in meetings:
        name = meeting.get("name", "")
        meeting_id = meeting.get("meeting_id", "")
        created_at = meeting.get("created_at", "")
        updated_at = meeting.get("updated_at") or created_at

        if updated_at and (max_updated is None or updated_at > max_updated):
            max_updated = updated_at

        is_status_meeting = bool(STATUS_MEETING_RE.match(name))

        summaries = client.fetch_summaries(meeting_id) or []

        for summary in summaries:
            summary_decisions = summary.get("decisions") or []
            if not isinstance(summary_decisions, list):
                continue
            for d in summary_decisions:
                d_text = str(d).strip()
                if not d_text or len(d_text) < 10:
                    continue
                decisions.append({
                    "text": d_text,
                    "source_ref": f"tldv:{meeting_id}",
                    "confidence": 0.92,
                    "date": _meeting_date(meeting),
                    "source": "tldv",
                    "meeting_name": name,
                    "tags": summary.get("tags", []) or [],
                    "_is_status_meeting": is_status_meeting,
                })

    return decisions, max_updated

def _meeting_date(meeting: dict) -> str:
    try:
        dt = datetime.fromisoformat(meeting.get("created_at", "").replace("Z", "+00:00"))
        return (dt - timedelta(hours=3)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
