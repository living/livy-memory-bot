"""TLDV participant ingestion → canonical person entities.

Wave B contract:
- Default lookback window = 30 days
- Build person payloads with source_keys + lineage
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any


def from_recent_meetings(meetings: list[dict[str, Any]], days: int = 30) -> list[dict[str, Any]]:
    """Filter meetings by started_at within lookback window.

    Args:
        meetings: list of TLDV meeting dicts
        days: lookback window in days (default 30)
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for meeting in meetings:
        started = meeting.get("started_at")
        if not started:
            continue
        try:
            dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if dt >= cutoff:
            out.append(meeting)
    return out


def participant_to_person(participant: dict[str, Any], run_id: str = "wave-b") -> dict[str, Any]:
    """Convert one TLDV participant record into canonical person entity payload."""
    email = participant.get("email")
    display_name = participant.get("name") or participant.get("display_name") or "unknown"
    github_login = participant.get("github_login")
    source_key = participant.get("source_key") or f"tldv:participant:{participant.get('id', display_name)}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_keys = [source_key]
    if github_login:
        source_keys.append(f"github:{github_login}")

    return {
        "id_canonical": f"person:tldv:{participant.get('id', display_name).lower()}",
        "display_name": display_name,
        "github_login": github_login,
        "email": email,
        "source_keys": source_keys,
        "first_seen_at": participant.get("first_seen_at", now),
        "last_seen_at": participant.get("last_seen_at", now),
        "confidence": participant.get("confidence", "medium"),
        "lineage": {
            "run_id": run_id,
            "source_keys": source_keys,
            "transformed_at": now,
            "mapper_version": "wave-b-person-ingest-v1",
            "actor": "livy-agent",
        },
    }
