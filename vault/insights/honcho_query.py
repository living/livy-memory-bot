#!/usr/bin/env python3
"""honcho_query.py — Query lessons: fast path Honcho, fallback to disk."""

import os, re
from pathlib import Path

HONCHO_ENDPOINT = os.environ.get("HONCHO_ENDPOINT", "http://100.121.74.111:8000")
HONCHO_API_KEY = os.environ.get("HONCHO_API_KEY", "")
LESSONS_DIR = Path(__file__).parent.parent.parent / "memory" / "vault" / "lessons"


def honcho_health_check() -> bool:
    """Check if Honcho is reachable."""
    try:
        import httpx
        r = httpx.get(f"{HONCHO_ENDPOINT}/health", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def honcho_search(query: str, topK: int = 5) -> list[dict]:
    """Search Honcho for conclusions matching query. Returns [] on failure."""
    try:
        import httpx
        r = httpx.post(
            f"{HONCHO_ENDPOINT}/v1/search",
            headers={"Authorization": f"Bearer {HONCHO_API_KEY}"},
            json={"query": query, "topK": topK},
            timeout=10.0,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("conclusions", [])
    except Exception:
        return []


def disk_search(query: str, topK: int = 5) -> list[dict]:
    """Fallback: grep-like text search over lesson files."""
    if not LESSONS_DIR.exists():
        return []
    query_lower = query.lower()
    results = []
    for path in sorted(LESSONS_DIR.glob("*.md")):
        if path.name == "TEMPLATE.md":
            continue
        try:
            content = path.read_text()
            if query_lower in content.lower():
                m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                subject = m.group(1) if m else path.stem
                # Extract context around match for verification
                lines = content.split('\n')
                for line in lines:
                    if query_lower in line.lower():
                        snippet = line.strip()[:100]
                        # Append snippet to text so test can verify match
                        text = f"{subject} | {snippet}"
                        break
                else:
                    text = subject
                results.append({"text": text, "source": str(path), "path": str(path)})
        except Exception:
            continue
        if len(results) >= topK:
            break
    return results


def honcho_query(query: str, topK: int = 5) -> list[dict]:
    """Query lessons. Fast path: Honcho. Fallback: disk grep."""
    if honcho_health_check():
        results = honcho_search(query, topK)
        if results:
            return results
    return disk_search(query, topK)
