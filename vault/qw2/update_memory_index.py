#!/usr/bin/env python3
"""
Update MEMORY.md index with latest decisions from topic files.
Run after consolidate.py to keep MEMORY.md in sync.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

_WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_WS))

from vault.qw2.consolidate import parse_topic_file

MEMORY_PATH = _WS / "MEMORY.md"
DECISIONS_DIR = _WS / "memory" / "vault" / "decisions"


def build_topic_summary(path: Path) -> dict:
    """Build summary dict for a topic file."""
    entries = parse_topic_file(path)
    if not entries:
        return None
    latest = max(e["date"] for e in entries)
    topics = list(set(e["source"] for e in entries))
    return {
        "path": path,
        "name": path.stem,
        "count": len(entries),
        "latest": latest,
        "topics": topics,
    }


def update_memory_index() -> None:
    """Update MEMORY.md with latest topic file summaries."""
    summaries = []
    for p in DECISIONS_DIR.glob("*.md"):
        if p.name == ".gitkeep":
            continue
        s = build_topic_summary(p)
        if s:
            summaries.append(s)

    if not summaries:
        print("[update_memory] No entries found, skipping update")
        return

    # Sort by latest date descending
    summaries.sort(key=lambda x: x["latest"], reverse=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build new section
    new_lines = [
        "",
        "---",
        f"## QW-2 Topic Files (auto-updated {now})",
        "",
        "| Topic | Entries | Latest | Sources |",
        "|---|---|---|---|",
    ]
    for s in summaries:
        sources = ", ".join(s["topics"])
        new_lines.append(f"| `{s['name']}` | {s['count']} | {s['latest']} | {sources} |")

    # Read existing MEMORY.md
    content = MEMORY_PATH.read_text()

    # Remove old QW-2 section if exists
    marker_start = content.find("\n## QW-2 Topic Files")
    marker_end = content.find("\n---\n##", marker_start + 1) if marker_start != -1 else -1

    if marker_start != -1 and marker_end != -1:
        content = content[:marker_start] + content[marker_end:]
        print(f"[update_memory] Replaced existing QW-2 section")

    # Append new section
    content = content.rstrip() + "\n" + "\n".join(new_lines) + "\n"
    MEMORY_PATH.write_text(content)
    print(f"[update_memory] Updated MEMORY.md with {len(summaries)} topics")


if __name__ == "__main__":
    update_memory_index()
