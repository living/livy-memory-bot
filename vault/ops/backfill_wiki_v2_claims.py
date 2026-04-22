#!/usr/bin/env python3
"""
Backfill Wiki v2 claims for all historically processed events.

Usage:
    # Dry-run (no writes)
    python3 vault/ops/backfill_wiki_v2_claims.py --dry-run

    # Real backfill (writes claims + blob)
    python3 vault/ops/backfill_wiki_v2_claims.py

    # Single source
    python3 vault/ops/backfill_wiki_v2_claims.py --source=github
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure vault is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vault.research.state_store import load_state, save_state
from vault.research.github_client import GitHubClient
from vault.research.trello_client import TrelloClient
from vault.research.tldv_client import TLDVClient
from vault.research.pipeline import ResearchPipeline
from vault.ops.rollback import is_wiki_v2_enabled


SSOT_PATH = Path("state/identity-graph/state.json")
CLAIMS_DIR = Path("memory/vault/claims")
DRY_RUN = False


def log(msg: str) -> None:
    prefix = "[DRY-RUN] " if DRY_RUN else ""
    print(f"{prefix}{msg}")


def _claim_blob_exists(claim_id: str) -> bool:
    return (CLAIMS_DIR / f"{claim_id}.md").exists()


def backfill_github(pipeline: ResearchPipeline, events: list[dict]) -> dict[str, int]:
    """Backfill GitHub PR events into wiki v2 claims."""
    stats = {"total": 0, "skipped_no_change": 0, "written": 0, "errors": 0}
    client = GitHubClient()

    for entry in events:
        event_key = entry["key"]
        # Format: github:pr_merged:{repo}#{pr_number}  (e.g. github:pr_merged:living/livy-memory-bot#20)
        try:
            _, _, rest = event_key.split(":", 2)
            repo_part, pr_part = rest.rsplit("#", 1)
            repo = repo_part  # full repo path like "living/livy-memory-bot"
            pr_number = int(pr_part)
        except Exception:
            log(f"  cannot parse github event_key: {event_key}")
            stats["errors"] += 1
            continue

        stats["total"] += 1

        # Fetch current PR state from GitHub API using internal method
        try:
            pr_data = client._fetch_pr_details(repo, pr_number)
        except Exception as e:
            log(f"  fetch PR {repo}#{pr_number} failed: {e}")
            stats["errors"] += 1
            continue

        if not pr_data:
            log(f"  PR {repo}#{pr_number} returned no data (may be deleted)")
            stats["skipped_no_change"] += 1
            continue

        # Normalize to the same shape the polling client produces
        event = {
            "event_type": "pr_merged",
            "repo": repo,
            "pr_number": pr_number,
            "event_at": entry["event_at"],
        }

        try:
            result = pipeline._process_wiki_v2_github_event(event, pr_data)
            if result.get("claims_written", 0) > 0:
                log(f"  github: wrote {result['claims_written']} claim(s) for {event_key}")
                stats["written"] += result["claims_written"]
            else:
                stats["skipped_no_change"] += 1
        except Exception as e:
            log(f"  process_wiki_v2_github_event error for {event_key}: {e}")
            stats["errors"] += 1

    return stats


def backfill_trello(pipeline: ResearchPipeline, events: list[dict]) -> dict[str, int]:
    """Backfill Trello card events into wiki v2 claims.

    Trello event_keys in SSOT are action_ids (e.g. trello:abc123).
    We fetch all current cards from Trello and map by card_id,
    then backfill claims for each unique card referenced.
    """
    stats = {"total": 0, "skipped_no_change": 0, "written": 0, "errors": 0}
    client = TrelloClient()

    # Collect unique card_ids from event_keys
    # Format: trello:{action_id}  (action_id = 24-char hex)
    seen_cards: set[str] = set()
    for entry in events:
        event_key = entry["key"]
        parts = event_key.split(":", 1)
        if len(parts) < 2:
            continue
        action_id = parts[1].strip()
        # action_ids are 24-char hex strings
        if len(action_id) == 24 and all(c in "0123456789abcdef" for c in action_id):
            seen_cards.add(action_id)

    log(f"  Trello: {len(events)} events, {len(seen_cards)} unique action_ids")

    # Fetch all current cards from all boards
    try:
        cards = client.get_normalized_cards(last_seen_at=None)
    except Exception as e:
        log(f"  get_normalized_cards() failed: {e}")
        stats["errors"] = len(seen_cards)
        return stats

    # Build card_id -> ParsedTrelloCard lookup
    card_map: dict[str, ParsedTrelloCard] = {}
    for card in cards:
        if card.card_id:
            card_map[card.card_id] = card

    log(f"  Trello: fetched {len(cards)} cards from boards, {len(card_map)} mappable")

    # For each seen action_id, find the corresponding card
    for action_id in seen_cards:
        stats["total"] += 1

        # We don't know which card this action belongs to without the full action data.
        # Heuristic: look for cards whose lastActivity matches the event_at.
        # If no match, try to backfill from action data directly.
        # Simple fallback: try to use the card from board data as-is.
        matched_card = None
        for card in cards:
            if card.card_id == action_id:
                matched_card = card
                break

        if not matched_card:
            # Action_id is not a card_id - likely a real action_id.
            # We can't easily get the card state for a historical action.
            # Skip with a note.
            log(f"  trello: action_id {action_id} not found as card_id in current board state (may be old/archived)")
            stats["skipped_no_change"] += 1
            continue

        card_id = matched_card.card_id
        event = {
            "event_type": "trello:card_updated",
            "card_id": card_id,
            "card_name": matched_card.name,
            "card_url": matched_card.url,
            "board_id": matched_card.board_id,
            "github_links": matched_card.github_links,
            "labels": matched_card.labels,
            "due_date": matched_card.due_date,
            "list_id": matched_card.list_id,
            "timestamp": matched_card.last_activity,
            "event_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            result = pipeline._process_wiki_v2_trello_event(event)
            if result.get("claims_written", 0) > 0:
                log(f"  trello: wrote {result['claims_written']} claim(s) for card {card_id}")
                stats["written"] += result["claims_written"]
            else:
                stats["skipped_no_change"] += 1
        except Exception as e:
            log(f"  process_wiki_v2_trello_event error for card {card_id}: {e}")
            stats["errors"] += 1

    return stats


def backfill_tldv(pipeline: ResearchPipeline, events: list[dict]) -> dict[str, int]:
    """Backfill TLDV meeting events into wiki v2 claims."""
    stats = {"total": 0, "skipped_no_change": 0, "written": 0, "errors": 0}
    client = TLDVClient()

    for entry in events:
        event_key = entry["key"]
        # Format: tldv:meeting:{meeting_id}
        try:
            _, _, meeting_id = event_key.split(":")
        except Exception:
            log(f"  cannot parse tldv event_key: {event_key}")
            stats["errors"] += 1
            continue

        stats["total"] += 1

        try:
            meeting_data = client.fetch_meeting(meeting_id)
        except Exception as e:
            log(f"  fetch_meeting {meeting_id} failed: {e}")
            stats["errors"] += 1
            continue

        if not meeting_data:
            log(f"  meeting {meeting_id} not found")
            stats["skipped_no_change"] += 1
            continue

        event = {
            "event_type": "meeting_processed",
            "meeting_id": meeting_id,
            "event_at": entry["event_at"],
        }

        try:
            result = pipeline._process_wiki_v2_tldv_event(event, meeting_data)
            if result.get("claims_written", 0) > 0:
                log(f"  tldv: wrote {result['claims_written']} claim(s) for meeting {meeting_id}")
                stats["written"] += result["claims_written"]
            else:
                stats["skipped_no_change"] += 1
        except Exception as e:
            log(f"  process_wiki_v2_tldv_event error for meeting {meeting_id}: {e}")
            stats["errors"] += 1

    return stats


def main() -> None:
    global DRY_RUN

    parser = argparse.ArgumentParser(description="Backfill Wiki v2 claims for historical events")
    parser.add_argument("--dry-run", action="store_true", help="Log what would happen without writing")
    parser.add_argument(
        "--source",
        choices=["github", "tldv", "trello", "all"],
        default="all",
        help="Source to backfill (default: all)",
    )
    parser.add_argument("--state", default=str(SSOT_PATH), help="SSOT state path")
    args = parser.parse_args()

    DRY_RUN = args.dry_run

    wiki_v2_active = is_wiki_v2_enabled()
    print(f"WIKI_V2_ENABLED={wiki_v2_active}")

    state = load_state(args.state)
    processed = state.get("processed_event_keys", {})
    existing_claims = state.get("claims", [])
    print(f"SSOT: {len(existing_claims)} existing claims")
    print(f"Events to backfill:")
    for src in ["github", "tldv", "trello"]:
        evts = processed.get(src, [])
        print(f"  {src}: {len(evts)} events")

    total_written = 0
    total_errors = 0

    sources = ["github", "tldv", "trello"] if args.source == "all" else [args.source]

    for source in sources:
        events = processed.get(source, [])
        if not events:
            continue

        print(f"\n=== Backfilling {source} ({len(events)} events) ===")

        # Create pipeline instance for this source
        research_dir = f".research/{source}"
        pipeline = ResearchPipeline(
            source=source,
            state_path=args.state,
            research_dir=research_dir,
            wiki_root=Path("memory/vault"),
        )

        if source == "github":
            s = backfill_github(pipeline, events)
        elif source == "tldv":
            s = backfill_tldv(pipeline, events)
        elif source == "trello":
            s = backfill_trello(pipeline, events)
        else:
            continue

        print(f"  → {s}")
        total_written += s.get("written", 0)
        total_errors += s.get("errors", 0)

    print(f"\n=== Summary ===")
    print(f"Claims written: {total_written}")
    print(f"Errors: {total_errors}")

    # Final state check
    final_state = load_state(args.state)
    print(f"Final claims in SSOT: {len(final_state.get('claims', []))}")


if __name__ == "__main__":
    main()
