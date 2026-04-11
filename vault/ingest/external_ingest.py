"""External ingest orchestration — fetch, normalize, write meeting + card entities.

Orchestrates the full external data flow:
  1. Fetch meetings from TLDV (Supabase) + fetch cards from Trello
  2. Resolve participants for each meeting (layered: TLDV API → Supabase → Whisper speakers)
  3. Build canonical entities with full lineage stamps
  4. Idempotent upsert to memory/vault/entities/
  5. Write person↔meeting relationships
  6. Return summary with counts

Can be run standalone or integrated into vault/pipeline.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json

from vault.ingest.meeting_ingest import (
    fetch_meetings_from_supabase,
    resolve_participants_for_meeting,
    build_meeting_entity,
    MAPPER_VERSION as MEETING_MAPPER_VERSION,
)
from vault.ingest.card_ingest import (
    fetch_and_build as fetch_cards,
    MAPPER_VERSION as CARD_MAPPER_VERSION,
)
from vault.ingest.person_ingest import participant_to_person
from vault.ingest.entity_writer import upsert_meeting, upsert_card, upsert_person
from vault.domain.normalize import build_source_record
from vault.domain.relationship_builder import build_person_meeting_edge


def run_external_ingest(
    vault_root: Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    meeting_days: int = 7,
    card_days: int = 7,
    tldv_token: str | None = None,
) -> dict[str, Any]:
    """Run external ingest: meetings + cards."""
    if vault_root is None:
        vault_root = Path(__file__).resolve().parents[2] / "memory" / "vault"

    meetings_written = 0
    meetings_skipped = 0
    meetings_resolved = 0
    persons_written = 0
    persons_skipped = 0
    cards_written = 0
    cards_skipped = 0
    relationships_written = 0
    errors: list[dict[str, Any]] = []
    skips: list[dict[str, Any]] = []

    # Stage 1 — Fetch meetings
    try:
        if verbose:
            print(f"[external-ingest] fetching meetings (lookback={meeting_days}d)...")
        raw_meetings = fetch_meetings_from_supabase(days=meeting_days)
        if verbose:
            print(f"[external-ingest] fetched {len(raw_meetings)} meetings")
    except Exception as exc:
        if verbose:
            print(f"[external-ingest] ERROR fetching meetings: {exc}")
        errors.append({"source": "tldv_meetings", "error": str(exc), "type": type(exc).__name__})
        raw_meetings = []

    # Stage 2/3/4 — Resolve participants + build meeting/person entities
    meeting_units: list[dict[str, Any]] = []
    person_by_id: dict[str, dict[str, Any]] = {}

    for raw in raw_meetings:
        meeting_id = raw.get("meeting_id") or raw.get("id") or ""

        # Stage 2 — Resolve participants
        try:
            resolution = resolve_participants_for_meeting(raw, tldv_token or "")
        except Exception as exc:
            errors.append({
                "source": "participant_resolve",
                "meeting_id": meeting_id,
                "error": str(exc),
                "type": type(exc).__name__,
            })
            meetings_skipped += 1
            skips.append({"meeting_id": meeting_id, "reason": "RESOLVE_ERROR", "tried": ["tldv_api"]})
            continue

        if resolution.get("status") == "skip":
            meetings_skipped += 1
            skips.append({
                "meeting_id": meeting_id,
                "reason": resolution.get("reason", "NO_PARTICIPANTS"),
                "tried": resolution.get("tried", []),
            })
            continue

        participants = resolution.get("participants") or []
        meetings_resolved += 1

        # Stage 3 — Build meeting entity
        try:
            meeting_entity = build_meeting_entity(raw)
        except Exception as exc:
            meetings_skipped += 1
            errors.append({
                "source": "meeting_build",
                "meeting_id": meeting_id,
                "error": str(exc),
                "type": type(exc).__name__,
            })
            continue

        # Keep resolved participants attached for downstream relationship stage
        meeting_units.append({"meeting": meeting_entity, "participants": participants})

        # Stage 4 — Build person entities
        for p in participants:
            try:
                person = participant_to_person(p, run_id="external-ingest")
                pid = person.get("id_canonical")
                if not pid:
                    continue
                person.setdefault("sources", [
                    build_source_record(
                        source_type="tldv_api",
                        source_ref=(person.get("source_keys") or ["tldv:participant:unknown"])[0],
                        mapper_version="external-ingest-person-ingest-v1",
                    )
                ])
                person_by_id[pid] = person
            except Exception as exc:
                errors.append({"source": "person_build", "error": str(exc), "type": type(exc).__name__})

    # Stage 6(a) — Persist persons before meetings
    if dry_run:
        persons_skipped += len(person_by_id)
    else:
        for person in person_by_id.values():
            try:
                _, written = upsert_person(person, vault_root)
                if written:
                    persons_written += 1
                else:
                    persons_skipped += 1
            except Exception as exc:
                errors.append({
                    "source": "person_upsert",
                    "id_canonical": person.get("id_canonical"),
                    "error": str(exc),
                    "type": type(exc).__name__,
                })

    # Stage 6(b) — Persist meetings
    for unit in meeting_units:
        entity = unit["meeting"]
        try:
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            meeting_sources = entity.get("sources") or []
            source_keys = entity.get("source_keys") or []
            for key in source_keys:
                if isinstance(key, str) and key.startswith("tldv:"):
                    meeting_sources.append(build_source_record(
                        source_type="tldv_api",
                        source_ref=key,
                        mapper_version=entity.get("lineage", {}).get("mapper_version", MEETING_MAPPER_VERSION),
                        retrieved_at=now_iso,
                    ))
                    break
            entity["sources"] = meeting_sources

            if dry_run:
                meetings_skipped += 1
                continue

            path, written = upsert_meeting(entity, vault_root)
            if written:
                meetings_written += 1
                if verbose:
                    print(f"  [meeting] written: {path.name}")
            else:
                meetings_skipped += 1
                if verbose:
                    print(f"  [meeting] skipped (exists): {path.name}")
        except Exception as exc:
            if verbose:
                print(f"  [meeting] ERROR {entity.get('id_canonical', '?')}: {exc}")
            errors.append({
                "source": "meeting_upsert",
                "id_canonical": entity.get("id_canonical"),
                "error": str(exc),
                "type": type(exc).__name__,
            })

    # Stage 5 — Build relationships
    rel_dir = vault_root / "relationships"
    rel_edges: list[dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for unit in meeting_units:
        meeting_entity = unit["meeting"]
        participants = unit["participants"]

        meeting_id = meeting_entity.get("id_canonical")
        if not meeting_id:
            continue

        meeting_source_keys = meeting_entity.get("source_keys", [])
        meeting_source_ref = next((k for k in meeting_source_keys if isinstance(k, str) and k.startswith("tldv:")), "")

        for p in participants:
            p_source_key = p.get("source_key")
            if not isinstance(p_source_key, str):
                continue
            person = participant_to_person(p, run_id="external-ingest")
            person_id = person.get("id_canonical")
            if not person_id:
                continue

            source = build_source_record(
                source_type="tldv_api",
                source_ref=meeting_source_ref or p_source_key,
                mapper_version="external-ingest-person-meeting-rel-v1",
                retrieved_at=now_iso,
            )
            try:
                edge = build_person_meeting_edge(
                    person_id=person_id,
                    meeting_id=meeting_id,
                    role="participant",
                    source=source,
                    lineage_run_id=f"run-{now_iso}-external-ingest-person-meeting-rel-v1",
                    since=meeting_entity.get("started_at"),
                )
                rel_edges.append(edge)
            except Exception as exc:
                errors.append({"source": "relationship_build", "error": str(exc), "type": type(exc).__name__})

    if rel_edges:
        if dry_run:
            relationships_written = 0
        else:
            rel_dir.mkdir(parents=True, exist_ok=True)
            rel_path = rel_dir / "person-meeting.json"
            rel_path.write_text(json.dumps({"edges": rel_edges}, ensure_ascii=False, indent=2), encoding="utf-8")
            relationships_written = len(rel_edges)

    # Cards flow unchanged
    try:
        if verbose:
            print(f"[external-ingest] fetching cards (lookback={card_days}d)...")
        card_entities, _ = fetch_cards(days=card_days)
        if verbose:
            print(f"[external-ingest] fetched {len(card_entities)} cards")
    except Exception as exc:
        if verbose:
            print(f"[external-ingest] ERROR fetching cards: {exc}")
        errors.append({"source": "trello_cards", "error": str(exc), "type": type(exc).__name__})
        card_entities = []

    for entity in card_entities:
        try:
            if dry_run:
                cards_skipped += 1
                continue

            path, written = upsert_card(entity, vault_root)
            if written:
                cards_written += 1
                if verbose:
                    print(f"  [card] written: {path.name}")
            else:
                cards_skipped += 1
                if verbose:
                    print(f"  [card] skipped (exists): {path.name}")
        except Exception as exc:
            if verbose:
                print(f"  [card] ERROR {entity.get('id_canonical', '?')}: {exc}")
            errors.append({
                "source": "card_upsert",
                "id_canonical": entity.get("id_canonical"),
                "error": str(exc),
                "type": type(exc).__name__,
            })

    return {
        "meetings_fetched": len(raw_meetings),
        "meetings_resolved": meetings_resolved,
        "meetings_skipped": meetings_skipped,
        "meetings_written": meetings_written,
        "persons_written": persons_written,
        "persons_skipped": persons_skipped,
        "relationships_written": relationships_written,
        "cards_fetched": len(card_entities),
        "cards_written": cards_written,
        "cards_skipped": cards_skipped,
        "dry_run": dry_run,
        "errors": errors,
        "skips": skips,
    }
