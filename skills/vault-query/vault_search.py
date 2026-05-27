#!/usr/bin/env python3
"""
vault_search.py — single-entry point for vault queries.

Usage:
    python3 vault_search.py "delphos-svd"
    python3 vault_search.py "delphos-svd" --type simple --limit 10
    python3 vault_search.py "Lincoln" --type entity --limit 5
    python3 vault_search.py "kaba PRs" --type simple --limit 20

Query types:
    simple      — direct keyword search in decisions/*.md (default)
    entity      — person/meeting lookup
    complex     — synthesis with cross-reference (NYI)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Add skills dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from decision_lookup import parse_decision_file, build_tag_index, search_by_tag, search_by_source, search_by_date_range
from scoring import RelevanceScorer, filter_and_rank
from search_limits import search_with_limit, MAX_RESULTS, ComplexityBudget
from vault_cache import VaultCache

DECISIONS_DIR = Path(__file__).parent.parent.parent / "memory" / "vault" / "decisions"
INDEX_PATH = Path(__file__).parent.parent.parent / "memory" / "vault" / "index.md"


def classify_query(query: str) -> str:
    """Classify query type from keyword patterns."""
    q = query.lower()
    entity_patterns = ['who is', 'who was', 'what meetings', 'which meetings']
    if any(p in q for p in entity_patterns):
        return "entity"
    if any(p in q for p in ['what is happening', "what's happening", 'compare across', 'synthesis']):
        return "complex"
    return "simple"


def search_decisions_simple(query: str, limit: int = 20) -> list[dict]:
    """Direct keyword search across all decision files."""
    all_blocks = []
    for f in DECISIONS_DIR.glob("*.md"):
        if f.name == ".gitkeep":
            continue
        blocks = parse_decision_file(f)
        all_blocks.extend(blocks)

    # Build tag index
    tag_idx = build_tag_index(all_blocks)

    # Search by keyword in text (simple grep)
    query_lower = query.lower()
    matched = []
    for b in all_blocks:
        if query_lower in b.text.lower() or query_lower in b.source_ref.lower():
            matched.append(b)
        elif any(query_lower in tag for tag in b.tags):
            matched.append(b)

    # Convert to dict
    dicts = [_block_to_dict(b) for b in matched]

    # Score and rank
    scored = filter_and_rank(dicts, query, min_score=3)

    # Apply limits
    return search_with_limit("simple_keyword", scored)[:limit]


def search_decisions_by_tag(tag: str, limit: int = 20) -> list[dict]:
    """O(1) tag lookup."""
    all_blocks = []
    for f in DECISIONS_DIR.glob("*.md"):
        if f.name == ".gitkeep":
            continue
        all_blocks.extend(parse_decision_file(f))

    tag_idx = build_tag_index(all_blocks)
    results = search_by_tag(tag_idx, tag, limit=limit)
    return [_block_to_dict(b) for b in results]


def search_entity(query: str, limit: int = 10) -> list[dict]:
    """Person/meeting lookup via index.md."""
    cache = VaultCache()
    content = cache.get_index()
    lines = content.split("\n")

    # Simple: find lines mentioning the query
    query_lower = query.lower()
    matches = [l for l in lines if query_lower in l.lower()]

    results = []
    for m in matches[:limit]:
        # Extract name/title from [[...]] or line content
        name = m
        if "[[" in m:
            import re
            names = re.findall(r'\[\[(.+?)\]\]', m)
            if names:
                name = names[0]
        results.append({"match": name, "line": m.strip()[:200]})

    return results


def _block_to_dict(b) -> dict:
    return {
        "date": b.date,
        "source": b.source,
        "source_ref": b.source_ref,
        "text": b.text,
        "tags": b.tags,
        "confidence": b.confidence,
    }


def format_results(results: list[dict], query: str, elapsed: float) -> str:
    """Format results for terminal output."""
    lines = []
    lines.append(f"Query: {query}")
    lines.append(f"Results: {len(results)}")
    lines.append(f"Time: {elapsed:.3f}s")
    lines.append("")

    if not results:
        lines.append("(no results)")
        return "\n".join(lines)

    # Group by date
    by_date = {}
    for r in results:
        d = r.get("date", "unknown")
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(r)

    for date in sorted(by_date.keys(), reverse=True):
        lines.append(f"## {date}")
        for r in by_date[date]:
            ref = r.get("source_ref", "")
            text = r.get("text", "")[:100]
            tags = r.get("tags", [])
            score = r.get("_score", "")
            tag_str = f" [{', '.join(tags[:3])}]" if tags else ""
            score_str = f" (score={score})" if score else ""
            lines.append(f"  • {ref}{tag_str}{score_str}")
            lines.append(f"    {text}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Vault search — single entry point")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--type", "-t", choices=["simple", "entity", "complex", "auto"],
                        default="auto", help="Query type (default: auto)")
    parser.add_argument("--tag", help="Search by exact tag (bypasses text search)")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--since", help="Filter by date (YYYY-MM-DD)")
    parser.add_argument("--until", help="Filter by date (YYYY-MM-DD)")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    start = time.perf_counter()

    query_type = args.type
    if query_type == "auto":
        query_type = classify_query(args.query)

    if args.tag:
        results = search_decisions_by_tag(args.tag, limit=args.limit)
    elif query_type == "entity":
        results = search_entity(args.query, limit=args.limit)
    elif query_type == "complex":
        # TODO: implement cross-reference
        results = search_decisions_simple(args.query, limit=args.limit)
    else:
        results = search_decisions_simple(args.query, limit=args.limit)

    elapsed = time.perf_counter() - start

    if args.json:
        print(json.dumps({
            "query": args.query,
            "type": query_type,
            "count": len(results),
            "elapsed_s": round(elapsed, 3),
            "results": results
        }, indent=2))
    else:
        print(format_results(results, args.query, elapsed))


if __name__ == "__main__":
    main()
