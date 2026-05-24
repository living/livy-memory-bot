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
from vault.qw2.lock import acquire_lock, release_lock

QW2_BASE = Path(".research/qw2")
QW2_BASE.mkdir(parents=True, exist_ok=True)
DECISIONS_DIR = Path("memory/vault/decisions")
CONFIRMED_FLAG = QW2_BASE / ".confirmed"

CURSOR_FILES = {
    "tldv": QW2_BASE / "last_seen_tldv.json",
    "github": QW2_BASE / "last_seen_github.json",
    "trello": QW2_BASE / "last_seen_trello.json",
}
WRITTEN_REFS = QW2_BASE / "written_refs.json"
WRITE_LOG = QW2_BASE / "write_log.jsonl"

def do_reset(which: set[str]) -> None:
    """Reset cursor files and/or dedupe files."""
    if "all" in which or "tldv" in which:
        CURSOR_FILES["tldv"].unlink(missing_ok=True)
    if "all" in which or "github" in which:
        CURSOR_FILES["github"].unlink(missing_ok=True)
    if "all" in which or "trello" in which:
        CURSOR_FILES["trello"].unlink(missing_ok=True)
    if "all" in which or "dedupe" in which:
        WRITTEN_REFS.unlink(missing_ok=True)
        WRITE_LOG.unlink(missing_ok=True)


def is_confirmed() -> bool:
    return CONFIRMED_FLAG.exists()

def confirm_run() -> None:
    CONFIRMED_FLAG.parent.mkdir(parents=True, exist_ok=True)
    CONFIRMED_FLAG.touch()

def is_auto_write_enabled() -> bool:
    """Check if auto-write is enabled (read from file, not env var)."""
    return (QW2_BASE / ".auto_write_enabled").exists()

def _send_dry_run_dm(summary: dict) -> None:
    """Write DM content listing all pending decisions for Lincoln's review."""
    lines = [
        f"🔍 QW-2 dry-run — {summary['processed']} decisões processadas\n",
        f"📝 Escritas: {summary['written']} | Duplicadas: {summary['skipped_dedupe']} | Filtradas: {summary['skipped_filter']}\n",
        f"⚠️ Routings falhados (→ revisão): {summary['routing_failed']}\n",
        "---",
        "**Decisões pendentes de revisão:**",
    ]
    for d in summary.get("dm_candidates", []):
        conf = d.get("confidence", 0)
        text = d.get("text", "")[:80]
        source = d.get("source", "?").upper()
        topic = d.get("topic", "unknown")
        lines.append(f"• [{source}] {text}")
        lines.append(f"  → {topic} (conf: {conf:.0%})")

    lines.append("---")
    lines.append("**[✅ Confirmar — próximo run escreve]** | **[❌ Cancelar]**")

    text = "\n".join(lines)

    dm_file = QW2_BASE / ".pending_confirmation" / "dry_run_dm.txt"
    dm_file.parent.mkdir(parents=True, exist_ok=True)
    dm_file.write_text(text)
    print(f"[QW-2] Dry-run DM saved to {dm_file}")
    dm_file = QW2_BASE / ".pending_confirmation" / "dry_run_dm.txt"
    dm_file.parent.mkdir(parents=True, exist_ok=True)
    dm_file.write_text(text)
    print(f"[QW-2] Dry-run DM saved to {dm_file}")

def run(source: str = "all", dry_run: bool = True, since_days: int = 7) -> dict:
    # Acquire lock (using vault.qw2.lock module)
    if not acquire_lock():
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
        release_lock()

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
            summary["routing_failed"] += 1
            summary["dm_candidates"].append(decision)
            if not dry_run:
                print(f"  [DM] {source}: {decision['text'][:60]} → review pending")
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
    from datetime import datetime, timezone
    writer = QWWriter()
    for snap in snapshots:
        summary["processed"] += 1
        # Enrich with fields required by writer
        if "date" not in snap:
            snap["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if "confidence" not in snap:
            snap["confidence"] = 0
        if "text" not in snap:
            snap["text"] = snap.get("card_name", "")
        if "tags" not in snap:
            snap["tags"] = []
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
    parser.add_argument("--reset", action="store_true", help="Hard reset: clears cursors + written_refs + dedupe refs")
    parser.add_argument("--reset-cursors", action="store_true", help="Clear only cursors (keep dedupe)")
    parser.add_argument("--reset-dedupe", action="store_true", help="Clear only dedupe refs (keep cursors)")
    parser.add_argument("--reset-tldv", action="store_true", help="Clear only TLDV cursor + dedupe refs")
    parser.add_argument("--reset-github", action="store_true", help="Clear only GitHub cursor + dedupe refs")
    parser.add_argument("--reset-trello", action="store_true", help="Clear only Trello cursor + dedupe refs")
    args = parser.parse_args()

    # Handle reset flags
    if args.reset:
        do_reset({"all"})
        print("Reset: cleared all cursors + written_refs + write_log")
    elif args.reset_cursors:
        do_reset({"tldv", "github", "trello"})
        print("Reset: cleared all cursors")
    elif args.reset_dedupe:
        do_reset({"dedupe"})
        print("Reset: cleared dedupe refs")
    elif args.reset_tldv:
        do_reset({"tldv", "dedupe"})
        print("Reset: cleared TLDV cursor + dedupe")
    elif args.reset_github:
        do_reset({"github", "dedupe"})
        print("Reset: cleared GitHub cursor + dedupe")
    elif args.reset_trello:
        do_reset({"trello", "dedupe"})
        print("Reset: cleared Trello cursor + dedupe")

    if args.confirm_run:
        confirm_run()
        print("Run confirmed. Next runs will write for real.")
    else:
        result = run(source=args.source, dry_run=args.dry_run, since_days=args.days)
        print(f"\nSummary: {result}")
