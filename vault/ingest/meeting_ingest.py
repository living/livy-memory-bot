"""TLDV meeting ingestion → canonical meeting entities.

Phase C1 contract:
- Read from TLDV/Supabase (meetings table)
- Lookback: 7 days
- Output: canonical meeting entities with full lineage
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any
import os

from vault.domain.normalize import build_entity_with_traceability
from vault.domain.canonical_types import is_iso_date

MAPPER_VERSION = "wave-c-meeting-ingest-v1"
DEFAULT_LOOKBACK_DAYS = 7


def _fetch_from_supabase(days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict[str, Any]]:
    """Fetch recent meetings from Supabase TLDV.

    Reads SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY from environment.
    Returns list of raw meeting dicts.
    """
    import supabase

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("[WARN] SUPABASE_URL or key not set; skipping fetch")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    client = supabase.create_client(url, key)
    resp = (
        client.table("meetings")
        .select("*")
        .gte("started_at", cutoff.isoformat())
        .order("started_at", desc=True)
        .execute()
    )
    return resp.data or []


def normalize_meeting_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a TLDV meeting record to a Meeting entity.

    Produces a partial entity dict (without lineage stamps).
    Use build_entity_with_traceability() after to add lineage.

    Allowed fields per validate_meeting():
      id_canonical, meeting_id_source, title, started_at, ended_at, project_ref
    """
    meeting_id = raw.get("meeting_id", "")
    if not isinstance(meeting_id, str) or not meeting_id.strip():
        raise ValueError("meeting_id is required")

    title = raw.get("title", "")
    started_at = raw.get("started_at")
    ended_at = raw.get("ended_at")
    project_ref = raw.get("project_ref")

    if started_at is not None and not is_iso_date(started_at):
        raise ValueError("started_at must be ISO date/datetime")
    if ended_at is not None and not is_iso_date(ended_at):
        raise ValueError("ended_at must be ISO date/datetime")
    if project_ref is not None and not isinstance(project_ref, str):
        raise ValueError("project_ref must be string when provided")

    # id_canonical format: meeting:{normalized_id}
    # Use the raw meeting_id directly, colons replaced with hyphens
    id_canonical = f"meeting:{meeting_id.replace(':', '-')}"

    entity = {
        "id_canonical": id_canonical,
        "meeting_id_source": meeting_id,
        "title": title,
        # Keep tldv source key so idempotency remains stable after traceability stamp
        "source_keys": [f"tldv:{meeting_id}"],
    }

    if started_at is not None:
        entity["started_at"] = started_at
    if ended_at is not None:
        entity["ended_at"] = ended_at
    if project_ref is not None:
        entity["project_ref"] = project_ref

    return entity


def build_meeting_entity(
    raw: dict[str, Any],
    mapper_version: str = MAPPER_VERSION,
) -> dict[str, Any]:
    """Build a fully-stamped canonical meeting entity from a raw TLDV record."""
    entity = normalize_meeting_record(raw)
    return build_entity_with_traceability(entity, mapper_version)


def extract_participants(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract participant records from a meeting dict."""
    participants = raw.get("participants") or []
    meeting_id = raw.get("meeting_id", "")
    out = []
    for p in participants:
        pid = p.get("id")
        name = p.get("name") or p.get("display_name")
        if not pid and not name:
            continue
        pid = pid or "unknown"
        out.append(
            {
                "id": pid,
                "name": name or "unknown",
                "email": p.get("email"),
                "github_login": p.get("github_login"),
                "source_key": f"tldv:participant:{meeting_id}:{pid}",
            }
        )
    return out


def idem_key_for_meeting(entity: dict[str, Any]) -> str:
    """Return the idempotency source_key for a meeting entity.

    Returns the tldv:{meeting_id} source_key from the entity's source_keys list,
    or empty string if not present.
    """
    for key in entity.get("source_keys", []):
        if key.startswith("tldv:"):
            return key
    return ""


def fetch_and_build(
    days: int = DEFAULT_LOOKBACK_DAYS,
    mapper_version: str = MAPPER_VERSION,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch meetings from TLDV and build canonical entities + participants.

    Returns:
        (meeting_entities, participant_records)
    """
    raw_meetings = _fetch_from_supabase(days)
    entities = []
    all_participants = []
    for raw in raw_meetings:
        try:
            entity = build_meeting_entity(raw, mapper_version)
        except ValueError:
            continue
        entities.append(entity)
        participants = extract_participants(raw)
        all_participants.extend(participants)
    return entities, all_participants
