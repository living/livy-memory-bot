#!/usr/bin/env python3
"""Replay all vault entries to Honcho (living workspace)."""
from __future__ import annotations

import re
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

_WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_WS))

import requests

HONCHO_BASE = "http://100.121.74.111:8000"
HONCHO_WORKSPACE = "living"  # use living workspace (openclaw was wiped)
OBSERVER_ID = "agent-memory-agent"
DECISIONS_DIR = _WS / "memory" / "vault" / "decisions"


def build_content(entry: dict) -> str:
    parts = [
        entry.get("date", ""),
        entry.get("text", "")[:200],
        entry.get("source_ref", ""),
        f"tags:{entry.get('tags', '')}",
    ]
    return " | ".join(parts)


def index_entry(entry: dict, dry_run: bool = False) -> dict:
    content = build_content(entry)
    payload = {
        "conclusions": [{
            "content": content,
            "observer_id": OBSERVER_ID,
            "observed_id": entry.get("source_ref", "unknown").split(":")[0],
        }]
    }
    if dry_run:
        return {"status": "would_index", "content": content}
    try:
        url = f"{HONCHO_BASE}/v3/workspaces/{HONCHO_WORKSPACE}/conclusions"
        resp = requests.post(url, json=payload, timeout=15)
        if resp.ok:
            result = resp.json()
            return {"status": "indexed", "id": result[0]["id"] if isinstance(result, list) else "ok"}
        else:
            return {"status": "error", "detail": resp.text[:100]}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:100]}


def parse_entries():
    """Parse all entries from topic files."""
    entries = []
    for f in DECISIONS_DIR.glob("*.md"):
        if f.name == ".gitkeep":
            continue
        content = f.read_text()
        blocks = re.split(r"(?=^### \d{4}-\d{2}-\d{2})", content, flags=re.MULTILINE)
        for block in blocks:
            block = block.strip()
            if not block or not block.startswith("### "):
                continue
            lines = block.split("\n")
            # Parse header: "### YYYY-MM-DD — source"
            header = lines[0].replace("### ", "").strip()
            date = header[:10]
            source = header[13:].strip() if len(header) > 12 else ""

            text_lines, source_ref, tags_str, confidence = [], "", "", ""
            for line in lines[1:]:
                if line.startswith("> "):
                    text_lines.append(line[2:])
                elif "- **Source:**" in line:
                    source_ref = line.split("**Source:**")[1].strip()
                elif "- **Tags:**" in line:
                    tags_str = line.split("**Tags:**")[1].strip()
                elif "- **Confidence:**" in line:
                    confidence = line.split("**Confidence:**")[1].strip()

            text = " ".join(text_lines)
            if source_ref and text:
                entries.append({
                    "date": date,
                    "text": text,
                    "source_ref": source_ref,
                    "source": source,
                    "tags": tags_str,
                    "confidence": confidence,
                })
    return entries


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Replay vault entries to Honcho")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-workers", type=int, default=5)
    args = parser.parse_args()

    entries = parse_entries()
    print(f"Parsed {len(entries)} entries from vault")

    if args.dry_run:
        for e in entries[:5]:
            print(f"  [DRY] {e['date']} | {e['source_ref'][:50]} | {e['tags'][:30]}")
        print(f"  ... ({len(entries)} total)")
        return

    print(f"Indexing to workspace '{HONCHO_WORKSPACE}' ...")
    ok, err = 0, 0
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futures = {ex.submit(index_entry, e): e for e in entries}
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            e = futures[future]
            if result["status"] == "indexed":
                ok += 1
                if ok <= 5:
                    print(f"  OK {e['date']} {e['source_ref'][:40]}")
            else:
                err += 1
                print(f"  ERR {e['source_ref'][:40]}: {result.get('detail', '?')}")
            if i % 20 == 0:
                print(f"  ... {i}/{len(entries)}")

    print(f"\nDone: {ok} indexed, {err} errors")


if __name__ == "__main__":
    main()
