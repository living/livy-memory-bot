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

from vault.ingest.meeting_ingest import (
    fetch_and_build as fetch_meetings,
    MAPPER_VERSION as MEETING_MAPPER_VERSION,
)
from vault.ingest.card_ingest import (
    fetch_and_build as fetch_cards,
    MAPPER_VERSION as CARD_MAPPER_VERSION,
)
from vault.ingest.entity_writer import upsert_meeting, upsert_card


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
            "cards_fetched": 0,
            "cards_written": 0,
            "errors": [],
        }

    meetings_written = 0
    meetings_skipped = 0
    cards_written = 0
    cards_skipped = 0
    errors: list[dict[str, Any]] = []

    # --- Meetings ---
    try:
        if verbose:
            print(f"[wave-c] fetching meetings (lookback={meeting_days}d)...")
        meeting_entities, _ = fetch_meetings(days=meeting_days)
        if verbose:
            print(f"[wave-c] fetched {len(meeting_entities)} meetings")
    except Exception as exc:
        if verbose:
            print(f"[wave-c] ERROR fetching meetings: {exc}")
        errors.append({"source": "tldv_meetings", "error": str(exc), "type": type(exc).__name__})
        meeting_entities = []

    for entity in meeting_entities:
        try:
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
        "cards_fetched": len(card_entities),
        "cards_written": cards_written,
        "cards_skipped": cards_skipped,
        "errors": errors,
    }
