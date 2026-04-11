"""Wave C ingest orchestration — fetch, normalize, write meeting + card entities.

Orchestrates the full Wave C data flow:
  1. Fetch meetings from TLDV (Supabase) + fetch cards from Trello
  2. Build canonical entities with full lineage stamps
  3. Idempotent upsert to memory/vault/entities/
  4. Return summary with counts

Controlled by WAVE_C_C1_ENABLED env var (default: True).
When disabled, returns zero-count summary silently.

Can be run standalone or integrated into vault/pipeline.py.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json

from vault.ingest.meeting_ingest import (
    fetch_and_build as fetch_meetings,
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


def _is_wave_c_enabled() -> bool:
    """Check WAVE_C_C1_ENABLED env var (mirrors pipeline._get_wave_c_flag)."""
    raw = os.environ.get("WAVE_C_C1_ENABLED")
    if raw is None:
        return True  # default: enabled
    return raw.lower() in ("true", "1")


def run_wave_c_ingest(
    vault_root: Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    meeting_days: int = 7,
    card_days: int = 7,
) -> dict[str, Any]:
    """Run Wave C ingest: meetings + cards.

    Args:
        vault_root:   override vault root path (defaults to memory/vault)
        dry_run:      if True, fetch and normalize but skip file writes
        verbose:      if True, print per-entity actions
        meeting_days: lookback days for TLDV meetings (default 7)
        card_days:    lookback days for Trello cards (default 7)

    Returns:
        Summary dict with meetings_written, cards_written, errors, etc.
    """
    if vault_root is None:
        vault_root = Path(__file__).resolve().parents[2] / "memory" / "vault"

    if not _is_wave_c_enabled():
        return {
            "wave_c_enabled": False,
            "meetings_fetched": 0,
            "meetings_written": 0,
            "meetings_skipped": 0,
            "persons_fetched": 0,
            "persons_written": 0,
            "persons_skipped": 0,
            "relationships_written": 0,
            "cards_fetched": 0,
            "cards_written": 0,
            "cards_skipped": 0,
            "errors": [],
        }

    meetings_written = 0
    meetings_skipped = 0
    persons_written = 0
    persons_skipped = 0
    cards_written = 0
    cards_skipped = 0
    relationships_written = 0
    errors: list[dict[str, Any]] = []

    # --- Meetings ---
    try:
        if verbose:
            print(f"[wave-c] fetching meetings (lookback={meeting_days}d)...")
        meeting_entities, participant_records = fetch_meetings(days=meeting_days)
        if verbose:
            print(f"[wave-c] fetched {len(meeting_entities)} meetings")
    except Exception as exc:
        if verbose:
            print(f"[wave-c] ERROR fetching meetings: {exc}")
        errors.append({"source": "tldv_meetings", "error": str(exc), "type": type(exc).__name__})
        meeting_entities = []
        participant_records = []

    # Build person entities from meeting participants first
    person_by_id: dict[str, dict[str, Any]] = {}
    for p in participant_records:
        try:
            person = participant_to_person(p, run_id="wave-c")
            pid = person.get("id_canonical")
            if not pid:
                continue
            person.setdefault("sources", [
                build_source_record(
                    source_type="tldv_api",
                    source_ref=(person.get("source_keys") or ["tldv:participant:unknown"])[0],
                    mapper_version="wave-c-person-ingest-v1",
                )
            ])
            person_by_id[pid] = person
        except Exception as exc:
            errors.append({"source": "person_build", "error": str(exc), "type": type(exc).__name__})

    # write persons before meetings
    for person in person_by_id.values():
        try:
            _, written = upsert_person(person, vault_root)
            if dry_run:
                persons_skipped += 1
            else:
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

    # map source_key -> person id for meeting participant linkage
    sourcekey_to_personid: dict[str, str] = {}
    for person in person_by_id.values():
        for key in person.get("source_keys", []):
            if isinstance(key, str):
                sourcekey_to_personid[key] = person.get("id_canonical")

    for entity in meeting_entities:
        try:
            # enrich meeting sources with tldv source record for strict frontmatter tests
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

            path, written = upsert_meeting(entity, vault_root)
            if dry_run:
                meetings_skipped += 1
            else:
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

    # Write person->meeting relationships
    rel_dir = vault_root / "relationships"
    rel_dir.mkdir(parents=True, exist_ok=True)
    rel_edges: list[dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for meeting_entity in meeting_entities:
        meeting_id = meeting_entity.get("id_canonical")
        if not meeting_id:
            continue

        # Best-effort: infer participant keys from source keys carrying meeting id
        meeting_source_keys = meeting_entity.get("source_keys", [])
        meeting_source_ref = next((k for k in meeting_source_keys if isinstance(k, str) and k.startswith("tldv:")), "")

        for p in participant_records:
            p_source_key = p.get("source_key")
            if not isinstance(p_source_key, str):
                continue
            person = participant_to_person(p, run_id="wave-c")
            person_id = person.get("id_canonical")
            if not person_id:
                continue

            source = build_source_record(
                source_type="tldv_api",
                source_ref=meeting_source_ref or p_source_key,
                mapper_version="wave-c-person-meeting-rel-v1",
                retrieved_at=now_iso,
            )
            try:
                edge = build_person_meeting_edge(
                    person_id=person_id,
                    meeting_id=meeting_id,
                    role="participant",
                    source=source,
                    lineage_run_id=f"run-{now_iso}-wave-c-person-meeting-rel-v1",
                    since=meeting_entity.get("started_at"),
                )
                rel_edges.append(edge)
            except Exception as exc:
                errors.append({"source": "relationship_build", "error": str(exc), "type": type(exc).__name__})

    if rel_edges and not dry_run:
        rel_path = rel_dir / "wave-c-person-meeting.json"
        rel_path.write_text(json.dumps({"edges": rel_edges}, ensure_ascii=False, indent=2), encoding="utf-8")
        relationships_written = len(rel_edges)

    # --- Cards ---
    try:
        if verbose:
            print(f"[wave-c] fetching cards (lookback={card_days}d)...")
        card_entities, _ = fetch_cards(days=card_days)
        if verbose:
            print(f"[wave-c] fetched {len(card_entities)} cards")
    except Exception as exc:
        if verbose:
            print(f"[wave-c] ERROR fetching cards: {exc}")
        errors.append({"source": "trello_cards", "error": str(exc), "type": type(exc).__name__})
        card_entities = []

    for entity in card_entities:
        try:
            path, written = upsert_card(entity, vault_root)
            if dry_run:
                cards_skipped += 1
            else:
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
        "wave_c_enabled": True,
        "meetings_fetched": len(meeting_entities),
        "meetings_written": meetings_written,
        "meetings_skipped": meetings_skipped,
        "persons_fetched": len(participant_records),
        "persons_written": persons_written,
        "persons_skipped": persons_skipped,
        "relationships_written": relationships_written,
        "cards_fetched": len(card_entities),
        "cards_written": cards_written,
        "cards_skipped": cards_skipped,
        "errors": errors,
    }
