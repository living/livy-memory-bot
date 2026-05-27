#!/usr/bin/env python3
"""
vault_mcp_server.py — MCP server for vault search.

Exposes vault_search functionality as an MCP tool to OpenClaw.

Usage (stdio):
    python3 vault_mcp_server.py

Or via mcporter:
    mcporter run vault_mcp_server.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Add skills dir to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from decision_lookup import parse_decision_file, build_tag_index, search_by_tag
from scoring import filter_and_rank
from search_limits import search_with_limit
from vault_cache import VaultCache
from azure_transcript_search import search_transcripts as search_azure_transcripts, format_transcript_full

# Server instance
app = Server("vault")

DECISIONS_DIR = Path(__file__).parent.parent.parent / "memory" / "vault" / "decisions"


def _search(query: str, limit: int = 20, tag_filter: str | None = None) -> list[dict]:
    """Core search logic shared by all tools."""
    all_blocks = []
    for f in DECISIONS_DIR.glob("*.md"):
        if f.name == ".gitkeep":
            continue
        all_blocks.extend(parse_decision_file(f))

    if tag_filter:
        tag_idx = build_tag_index(all_blocks)
        results = search_by_tag(tag_idx, tag_filter, limit=limit)
    else:
        query_lower = query.lower()
        results = [b for b in all_blocks
                   if query_lower in b.text.lower() or query_lower in b.source_ref.lower()
                   or any(query_lower in t for t in b.tags)
                   or (b.confidence and query_lower in b.confidence.lower())]

    dicts = [_block_to_dict(b) for b in results]
    scored = filter_and_rank(dicts, query, min_score=3)
    return search_with_limit("simple_keyword", scored)[:limit]


def _block_to_dict(b) -> dict:
    return {
        "date": b.date,
        "source": b.source,
        "source_ref": b.source_ref,
        "text": b.text,
        "tags": b.tags,
        "confidence": b.confidence,
    }


# ─── MCP Tools ────────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="vault_search",
            description="Search vault decisions by keyword. Returns decisions from GitHub PRs, Trello cards, and TLDV meetings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g. 'delphos-svd', 'kaba', 'Lincoln')"},
                    "limit": {"type": "integer", "description": "Max results (default 20, max 50)", "default": 20},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="vault_search_by_tag",
            description="O(1) tag lookup in vault — faster than keyword search. Use when you know the exact tag.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "Exact tag to search (e.g. 'delphos-svd', 'kaba', 'bat')"},
                    "limit": {"type": "integer", "description": "Max results (default 20)", "default": 20},
                },
                "required": ["tag"],
            },
        ),
        Tool(
            name="vault_list_tags",
            description="List all unique tags in the vault.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="vault_stats",
            description="Get vault statistics — entry count by source and date range.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="vault_search_transcripts",
            description="Search full meeting transcripts in Azure Blob (not just decision summaries). Use this to find specific discussions, decisions or topics in actual meeting recordings. Returns speaker labels, timestamps, and transcript excerpts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g. 'Lincoln', 'compliance', 'deploy')"},
                    "limit": {"type": "integer", "description": "Max meetings to return (default 5)"},
                    "full": {"type": "boolean", "description": "Return full transcript instead of preview (default False)"},
                },
                "required": ["query"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    start = time.perf_counter()

    if name == "vault_search":
        query = arguments["query"]
        limit = min(arguments.get("limit", 20), 50)
        results = _search(query, limit=limit)

    elif name == "vault_search_by_tag":
        tag = arguments["tag"]
        limit = min(arguments.get("limit", 20), 50)
        results = _search("", limit=limit, tag_filter=tag)

    elif name == "vault_list_tags":
        all_blocks = []
        for f in DECISIONS_DIR.glob("*.md"):
            if f.name == ".gitkeep":
                continue
            all_blocks.extend(parse_decision_file(f))
        tag_idx = build_tag_index(all_blocks)
        all_tags = set()
        for tag_list in tag_idx.values():
            all_tags.update(tag_list)
        elapsed = time.perf_counter() - start
        return [TextContent(
            type="text",
            text=f"Tags ({len(all_tags)}): {', '.join(sorted(all_tags))}\nTime: {elapsed:.3f}s",
        )]

    elif name == "vault_stats":
        all_blocks = []
        sources = {}
        for f in DECISIONS_DIR.glob("*.md"):
            if f.name == ".gitkeep":
                continue
            blocks = parse_decision_file(f)
            all_blocks.extend(blocks)
            src = f.stem
            sources[src] = len(blocks)

        dates = sorted(set(b.date for b in all_blocks))
        elapsed = time.perf_counter() - start
        lines = [
            f"Vault Stats",
            f"Total entries: {len(all_blocks)}",
            f"Date range: {dates[0] if dates else '?'} → {dates[-1] if dates else '?'}",
            f"",
        ]
        for src, count in sorted(sources.items()):
            lines.append(f"  {src}: {count}")
        lines.append(f"")
        lines.append(f"Time: {elapsed:.3f}s")
        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "vault_search_transcripts":
        query = arguments["query"]
        limit = min(arguments.get("limit", 5), 10)
        full = arguments.get("full", False)

        try:
            from azure_transcript_search import (
                search_transcripts as azure_search,
                format_transcript_full,
                get_transcript,
            )
        except Exception as e:
            return [TextContent(type="text", text=f"Error loading azure_transcript_search: {e}\nTime: {time.perf_counter()-start:.3f}s")]

        try:
            transcript_results = azure_search(query, limit=limit)
        except Exception as e:
            return [TextContent(type="text", text=f"Azure search error: {e}\nTime: {time.perf_counter()-start:.3f}s")]

        elapsed = time.perf_counter() - start

        if not transcript_results:
            return [TextContent(type="text", text=f"No transcript matches for '{query}'\nTime: {elapsed:.3f}s")]

        lines = []
        lines.append(f"Transcript search: {query}")
        lines.append(f"Meetings found: {len(transcript_results)}")
        lines.append(f"Time (Azure Blob): {elapsed:.3f}s")
        lines.append("")

        for r in transcript_results:
            date = r.get("date", "?")
            mid = r.get("meeting_id", "?")
            speakers = r.get("speakers", [])
            matched = r.get("matched_segments", 0)
            total = r.get("total_segments", 0)
            preview = r.get("matched_segment_preview", "")

            lines.append(f"## {date} | {mid[:12]}... | {matched}/{total} segmentos")
            lines.append(f"Speakers: {', '.join(speakers)}")
            lines.append(f"Match: {preview}")

            if full:
                transcript = get_transcript(mid)
                if transcript:
                    full_text = format_transcript_full(transcript, query=query)
                    lines.append("")
                    lines.append("--- FULL TRANSCRIPT ---")
                    lines.append(full_text)
                    lines.append("--- END ---")

            lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    elapsed = time.perf_counter() - start

    if not results:
        return [TextContent(type="text", text=f"No results for '{arguments.get('query', arguments.get('tag'))}'\nTime: {elapsed:.3f}s")]

    # Format output
    lines = []
    query_label = arguments.get("query", arguments.get("tag", ""))
    lines.append(f"Query: {query_label}")
    lines.append(f"Results: {len(results)}")
    lines.append(f"Time: {elapsed:.3f}s")
    lines.append("")

    by_date = {}
    for r in results:
        d = r.get("date", "unknown")
        by_date.setdefault(d, []).append(r)

    for date in sorted(by_date.keys(), reverse=True):
        lines.append(f"## {date}")
        for r in by_date[date]:
            ref = r.get("source_ref", "")
            text = r.get("text", "")[:100]
            tags = r.get("tags", [])
            tag_str = f" [{', '.join(tags[:3])}]" if tags else ""
            lines.append(f"  • {ref}{tag_str}")
            lines.append(f"    {text}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
