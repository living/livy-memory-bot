"""
vault/qw2/consolidate.py — Dedupe intra-file + fact-check enrichment.
Runs after QW-2 writes to topic files.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

_WS = Path(__file__).resolve().parents[2]
if str(_WS) not in sys.path:
    sys.path.insert(0, str(_WS))

from vault.qw2.lock import acquire_lock, release_lock
from vault.qw2.fact_check import enrich_decision

DECISIONS_DIR = _WS / "memory" / "vault" / "decisions"

# Entry regex: capture date, source, text, source_ref, confidence
# Handles both buggy format (**Source:e**) and correct format (**Source:**)

_ENTRY_RE_RAW = re.compile(
    r"(?:\n|^)### (\d{4}-\d{2}-\d{2}) [—-] (\w+)\n\n> ([^\n]+)\n\n- \*\*(\w+(?:\s+\w+)*):\*\* (.+)\n- \*\*(\w+(?:\s+\w+)*):\*\* (.+)\n(?:- \*\*(\w+(?:\s+\w+)*):\*\* (.+)\n)?"
)

# Matches frontmatter and consumes 1-3 trailing newlines before entries
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n{1,3}", re.DOTALL)


class ParsedEntry(TypedDict):
    date: str
    source: str
    text: str
    source_ref: str
    confidence: str
    confidence_level: str | None


def parse_topic_file(path: Path, content: str | None = None) -> list[ParsedEntry]:
    """Parse all entries from a topic file. Returns list of ParsedEntry.
    
    Parameters
    ----------
    path : Path — file to read (ignored if content is provided)
    content : str | None — if provided, parse this string instead of reading from path
    """
    if content is None:
        content = path.read_text()
    entries: list[ParsedEntry] = []

    # Extract frontmatter if present
    fm_match = FRONTMATTER_RE.match(content)
    frontmatter: dict[str, str] = {}
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                frontmatter[k.strip()] = v.strip()

    body = FRONTMATTER_RE.sub("", content)

    for match in _ENTRY_RE_RAW.finditer(body):
        label1, value1 = match.group(4), match.group(5)
        label2, value2 = match.group(6), match.group(7)
        # Assign to correct fields
        if label1 == "Source":
            source_ref, confidence = value1, value2
        else:
            source_ref, confidence = value2, value1
        # Extract confidence_level from **Confidence Level:** line after the entry block
        entry_start = match.end()
        entry_block = body[entry_start:entry_start + 300]
        cl_match = re.search(r"- \*\*Confidence Level:\*\* ([^\n]+)", entry_block)
        confidence_level: str | None = cl_match.group(1).strip() if cl_match else None
        entry: ParsedEntry = {
            "date": match.group(1),
            "source": match.group(2),
            "text": match.group(3).strip(),
            "source_ref": source_ref.strip(),
            "confidence": confidence.strip(),
            "confidence_level": confidence_level,
        }
        entries.append(entry)

    return entries


def dedupe_entries(entries: list[ParsedEntry]) -> list[ParsedEntry]:
    """Remove duplicate source_refs, keeping latest by date."""
    seen: dict[str, ParsedEntry] = {}
    for entry in entries:
        ref = entry["source_ref"]
        if ref not in seen or entry["date"] > seen[ref]["date"]:
            seen[ref] = entry
    return list(seen.values())


def build_frontmatter(topic_name: str, confidence_level: str | None = None) -> str:
    """Build YAML frontmatter string."""
    lines = ["---", f"name: {topic_name}"]
    if confidence_level:
        lines.append(f"confidence_level: {confidence_level}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def rewrite_topic_file(path: Path, entries: list[ParsedEntry], topic_name: str) -> None:
    """Rewrite topic file with deduplicated + enriched entries."""
    # Sort by date descending
    entries_sorted = sorted(entries, key=lambda e: e["date"], reverse=True)

    # Build new content: frontmatter + entries separated by blank lines
    parts = [build_frontmatter(topic_name)]
    for e in entries_sorted:
        level = e.get("confidence_level") or ""
        entry_lines = [
            f"### {e['date']} — {e['source']}",
            "",  # blank line before blockquote
            f"> {e['text']}",
            "",
            f"- **Source:** {e['source_ref']}",
            f"- **Confidence:** {e['confidence']}",
        ]
        if level:
            entry_lines.append(f"- **Confidence Level:** {level}")
        parts.append("\n".join(entry_lines))

    # Join entries with double newline (blank line between entries)
    path.write_text("\n\n".join(parts) + "\n")


def get_topic_name(path: Path) -> str:
    """Extract name from frontmatter, fallback to path stem."""
    content = path.read_text()
    fm = FRONTMATTER_RE.match(content)
    if fm:
        for line in fm.group(1).splitlines():
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip()
    return path.stem


def consolidate_topic(path: Path, dry_run: bool = False) -> dict[str, int]:
    """Consolidate a single topic file. Returns stats dict."""
    topic_name = get_topic_name(path)
    entries = parse_topic_file(path)
    total = len(entries)

    deduped = dedupe_entries(entries)
    removed = total - len(deduped)

    # Fact-check: enrich each entry (adds confidence_level)
    enriched = [enrich_decision(dict(e)) for e in deduped]

    if not dry_run:
        rewrite_topic_file(path, enriched, topic_name)

    return {
        "processed": 1,
        "entries_total": total,
        "deduped": removed,
        "fact_checked": len(enriched),
        "written": 0 if dry_run else 1,
        "errors": 0,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="QW-2 Consolidate")
    parser.add_argument("--all", action="store_true", help="Consolidate all topic files")
    parser.add_argument("--topic", help="Consolidate specific topic file (without .md)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--reset", action="store_true", help="Clear confidence_level from frontmatter")
    args = parser.parse_args()

    if not acquire_lock():
        print("ERROR: Lock file exists, another run in progress")
        sys.exit(1)

    try:
        if args.topic:
            topic_path = DECISIONS_DIR / f"{args.topic}.md"
            if not topic_path.exists():
                print(f"WARNING: {topic_path} not found")
                sys.exit(1)
            stats = consolidate_topic(topic_path, dry_run=args.dry_run)
            print(stats)
        elif args.all or args.reset:
            stats = {"processed": 0, "entries_total": 0, "deduped": 0, "fact_checked": 0, "written": 0, "errors": 0}
            for path in DECISIONS_DIR.glob("*.md"):
                if path.name == ".gitkeep":
                    continue
                s = consolidate_topic(path, dry_run=args.dry_run)
                for k in stats:
                    stats[k] += s[k]
            print(stats)
        else:
            print("Specify --all or --topic NAME")
            sys.exit(1)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
