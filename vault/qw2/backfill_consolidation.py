#!/usr/bin/env python3
"""
QW-2 Consolidation Backfill — consolidate all topic files for historical periods.
Deduplicates intra-file, fact-checks entries, updates MEMORY.md.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_WS))

from vault.qw2.consolidate import consolidate_topic
from vault.qw2.update_memory_index import update_memory_index

TOPICS = [
    "delphos-video-vistoria.md",
    "infra.md",
    "bat-conectabot-observability.md",
    "livy-memory-agent.md",
    "general.md",
]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="QW-2 consolidation backfill")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"=== Consolidation backfill {'(DRY-RUN)' if args.dry_run else '(REAL)'} ===\n")

    total_deduped = 0
    total_entries = 0

    for topic in TOPICS:
        path = _WS / "memory" / "vault" / "decisions" / topic
        if not path.exists():
            print(f"  [SKIP] {topic} — not found")
            continue

        stats = consolidate_topic(path, dry_run=args.dry_run)
        total_deduped += stats["deduped"]
        total_entries += stats["entries_total"]
        print(f"  {topic}: {stats['entries_total']} entries, "
              f"{stats['deduped']} deduped, {stats['fact_checked']} fact_checked, "
              f"{stats['written']} written")

    if not args.dry_run:
        update_memory_index()
        print(f"\n  MEMORY.md updated")

    print(f"\n=== Total: {total_entries} entries, {total_deduped} deduped ===")


if __name__ == "__main__":
    main()
