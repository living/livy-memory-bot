"""Fetch decisions from GitHub merged PRs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from vault.research.github_client import GitHubClient

logger = logging.getLogger(__name__)

def fetch_github_decisions(since_days: int = 7) -> tuple[list[dict[str, Any]], str | None]:
    """
    Fetch merged PRs from all living org repos since cursor.
    Returns (decisions, max_merged_at) for cursor update.
    Uses existing GitHubClient normalization.
    """
    try:
        client = GitHubClient(lookback_days=since_days)
    except EnvironmentError as e:
        logger.warning(f"GitHub not configured: {e}")
        return [], None

    events = client.fetch_events_since(None)
    decisions = []
    max_merged: str | None = None

    for event in events:
        pr = event.get("payload", {})
        title = pr.get("title", "")
        body = pr.get("body", "") or ""
        merged_at = pr.get("merged_at", "")
        url = pr.get("url", "")
        repo = event.get("repo", "")

        if merged_at and (max_merged is None or merged_at > max_merged):
            max_merged = merged_at

        combined = f"{title} {body}".strip()
        if len(combined) < 50:
            continue

        decisions.append({
            "text": combined[:500],
            "source_ref": f"github:{repo}#{pr.get('number', '')}",
            "confidence": 0.85,
            "date": _pr_date(merged_at),
            "source": "github",
            "pr_title": title,
            "tags": [repo.split("/")[-1]] if repo else [],
            "url": url,
        })

    return decisions, max_merged

def _pr_date(merged_at: str) -> str:
    try:
        dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        return (dt - timedelta(hours=3)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
