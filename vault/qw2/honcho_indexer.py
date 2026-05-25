"""
vault/qw2/honcho_indexer.py — Index decisions to Honcho with supersedes chain.
"""
from __future__ import annotations

import httpx
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_WS = Path(__file__).resolve().parents[2]
if str(_WS) not in sys.path:
    sys.path.insert(0, str(_WS))

from vault.qw2.lock import acquire_lock, release_lock
from vault.qw2.consolidate import parse_topic_file

DECISIONS_DIR = _WS / "memory" / "vault" / "decisions"
HONCHO_BASE = "http://100.121.74.111:8000"
HONCHO_WORKSPACE = "openclaw"
HONCHO_AGENT_PEER = "agent-memory-agent"


def get_source_type(source_ref: str) -> str:
    """Extract source type from source_ref prefix."""
    m = re.match(r"^(tldv|github|trello):", source_ref)
    return m.group(1) if m else "unknown"


def build_content(entry: dict[str, Any], supersedes: str | None = None) -> str:
    """Build pipe-delimited content string."""
    parts = [
        entry.get("date", ""),
        entry.get("text", "")[:200],
        entry.get("source_ref", ""),
        f"confidence:{entry.get('confidence_level', 'unverified')}",
        f"tags:{entry.get('tags', '')}",
    ]
    if supersedes:
        parts.append(f"supersedes:{supersedes}")
    return " | ".join(parts)


def find_existing_conclusion(source_ref: str, source_type: str) -> str | None:
    """
    Search Honcho for existing conclusion with same source_ref.
    Uses POST /conclusions/list with filters.
    Returns conclusion ID if found, None otherwise.
    """
    url = f"{HONCHO_BASE}/v3/workspaces/{HONCHO_WORKSPACE}/conclusions/list"
    headers = {"Content-Type": "application/json"}
    payload = {"filters": {"observed_id": source_type}}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        conclusions = data if isinstance(data, list) else data.get("conclusions", [])

        for c in conclusions:
            content = c.get("content", "")
            # Exact match: content contains source_ref
            if f"source_ref:{source_ref}" in content or f"| {source_ref} |" in content:
                return c.get("id")
    except Exception:
        pass
    return None


def index_decision(entry: dict[str, Any], dry_run: bool = False) -> dict[str, str]:
    """Index a single decision to Honcho. Returns result dict."""
    source_ref = entry.get("source_ref", "")
    source_type = get_source_type(source_ref)
    if not source_ref or source_type == "unknown":
        return {"status": "skipped", "reason": "no source_ref"}

    # Find existing conclusion
    existing_id = find_existing_conclusion(source_ref, source_type) if not dry_run else None

    supersedes = existing_id if existing_id else None
    content = build_content(entry, supersedes)

    if dry_run:
        return {
            "status": "would_index",
            "source_ref": source_ref,
            "supersedes": supersedes,
            "content": content[:100],
        }

    # POST to Honcho
    url = f"{HONCHO_BASE}/v3/workspaces/{HONCHO_WORKSPACE}/conclusions"
    payload = {
        "conclusions": [{
            "content": content,
            "observer_id": HONCHO_AGENT_PEER,
            "observed_id": HONCHO_AGENT_PEER,
        }]
    }

    try:
        resp = httpx.post(url, json=payload, timeout=15)
        if resp.status_code == 201:
            new_id = resp.json()[0].get("id", "")
            return {"status": "indexed", "id": new_id, "superseded": existing_id}
        else:
            return {"status": "error", "code": resp.status_code, "body": resp.text[:100]}
    except Exception as e:
        return {"status": "error", "exception": str(e)}


def index_topic(path: Path, since: str | None = None, dry_run: bool = False) -> dict[str, int]:
    """Index all decisions from a topic file."""
    entries = parse_topic_file(path)
    stats = {"indexed": 0, "superseded": 0, "skipped": 0, "errors": 0}

    for entry in entries:
        if since and entry.get("date", "") < since:
            continue
        result = index_decision(entry, dry_run=dry_run)
        if result.get("status") == "indexed":
            stats["indexed"] += 1
            if result.get("superseded"):
                stats["superseded"] += 1
        elif result.get("status") == "skipped":
            stats["skipped"] += 1
        else:
            stats["errors"] += 1

    return stats


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="QW-2 Honcho Indexer")
    parser.add_argument("--all", action="store_true", help="Index all topic files")
    parser.add_argument("--since", help="Index only entries since DATE (ISO format)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    if not acquire_lock():
        print("ERROR: Lock file exists")
        sys.exit(1)

    try:
        stats = {"indexed": 0, "superseded": 0, "skipped": 0, "errors": 0}
        for path in DECISIONS_DIR.glob("*.md"):
            if path.name == ".gitkeep":
                continue
            s = index_topic(path, since=args.since, dry_run=args.dry_run)
            for k in stats:
                stats[k] += s[k]
        print(stats)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
