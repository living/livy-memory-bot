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
import sys
import hashlib
import json

from vault.domain.normalize import build_entity_with_traceability
from vault.domain.canonical_types import is_iso_date
from vault.ingest.tldv_api_client import fetch_participants_from_tldv_api

MAPPER_VERSION = "wave-c-meeting-ingest-v1"
DEFAULT_LOOKBACK_DAYS = 7


def _fetch_from_supabase(days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict[str, Any]]:
    """Fetch recent meetings from Supabase TLDV.

    Real table schema uses `id`, `name`, `created_at` (not `meeting_id`, `title`,
    `started_at`). We filter/order by `created_at` and normalize downstream.

    Reads SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY from environment.
    Returns list of raw meeting dicts.
    """
    import supabase

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("[WARN] SUPABASE_URL or key not set; skipping fetch", file=sys.stderr)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    client = supabase.create_client(url, key)
    resp = (
        client.table("meetings")
        .select("*")
        .gte("created_at", cutoff.isoformat())
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def _transcript_fallback(raw: dict[str, Any]) -> tuple[str | None, str | None]:
    """Pick transcript source with priority:
    1) transcript_blob_path
    2) whisper_transcript_json
    3) whisper_transcript

    Returns (transcript_source, transcript_ref).
    """
    blob_path = raw.get("transcript_blob_path")
    if isinstance(blob_path, str) and blob_path.strip():
        return "blob_path", blob_path.strip()

    wt_json = raw.get("whisper_transcript_json")
    if wt_json not in (None, [], ""):
        payload = json.dumps(wt_json, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
        return "inline_json", f"inline:whisper_transcript_json:{digest}"

    wt_text = raw.get("whisper_transcript")
    if isinstance(wt_text, str) and wt_text.strip():
        digest = hashlib.sha1(wt_text.encode("utf-8")).hexdigest()[:12]
        return "inline_text", f"inline:whisper_transcript:{digest}"

    return None, None


def normalize_meeting_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a TLDV meeting record to a Meeting entity.

    Produces a partial entity dict (without lineage stamps).
    Use build_entity_with_traceability() after to add lineage.

    Allowed fields per validate_meeting():
      id_canonical, meeting_id_source, title, started_at, ended_at, project_ref
    """
    meeting_id = raw.get("meeting_id") or raw.get("id")
    if not isinstance(meeting_id, str) or not meeting_id.strip():
        raise ValueError("meeting_id is required")

    title = raw.get("title") or raw.get("name") or ""
    started_at = raw.get("started_at") or raw.get("created_at")
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

    transcript_source, transcript_ref = _transcript_fallback(raw)
    if transcript_source and transcript_ref:
        entity["transcript_source"] = transcript_source
        entity["transcript_ref"] = transcript_ref

    return entity


def build_meeting_entity(
    raw: dict[str, Any],
    mapper_version: str = MAPPER_VERSION,
) -> dict[str, Any]:
    """Build a fully-stamped canonical meeting entity from a raw TLDV record."""
    entity = normalize_meeting_record(raw)
    return build_entity_with_traceability(entity, mapper_version)


def extract_participants(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract participant records from a meeting dict.

    Priority:
    1) raw['participants'] records (native participant payload)
    2) Fallback to distinct speaker labels from whisper_transcript_json
    """
    participants = raw.get("participants") or []
    meeting_id = raw.get("meeting_id") or raw.get("id") or ""
    out = []
    seen_ids: set[str] = set()

    for p in participants:
        pid = p.get("id")
        name = p.get("name") or p.get("display_name")
        if not pid and not name:
            continue
        pid = str(pid or "unknown")
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        out.append(
            {
                "id": pid,
                "name": name or "unknown",
                "email": p.get("email"),
                "github_login": p.get("github_login"),
                "source_key": f"tldv:participant:{meeting_id}:{pid}",
            }
        )

    # Fallback: infer participants from transcript speakers when participants list is empty
    if out:
        return out

    transcript_segments = raw.get("whisper_transcript_json") or []
    if not isinstance(transcript_segments, list):
        return out

    speaker_seen: set[str] = set()
    for seg in transcript_segments:
        if not isinstance(seg, dict):
            continue
        speaker = seg.get("speaker")
        if not isinstance(speaker, str) or not speaker.strip():
            continue
        normalized = speaker.strip()
        slug = "speaker-" + "-".join(normalized.lower().split())
        if slug in speaker_seen:
            continue
        speaker_seen.add(slug)
        out.append(
            {
                "id": slug,
                "name": normalized,
                "email": None,
                "github_login": None,
                "source_key": f"tldv:participant:{meeting_id}:{slug}",
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


def resolve_participants_for_meeting(raw_meeting: dict[str, Any], tldv_token: str) -> dict[str, Any]:
    """Resolve participants using layered sources for a single meeting."""
    meeting_id = raw_meeting.get("meeting_id") or raw_meeting.get("id") or ""
    tried = ["tldv_api"]

    seen_ids: set[str] = set()
    seen_names: set[str] = set()

    def _normalize_name(name: Any) -> str:
        return name.strip().lower() if isinstance(name, str) else ""

    def _merge(
        target: list[dict[str, Any]],
        pid: Any,
        name: Any,
        email: Any,
        source: str,
        source_key: str,
    ) -> None:
        participant_id = str(pid).strip() if pid not in (None, "") else None
        participant_name = name.strip() if isinstance(name, str) else ""
        if not participant_id and not participant_name:
            return

        if participant_id and participant_id in seen_ids:
            return
        norm_name = _normalize_name(participant_name)
        if norm_name and norm_name in seen_names:
            return

        if participant_id:
            seen_ids.add(participant_id)
        if norm_name:
            seen_names.add(norm_name)

        resolved_id = participant_id or f"speaker:{'-'.join(participant_name.lower().split())}"
        target.append(
            {
                "id": resolved_id,
                "name": participant_name or resolved_id,
                "email": email if isinstance(email, str) else None,
                "source_key": source_key,
                "source": source,
            }
        )

    # Layer 1 — TLDV API direct
    resolved: list[dict[str, Any]] = []
    api_result = fetch_participants_from_tldv_api(meeting_id, tldv_token)
    for p in api_result.get("participants", []) or []:
        pid = p.get("id") if isinstance(p, dict) else None
        pname = (
            (p.get("name") if isinstance(p, dict) else None)
            or (p.get("display_name") if isinstance(p, dict) else None)
            or ""
        )
        _merge(
            resolved,
            pid,
            pname,
            p.get("email") if isinstance(p, dict) else None,
            "tldv_api",
            f"tldv_api:participant:{meeting_id}:{pid or 'anon'}",
        )

    for speaker in api_result.get("speakers", []) or []:
        if not isinstance(speaker, str) or not speaker.strip():
            continue
        speaker_slug = "-".join(speaker.strip().lower().split())
        _merge(
            resolved,
            None,
            speaker.strip(),
            None,
            "tldv_api",
            f"tldv_api:speaker:{meeting_id}:{speaker_slug}",
        )

    if resolved:
        return {"status": "ok", "participants": resolved}

    # Layer 2 — Supabase participants fallback
    tried.append("supabase_participants")
    for p in raw_meeting.get("participants") or []:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        pname = p.get("name") or p.get("display_name") or ""
        _merge(
            resolved,
            pid,
            pname,
            p.get("email"),
            "supabase_participants",
            f"supabase:participant:{meeting_id}:{pid or 'anon'}",
        )

    if resolved:
        return {"status": "ok", "participants": resolved}

    # Layer 3 — whisper speaker labels fallback
    tried.append("supabase_whisper_speakers")
    transcript_segments = raw_meeting.get("whisper_transcript_json") or []
    if isinstance(transcript_segments, list):
        for seg in transcript_segments:
            if not isinstance(seg, dict):
                continue
            speaker = seg.get("speaker")
            if not isinstance(speaker, str) or not speaker.strip():
                continue
            speaker = speaker.strip()
            speaker_slug = "-".join(speaker.lower().split())
            _merge(
                resolved,
                None,
                speaker,
                None,
                "supabase_whisper_speakers",
                f"supabase:whisper_speaker:{meeting_id}:{speaker_slug}",
            )

    if resolved:
        return {"status": "ok", "participants": resolved}

    return {
        "status": "skip",
        "reason": "NO_PARTICIPANTS",
        "tried": tried,
    }
