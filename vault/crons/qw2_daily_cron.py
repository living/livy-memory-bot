#!/usr/bin/env python3
"""
QW-2 Daily Cron — runs the QW-2 pipeline in REAL mode.
Fetches TLDV + GitHub + Trello decisions, routes, writes to topic files,
consolidates, and updates MEMORY.md.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_WS = Path(__file__).resolve().parents[2]
QW2_BASE = _WS / ".research" / "qw2"
QW2_DRY_RUN_FLAG = QW2_BASE / ".dry_run_flag"


def load_env():
    env_file = Path.home() / ".openclaw" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def is_dry_run() -> bool:
    return QW2_DRY_RUN_FLAG.exists()


def main():
    load_env()
    sys.path.insert(0, str(_WS))

    from vault.qw2.run import run
    from vault.qw2.lock import acquire_lock, release_lock
    from vault.qw2.consolidate import consolidate_topic
    from vault.qw2.update_memory_index import update_memory_index

    # Acquire lock
    if not acquire_lock():
        print("[qw2-daily] Already running, skipping.")
        return

    try:
        dry_run = is_dry_run()

        if dry_run:
            print("[qw2-daily] DRY-RUN mode — no writes")
        else:
            print("[qw2-daily] REAL mode — writing decisions")

        # Run QW-2 pipeline
        result = run(source="all", dry_run=dry_run, since_days=7)

        processed = result.get("processed", 0)
        written = result.get("written", 0)
        dedupe = result.get("skipped_dedupe", 0)
        failed = result.get("routing_failed", 0)
        dms = len(result.get("dm_candidates", []))

        print(f"[qw2-daily] processed={processed} written={written} dedupe={dedupe} routing_failed={failed} dm={dms}")

        if not dry_run:
            # Consolidate all topic files
            topics = [
                "delphos-video-vistoria.md",
                "infra.md",
                "bat-conectabot-observability.md",
                "livy-memory-agent.md",
                "general.md",
            ]
            for t in topics:
                p = _WS / "memory" / "vault" / "decisions" / t
                if p.exists():
                    try:
                        consolidate_topic(p, dry_run=False)
                    except Exception as e:
                        print(f"[qw2-daily] consolidate error {t}: {e}")

            # Update MEMORY.md
            try:
                update_memory_index()
                print("[qw2-daily] MEMORY.md updated")
            except Exception as e:
                print(f"[qw2-daily] MEMORY.md update error: {e}")

            print(f"[qw2-daily] Done — {written} decisions written")
        else:
            print(f"[qw2-daily] DRY-RUN complete — {processed} processed, {failed} need review")

    finally:
        release_lock()


if __name__ == "__main__":
    main()
