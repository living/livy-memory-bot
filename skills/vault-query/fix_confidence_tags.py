#!/usr/bin/env python3
"""
fix_confidence_tags.py — Move tags from **Confidence:** to **Tags:** in vault entries.

Some vault entries (TLDV-sourced) have comma-separated tags in **Confidence:**
instead of in **Tags:**. This script fixes those entries.

Usage:
    python3 fix_confidence_tags.py [file.md]
    python3 fix_confidence_tags.py --all
"""
import re
from pathlib import Path

DECISIONS_DIR = Path(__file__).parent.parent.parent / "memory" / "vault" / "decisions"


def is_tag_string(s: str) -> bool:
    """Return True if s looks like a comma-separated tag list, not a confidence score."""
    s = s.strip()
    # A valid confidence is a single number (possibly with decimals)
    if re.match(r'^0?\.\d+$', s):
        return False
    if re.match(r'^1\.0+$', s):
        return False
    # A tag list has commas
    if ',' in s:
        return True
    return False


def fix_file(filepath: Path) -> int:
    """Fix one file. Returns number of entries fixed."""
    content = filepath.read_text()
    original = content

    # Pattern: find blocks that have both Source and a non-numeric Confidence
    # We need to insert Tags: after Source and before Confidence

    # Pattern for a full entry block:
    # - **Source:** tldv:xxx
    # - **Confidence:** tag1, tag2, tag3
    # We want to become:
    # - **Source:** tldv:xxx
    # - **Tags:** tag1, tag2, tag3
    # - **Confidence:** (remove or keep minimal)

    lines = content.split('\n')
    new_lines = []
    i = 0
    fixed = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is a Source line followed by a non-numeric Confidence
        if '**Source:**' in line and 'tldv:' in line:
            new_lines.append(line)
            i += 1

            # Look ahead for the Confidence line
            if i < len(lines) and '**Confidence:**' in lines[i]:
                conf_line = lines[i]
                # Extract the value after **Confidence:**
                match = re.search(r'\*\*Confidence:\*\*\s*(.+)', conf_line)
                if match:
                    conf_val = match.group(1).strip()
                    if is_tag_string(conf_val):
                        # Insert Tags line before Confidence line
                        new_lines.append(f" - **Tags:** {conf_val}")
                        # Replace Confidence with medium (placeholder)
                        new_lines.append(" - **Confidence:** medium")
                        fixed += 1
                        i += 1
                        continue
                new_lines.append(conf_line)
                i += 1
                continue

            new_lines.append(lines[i])
            i += 1
            continue

        new_lines.append(line)
        i += 1

    new_content = '\n'.join(new_lines)
    if new_content != original:
        filepath.write_text(new_content)
        print(f"Fixed {fixed} entries in {filepath.name}")
    return fixed


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix misplaced tags in Confidence field")
    parser.add_argument("--all", action="store_true", help="Fix all topic files")
    parser.add_argument("file", nargs="?", help="Specific file to fix")
    args = parser.parse_args()

    if args.all:
        files = list(DECISIONS_DIR.glob("*.md"))
        files = [f for f in files if f.name != ".gitkeep"]
    elif args.file:
        files = [Path(args.file)]
    else:
        print("Usage: fix_confidence_tags.py [--all|file.md]")
        return

    total = 0
    for f in files:
        total += fix_file(f)
    print(f"Total entries fixed: {total}")


if __name__ == "__main__":
    main()
