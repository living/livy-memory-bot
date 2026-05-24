#!/usr/bin/env python3
"""QW-2 CLI: RAW → Topic Files pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vault.qw2 import fetch_tldv, fetch_trello, fetch_github
from vault.qw2.filter import should_skip
from vault.qw2.router import route_decision
from vault.qw2.writer import QWWriter
from vault.qw2.cursor import QWCursor
from vault.research.lock_manager import acquire_lock, release_lock

QW2_BASE = Path(".research/qw2")
QW2_BASE.mkdir(parents=True, exist_ok=True)
DECISIONS_DIR = Path("memory/vault/decisions")
CONFIRMED_FLAG = QW2_BASE / ".confirmed"
LOCK_FILE = QW2_BASE / "lock"

def is_confirmed() -> bool:
    return CONFIRMED_FLAG.exists()

def confirm_run() -> None:
    CONFIRMED_FLAG.parent.mkdir(parents=True, exist_ok=True)
    CONFIRMED_FLAG.touch()

def is_auto_write_enabled() -> bool:
    """Check if auto-write is enabled (read from file, not env var)."""
    return (QW2_BASE / ".auto_write_enabled").exists()

def _send_dry_run_dm(summary: dict) -> None:
    """Send DM via OpenClaw message tool using subprocess."""
    text = f"""🔍 QW-2 dry-run result

Processed: {summary['processed']}
Written: {summary['written']} | Skipped (dedupe): {summary['skipped_dedupe']} | Skipped (filter): {summary['skipped_filter']}
Routing failed (→ DM): {summary['routing_failed']}

[✅ Confirmar — proximo run escreve] [❌ Cancelar]
"""
    dm_file = QW2_BASE / ".pending_confirmation" / "dry_run_dm.txt"
    dm_file.parent.mkdir(parents=True, exist_ok=True)
    dm_file.write_text(text)
    print(f"[QW-2] Dry-run DM saved to {dm_file}")

def run(source: str = "all", dry_run: bool = True, since_days: int = 7) -> dict:
    # Acquire lock
    if not acquire_lock(str(LOCK_FILE), ttl=10):
        print("[QW-2] Already running, skipping.")
        return {"error": "already_running"}

    try:
        summary = {
            "processed": 0, "written": 0, "skipped_dedupe": 0, "skipped_filter": 0,
            "errors": 0, "routing_failed": 0, "dm_candidates": [],
            "cursors": {}
        }

        # Always dry-run unless auto_write is enabled
        actual_dry_run = dry_run or not is_auto_write_enabled()
        if actual_dry_run:
            print("[QW-2] DRY-RUN — no writes")

        # Fetch decisions per source, track cursors
        if source in ("tldv", "all"):
            decisions, max_ts = fetch_tldv.fetch_tldv_decisions(since_days)
            _process_source("tldv", decisions, actual_dry_run, summary)
            if max_ts:
                summary["cursors"]["tldv"] = max_ts

        if source in ("trello", "all"):
            snapshots, trello_cursors = fetch_trello.fetch_trello_snapshots(since_days)
            _process_trello_snapshots(snapshots, actual_dry_run, summary)
            if trello_cursors:
                summary["cursors"]["trello"] = list(trello_cursors.values())[0] if trello_cursors else None

        if source in ("github", "all"):
            decisions, max_ts = fetch_github.fetch_github_decisions(since_days)
            _process_source("github", decisions, actual_dry_run, summary)
            if max_ts:
                summary["cursors"]["github"] = max_ts

        # Update cursors with actual API timestamps
        for src, ts in summary["cursors"].items():
            if ts:
                QWCursor(src).write(ts)

        # Save pending decisions and DM Lincoln if needed
        if summary["dm_candidates"]:
            try:
                from vault.qw3.pending_dm import save_pending
                for d in summary["dm_candidates"]:
                    save_pending(d)
            except ImportError:
                pass  # QW-3 not ready yet
            if actual_dry_run:
                _send_dry_run_dm(summary)

        return summary
    finally:
        release_lock(str(LOCK_FILE))

def _process_source(source: str, decisions: list, dry_run: bool, summary: dict) -> None:
    writer = QWWriter()
    for decision in decisions:
        summary["processed"] += 1
        skip, reason = should_skip(decision)
        if skip:
            summary["skipped_filter"] += 1
            continue
        routed = route_decision(decision)
        decision["topic"] = routed["topic"]
        if routed.get("routing_failed"):
            if decision.get("confidence", 0) < 0.85:
                summary["routing_failed"] += 1
                summary["dm_candidates"].append(decision)
            else:
                print(f"  [WARN] {source}: high-conf decision routed to general: {decision['text'][:60]}")
            continue
        topic_path = DECISIONS_DIR / routed["topic"]
        if dry_run:
            print(f"  [DRY] {source}: {decision['text'][:60]} → {routed['topic']}")
        else:
            written = writer.write(topic_path, decision)
            if written:
                summary["written"] += 1
                print(f"  [WROTE] {source}: {decision['text'][:60]}")
            else:
                summary["skipped_dedupe"] += 1

def _process_trello_snapshots(snapshots: list, dry_run: bool, summary: dict) -> None:
    """Process Trello snapshots — no should_skip, routing via board_name."""
    writer = QWWriter()
    for snap in snapshots:
        summary["processed"] += 1
        routed = route_decision(snap)
        snap["topic"] = routed["topic"]
        if routed.get("routing_failed"):
            summary["routing_failed"] += 1
            summary["dm_candidates"].append(snap)
            continue
        topic_path = DECISIONS_DIR / routed["topic"]
        if dry_run:
            print(f"  [DRY] trello: {snap['card_name'][:60]} → {routed['topic']}")
        else:
            written = writer.write(topic_path, snap)
            if written:
                summary["written"] += 1
            else:
                summary["skipped_dedupe"] += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QW-2: RAW → Topic Files")
    parser.add_argument("--source", choices=["tldv", "trello", "github", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-run", action="store_true", help="Acknowledge first-run confirmation")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    if args.confirm_run:
        confirm_run()
        print("Run confirmed. Next runs will write for real.")
    else:
        result = run(source=args.source, dry_run=args.dry_run, since_days=args.days)
        print(f"\nSummary: {result}")
