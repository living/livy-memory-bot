"""Rollback QW-2 writes by reading write_log.jsonl."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

QW2_BASE = Path(".research/qw2")
WRITE_LOG = QW2_BASE / "write_log.jsonl"
DECISIONS_DIR = Path("memory/vault/decisions")

def rollback_last(n: int, dry_run: bool = True) -> None:
    if not WRITE_LOG.exists():
        print("No write_log.jsonl found.")
        return
    entries = []
    with open(WRITE_LOG) as f:
        for line in f:
            entries.append(json.loads(line))
    to_revert = entries[-n:]
    for entry in reversed(to_revert):
        topic = Path(entry["topic"])
        if not topic.exists():
            print(f"  [SKIP] {topic} not found")
            continue
        if dry_run:
            print(f"  [DRY] Would remove last entry from {topic.name}")
        else:
            _remove_last_entry(topic, entry["source_ref"])
            print(f"  [REVERTED] {topic.name}")

    if not dry_run:
        with open(WRITE_LOG, "w") as f:
            for entry in entries[:-n]:
                f.write(json.dumps(entry) + "\n")

def _remove_last_entry(topic: Path, source_ref: str) -> None:
    """Remove the last block containing source_ref from topic file."""
    content = topic.read_text()
    lines = content.split("\n")
    new_lines = []
    skip = False
    for line in lines:
        if source_ref in line:
            skip = True
            continue
        if skip and line.startswith("### "):
            skip = False
        if not skip:
            new_lines.append(line)
    topic.write_text("\n".join(new_lines) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--last", type=int, required=True, help="Revert last N writes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rollback_last(args.last, dry_run=args.dry_run)
