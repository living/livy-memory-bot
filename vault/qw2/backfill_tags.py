#!/usr/bin/env python3
"""
Backfill tags for existing vault entries.
Tags are extracted from:
- GitHub: repo name from source_ref (e.g. github:living/delphos-svd#13 → delphos-svd)
- Trello: board/list name from API
- TLDV: meeting tags from Supabase
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_WS))

DECISIONS_DIR = _WS / "memory" / "vault" / "decisions"


def infer_github_tags(source_ref: str) -> list[str]:
    """Extract repo name as tag from github source_ref."""
    # Format: github:org/repo#number
    m = re.match(r"github:([^/]+/[^#]+)#", source_ref)
    if m:
        repo = m.group(1).split("/")[-1]  # just the repo name
        return [repo]
    return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Backfill tags for vault entries")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Backfill tags (dry-run)" if args.dry_run else "=== Backfill tags (REAL) ===\n")

    updated_files = set()

    for md_path in DECISIONS_DIR.glob("*.md"):
        if md_path.name == ".gitkeep":
            continue

        content = md_path.read_text()
        new_lines = []
        changed = False

        for line in content.split("\n"):
            # Check if this is a Source line followed by content that needs Tags
            if line.startswith("- **Source:**"):
                source_ref = line.split("**Source:**")[1].strip()
                source_type = source_ref.split(":")[0] if ":" in source_ref else ""

                # Determine tags based on source type
                if source_type == "github":
                    tags = infer_github_tags(source_ref)
                elif source_type == "trello":
                    tags = ["trello"]  # placeholder until we fetch card data
                elif source_type == "tldv":
                    tags = ["tldv"]
                elif source_type == "test":
                    tags = []
                else:
                    tags = []

                tags_str = ", ".join(tags) if tags else ""

                new_lines.append(line)
                # Add Tags line after Source
                new_lines.append(f"- **Tags:** {tags_str}")
                changed = True

                # Count entries processed
                if tags_str:
                    print(f"  {md_path.name}: {source_ref[:40]} → {tags_str}")
                else:
                    print(f"  {md_path.name}: {source_ref[:40]} → (no tags)")
            else:
                new_lines.append(line)

        if changed and not args.dry_run:
            new_content = "\n".join(new_lines)
            # Ensure double newline before Tags (fix formatting)
            new_content = re.sub(
                r"\n(- \*\*Tags:\*\* )",
                r"\n\1",
                new_content
            )
            md_path.write_text(new_content + "\n")
            updated_files.add(md_path.name)

    print(f"\n{'Would update' if args.dry_run else 'Updated'}: {len(updated_files)} files")
    if updated_files:
        print(f"  {', '.join(sorted(updated_files))}")


if __name__ == "__main__":
    main()
