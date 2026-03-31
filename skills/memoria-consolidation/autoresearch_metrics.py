#!/usr/bin/env python3
"""
autoresearch_metrics.py — Quality metrics for the Livy Memory Agent.

Calculates scores for 4 dimensions:
  completeness  Score 0-10 per topic file (frontmatter + content checklist)
  crossrefs     Count of cross-references between topic files
  actions       Count of auto-actions from consolidate.py dry-run
  interventions Count of entries in consolidation-log.md needing human review
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

MEMORY_DIR  = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory")
CURATED_DIR = MEMORY_DIR / "curated"
LOG_FILE    = MEMORY_DIR / "consolidation-log.md"

# ── Completeness ─────────────────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.MULTILINE | re.DOTALL,
)

DECISION_RE = re.compile(r"(?i)(decisão|decision|registrada)", re.MULTILINE)

CURATED_FIELDS = ("name", "description", "type", "date")

def completeness_score(path: Path) -> int:
    """
    Score 0-10 for a single topic file.
    +2 per frontmatter field filled (name, description, type, date)
    +2 content has registered decision
    +2 mtime < 30 days
    """
    try:
        content = path.read_text()
    except Exception:
        return 0

    score = 0

    # Frontmatter fields
    m = FRONTMATTER_RE.match(content)
    if m:
        fm_text = m.group(1)
        for field in CURATED_FIELDS:
            # match 'field: value' where value is not empty/blank
            if re.search(rf"^{field}:\s*\S", fm_text, re.MULTILINE):
                score += 2
    else:
        # No frontmatter at all — check legacy format fields at top of file
        for field in CURATED_FIELDS:
            if re.search(rf"^{field}:\s*\S", content, re.MULTILINE):
                score += 2

    # Registered decision in content
    if DECISION_RE.search(content):
        score += 2

    # mtime < 30 days
    cutoff = datetime.now().timestamp() - 30 * 86400
    if path.stat().st_mtime >= cutoff:
        score += 2

    return min(score, 10)


def completeness_avg() -> float:
    """Average completeness score across all curated/*.md files."""
    files = list(CURATED_DIR.glob("*.md")) if CURATED_DIR.exists() else []
    if not files:
        return 0.0
    return sum(completeness_score(f) for f in files) / len(files)


# ── Cross-references ─────────────────────────────────────────────────────────

MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^\)]+\.md)\)", re.MULTILINE)

def count_crossrefs() -> int:
    """Count links to other topic files within memory/curated/."""
    files = list(CURATED_DIR.glob("*.md")) if CURATED_DIR.exists() else []
    curated_names = {f.name for f in files}

    count = 0
    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue
        for _, path in MD_LINK_RE.findall(content):
            # path may be relative like "other-file.md" or "memory/curated/other.md"
            name = Path(path).name
            if name in curated_names and name != f.name:
                count += 1
    return count


# ── Actions (simulate consolidate.py dry-run) ────────────────────────────────

def count_actions() -> int:
    """
    Simulate consolidate.py dry-run and count:
      len(signals["relative_dates"])
    + len(signals["stale"])
    + len(signals["orphaned"])
    """
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from consolidate import gather_signal, load_memory_index
    except ImportError as e:
        return 0

    try:
        _, referenced = load_memory_index()
        signals = gather_signal(referenced)
    except Exception:
        return 0

    return (
        len(signals.get("relative_dates", []))
        + len(signals.get("stale", []))
        + len(signals.get("orphaned", []))
    )


# ── Interventions ─────────────────────────────────────────────────────────────

WARNING_RE = re.compile(r"⚠️", re.MULTILINE)

def count_interventions() -> int:
    """Count lines containing ⚠️ in consolidation-log.md."""
    if not LOG_FILE.exists():
        return 0
    try:
        content = LOG_FILE.read_text()
    except Exception:
        return 0
    return len(WARNING_RE.findall(content))


# ── CLI ──────────────────────────────────────────────────────────────────────

METRIC_FNS = {
    "completeness":  completeness_avg,
    "crossrefs":      count_crossrefs,
    "actions":        count_actions,
    "interventions":  count_interventions,
}


def main():
    parser = argparse.ArgumentParser(description="Memory agent quality metrics")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Print all metrics as JSON")
    group.add_argument("--metric", metavar="NAME",
                       choices=list(METRIC_FNS.keys()),
                       help=f"Print just one metric. Choices: {list(METRIC_FNS.keys())}")
    args = parser.parse_args()

    if args.all:
        results = {name: fn() for name, fn in METRIC_FNS.items()}
        # interventions direction: lower is better (add direction flag for consumers)
        print(results)
    else:
        value = METRIC_FNS[args.metric]()
        print(value)


if __name__ == "__main__":
    main()
