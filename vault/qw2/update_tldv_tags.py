#!/usr/bin/env python3
"""
Update TLDV tags for existing vault entries with real tags from Supabase.
One-time backfill: fetches tags for all 38 TLDV meetings and updates topic files.
"""
from __future__ import annotations

import re
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

_WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_WS))
os.environ.setdefault("SUPABASE_URL", "https://supabase.living.locaweb.com.br")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))

from vault.research.tldv_client import TLDVClient

DECISIONS_DIR = _WS / "memory" / "vault" / "decisions"


def get_tags_for_meeting(client, meeting_id: str) -> tuple[str, list[str]]:
    """Fetch tags for a single meeting from Supabase."""
    try:
        summaries = client.fetch_summaries(meeting_id) or []
        for summary in summaries:
            tags = summary.get("tags")
            if isinstance(tags, list) and tags:
                cleaned = [str(t).strip() for t in tags if str(t).strip()]
                if cleaned:
                    return meeting_id, cleaned
    except Exception as e:
        print(f"  [WARN] meeting {meeting_id[:16]}...: {e}")
    return meeting_id, []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Update TLDV tags in existing vault entries")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Update TLDV tags (dry-run)" if args.dry_run else "=== Update TLDV tags (REAL) ===")
    print()

    # 1. Collect all TLDV source_refs from topic files
    all_content = ""
    for f in DECISIONS_DIR.glob("*.md"):
        if f.name == ".gitkeep":
            continue
        all_content += f.read_text() + "\n"

    tldv_refs = re.findall(r"tldv:([a-f0-9]+)", all_content)
    unique_mids = list(dict.fromkeys(tldv_refs))  # preserve order, remove dupes
    print(f"Found {len(unique_mids)} unique TLDV meetings in vault")

    # 2. Fetch tags for all meetings (sequential — Tailscale DNS required)
    print(f"Fetching tags from Supabase (sequential, ~1s each)...")
    client = TLDVClient(lookback_days=60)
    mid_to_tags = {}
    for i, mid in enumerate(unique_mids):
        if i > 0 and i % 10 == 0:
            print(f"  [{i}/{len(unique_mids)}] ...")
        _, tags = get_tags_for_meeting(client, mid)
        mid_to_tags[mid] = tags
        if tags:
            print(f"  {mid[:16]}... -> {tags}")

    tags_found = sum(1 for v in mid_to_tags.values() if v)
    print(f"\nTags found: {tags_found}/{len(unique_mids)} meetings")

    # 3. Update topic files
    updated_files = set()
    for f in DECISIONS_DIR.glob("*.md"):
        if f.name == ".gitkeep":
            continue
        content = f.read_text()
        new_lines = []
        changed = False

        for line in content.split("\n"):
            if line.startswith("- **Source:**") and "tldv:" in line:
                # Extract meeting_id from source ref
                m = re.search(r"(tldv:[a-f0-9]+)", line)
                if m:
                    ref = m.group(1)
                    mid = ref.split(":")[1]
                    tags = mid_to_tags.get(mid, [])
                    tags_str = ", ".join(tags) if tags else "tldv"
                    new_lines.append(line)
                    new_lines.append(f"- **Tags:** {tags_str}")
                    changed = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        if changed and not args.dry_run:
            f.write_text("\n".join(new_lines) + "\n")
            updated_files.add(f.name)

    print(f"\n{'Would update' if args.dry_run else 'Updated'}: {len(updated_files)} files")
    if updated_files:
        print(f"  {', '.join(sorted(updated_files))}")


if __name__ == "__main__":
    main()
