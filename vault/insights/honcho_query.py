#!/usr/bin/env python3
"""honcho_query.py — Query lessons from Honcho conclusions API.

Fast path: POST /v3/workspaces/{workspace_id}/conclusions/query (semantic search)
Fallback: grep over lesson files in memory/vault/lessons/
"""

import os, re
from pathlib import Path

HONCHO_BASE = os.environ.get("HONCHO_BASE", "http://100.121.74.111:8000")
HONCHO_API_KEY = os.environ.get("HONCHO_API_KEY", "")
WORKSPACE_ID = os.environ.get("HONCHO_WORKSPACE_ID", "openclaw")
LESSONS_DIR = Path(__file__).parent.parent.parent / "memory" / "vault" / "lessons"
# The agent-memory-agent peer records all lessons
AGENT_PEER = os.environ.get("HONCHO_AGENT_PEER", "agent-memory-agent")


def honcho_health_check() -> bool:
    """Check if Honcho daemon is reachable."""
    try:
        import httpx
        r = httpx.get(f"{HONCHO_BASE}/health", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def honcho_search(query: str, top_k: int = 5) -> list[dict]:
    """Search lessons via Honcho conclusions semantic search.
    
    Requires observer_id and observed_id filters to scope results.
    All lessons are recorded with agent-memory-agent as both observer and observed.
    """
    try:
        import httpx
        payload = {
            "query": query,
            "top_k": top_k,
            "filters": {
                "observer_id": AGENT_PEER,
                "observed_id": AGENT_PEER,
            }
        }
        headers = {}
        if HONCHO_API_KEY:
            headers["Authorization"] = f"Bearer {HONCHO_API_KEY}"
        
        r = httpx.post(
            f"{HONCHO_BASE}/v3/workspaces/{WORKSPACE_ID}/conclusions/query",
            json=payload,
            headers=headers,
            timeout=15.0,
        )
        if r.status_code != 200:
            return []
        results = r.json()
        return [
            {
                "id": item.get("id", ""),
                "text": item.get("content", ""),
                "source": f"honcho:conclusion:{item.get('id', '')}",
                "observer_id": item.get("observer_id", ""),
                "observed_id": item.get("observed_id", ""),
                "created_at": item.get("created_at", ""),
            }
            for item in results
        ]
    except Exception:
        return []


def disk_search(query: str, top_k: int = 5) -> list[dict]:
    """Fallback: grep-like text search over lesson files.
    
    Searches both frontmatter and body content.
    """
    if not LESSONS_DIR.exists():
        return []
    query_lower = query.lower()
    results = []
    for path in sorted(LESSONS_DIR.glob("*.md")):
        if path.name == "TEMPLATE.md":
            continue
        try:
            content = path.read_text()
            if query_lower not in content.lower():
                continue
            # Extract subject from frontmatter
            subject = ""
            for line in content.split("\n"):
                if line.startswith("subject:"):
                    subject = line.split(":", 1)[1].strip().strip('"')
                    break
            if not subject:
                subject = path.stem
            results.append({
                "text": subject,
                "source": str(path),
                "path": str(path),
            })
        except Exception:
            continue
        if len(results) >= top_k:
            break
    return results


def honcho_query(query: str, top_k: int = 5) -> list[dict]:
    """Query lessons. Fast path: Honcho conclusions API. Fallback: disk grep."""
    if honcho_health_check():
        results = honcho_search(query, top_k)
        if results:
            return results
    return disk_search(query, top_k)
