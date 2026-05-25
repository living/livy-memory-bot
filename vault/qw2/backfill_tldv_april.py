#!/usr/bin/env python3
"""
QW-2 TLDV April Backfill — fetch TLDV decisions from Supabase for April 1-26.
Bypasses TLDV API timeout by using Supabase directly (summaries + Azure blob transcripts).
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_WS))

from vault.qw2.router import route_decision
from vault.qw2.writer import QWWriter
from vault.qw2.lock import acquire_lock, release_lock

DECISIONS_DIR = _WS / "memory" / "vault" / "decisions"
STATUS_MEETING_RE = re.compile(r"^Status\s+(KABA|BAT|BOT)", re.IGNORECASE)


def fetch_april_tldv_decisions():
    """Fetch all TLDV decisions from April 1-26 via Supabase."""
    import os
    os.environ.setdefault('SUPABASE_URL', 'https://supabase.living.locaweb.com.br')
    os.environ.setdefault('SUPABASE_SERVICE_ROLE_KEY', os.environ.get('SUPABASE_SERVICE_ROLE_KEY', ''))

    from vault.research.tldv_client import TLDVClient

    # lookback of 60d covers April 1
    client = TLDVClient(lookback_days=60)
    meetings = client.fetch_events_since(None)

    # Filter to April 1-26
    april_meetings = [
        m for m in meetings
        if '2026-04-01' <= m.get('created_at', '') <= '2026-04-26T23:59:59'
    ]

    print(f"April meetings: {len(april_meetings)}")

    decisions = []
    for meeting in april_meetings:
        name = meeting.get("name", "")
        meeting_id = meeting.get("meeting_id", "")
        created_at = meeting.get("created_at", "")
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
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                date = (dt - timedelta(hours=3)).strftime("%Y-%m-%d")
                decisions.append({
                    "text": d_text,
                    "source_ref": f"tldv:{meeting_id}",
                    "confidence": 0.92,
                    "date": date,
                    "source": "tldv",
                    "meeting_name": name,
                    "tags": summary.get("tags", []) or [],
                    "_is_status_meeting": is_status_meeting,
                })

    return decisions


def main():
    import argparse
    parser = argparse.ArgumentParser(description="QW-2 TLDV April backfill")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== QW-2 TLDV April backfill (Apr 1-26) ===\n")

    if not acquire_lock():
        print("ERROR: Lock file exists")
        sys.exit(1)

    try:
        decisions = fetch_april_tldv_decisions()
        print(f"Decisions extracted: {len(decisions)}")

        if args.dry_run:
            for d in decisions[:10]:
                print(f"  {d['date']} [{d['source_ref']}] {d['text'][:80]}")
            print(f"  ... ({len(decisions)} total)")
            return

        writer = QWWriter()
        written = 0
        deduped = 0
        failed = 0

        for d in decisions:
            result = writer.write(d)
            if result["action"] == "written":
                written += 1
            elif result["action"] == "skipped":
                deduped += 1
            else:
                failed += 1

        print(f"\nWritten: {written}, Deduped: {deduped}, Failed: {failed}")

        # Consolidate topic files
        from vault.qw2.consolidate import consolidate_topic
        topics = [
            "delphos-video-vistoria.md",
            "infra.md",
            "bat-conectabot-observability.md",
            "livy-memory-agent.md",
            "general.md",
        ]
        for t in topics:
            p = DECISIONS_DIR / t
            if p.exists():
                try:
                    stats = consolidate_topic(p, dry_run=False)
                    print(f"  {t}: {stats['entries_total']} entries, {stats['deduped']} deduped")
                except Exception as e:
                    print(f"  {t}: ERROR {e}")

        # Update MEMORY.md
        from vault.qw2.update_memory_index import update_memory_index
        update_memory_index()
        print("\nMEMORY.md updated")

        # Index to Honcho
        from vault.qw2.honcho_indexer import index_topic
        for t in topics:
            p = DECISIONS_DIR / t
            if p.exists():
                try:
                    result = index_topic(p, dry_run=False)
                    print(f"  honcho {t}: indexed={result['indexed']} superseded={result['superseded']}")
                except Exception as e:
                    print(f"  honcho {t}: ERROR {e}")

        print("\n=== Done ===")

    finally:
        release_lock()


if __name__ == "__main__":
    main()
