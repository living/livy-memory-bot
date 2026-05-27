"""
Structured decision lookup for vault-query.

Provides O(1) tag lookups, O(log n) date range queries, and O(n) source_ref lookups
by parsing decision blocks once and building indexes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class DecisionBlock:
    """A single decision entry parsed from a decisions/*.md file."""
    date: str  # YYYY-MM-DD
    source: str  # e.g. "github", "tldv", "trello"
    source_ref: str  # e.g. "github:living/delphos-svd#35"
    text: str  # decision text
    tags: list[str] = field(default_factory=list)
    confidence: str = "N/A"

    def __post_init__(self):
        if isinstance(self.tags, str):
            self.tags = [t.strip() for t in self.tags.split(",") if t.strip()]


def parse_decision_file(path: str | Path) -> list[DecisionBlock]:
    """
    Parse a decisions/*.md file into DecisionBlock objects.

    Format:
    ### YYYY-MM-DD — source

    > decision text

    - **Source:** github:org/repo#N
    - **Confidence:** 0.92
    - **Tags:** tag1, tag2, tag3
    """
    content = Path(path).read_text()
    blocks = re.split(r"(?=^### \d{4}-\d{2}-\d{2})", content, flags=re.MULTILINE)

    decisions = []
    for block in blocks:
        block = block.strip()
        if not block or not block.startswith("### "):
            continue

        lines = block.split("\n")
        header = lines[0].replace("### ", "").strip()
        date = header[:10]

        # Source type: "github", "tldv", "trello", "test"
        rest = header[13:].strip() if len(header) > 12 else ""
        source = rest.split()[0] if rest else ""

        text_parts = []
        source_ref = ""
        tags: list[str] = []
        confidence = "N/A"

        for line in lines[1:]:
            line = line.strip()
            if line.startswith("> "):
                text_parts.append(line[2:])
            elif "**Source:**" in line:
                source_ref = line.split("**Source:**")[1].strip()
            elif "**Tags:**" in line:
                tags_str = line.split("**Tags:**")[1].strip()
                if tags_str:
                    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
            elif "**Confidence:**" in line:
                confidence = line.split("**Confidence:**")[1].strip()

        text = " ".join(text_parts)
        if text:
            decisions.append(DecisionBlock(
                date=date,
                source=source,
                source_ref=source_ref,
                text=text,
                tags=tags,
                confidence=confidence,
            ))

    return decisions


def build_tag_index(blocks: list[DecisionBlock]) -> dict[str, list[DecisionBlock]]:
    """Build a tag → [DecisionBlock] index. O(n) build, O(1) lookup."""
    index: dict[str, list[DecisionBlock]] = {}
    for block in blocks:
        for tag in block.tags:
            if tag not in index:
                index[tag] = []
            index[tag].append(block)
    return index


def build_source_index(blocks: list[DecisionBlock]) -> dict[str, list[DecisionBlock]]:
    """Build a source type → [DecisionBlock] index."""
    index: dict[str, list[DecisionBlock]] = {}
    for block in blocks:
        if block.source not in index:
            index[block.source] = []
        index[block.source].append(block)
    return index


def search_by_tag(
    tag_index: dict[str, list[DecisionBlock]],
    tag: str,
    limit: int = 20,
) -> list[DecisionBlock]:
    """O(1) lookup by tag."""
    results = tag_index.get(tag, [])
    return sorted(results, key=lambda b: b.date, reverse=True)[:limit]


def search_by_source(
    blocks: list[DecisionBlock],
    source_prefix: str,
    limit: int = 20,
) -> list[DecisionBlock]:
    """O(n) filter by source prefix."""
    results = [b for b in blocks if b.source_ref.startswith(source_prefix)]
    return sorted(results, key=lambda b: b.date, reverse=True)[:limit]


def search_by_date_range(
    blocks: list[DecisionBlock],
    since: str | None = None,
    until: str | None = None,
    limit: int = 30,
) -> list[DecisionBlock]:
    """O(log n) date range filter using binary search."""
    if since is None and until is None:
        return sorted(blocks, key=lambda b: b.date, reverse=True)[:limit]

    # Sort once
    sorted_blocks = sorted(blocks, key=lambda b: b.date)

    # Binary search for start index
    def bisect_start(data: list[DecisionBlock], target: str) -> int:
        lo, hi = 0, len(data)
        while lo < hi:
            mid = (lo + hi) // 2
            if data[mid].date < target:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def bisect_end(data: list[DecisionBlock], target: str) -> int:
        lo, hi = 0, len(data)
        while lo < hi:
            mid = (lo + hi) // 2
            if data[mid].date <= target:
                lo = mid + 1
            else:
                hi = mid
        return lo

    start_idx = bisect_start(sorted_blocks, since) if since else 0
    end_idx = bisect_end(sorted_blocks, until) if until else len(sorted_blocks)

    results = sorted_blocks[start_idx:end_idx]
    results.sort(key=lambda b: b.date, reverse=True)
    return list(results)[:limit]
