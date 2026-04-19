"""GitHub polling client for research pipeline.

Uses gh api search to fetch merged PRs in scoped repositories.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_REPOS_SCOPE = [
    "living/livy-memory-bot",
    "living/livy-bat-jobs",
    "living/livy-delphos-jobs",
    "living/livy-tldv-jobs",
]


class GitHubClient:
    """Client for polling merged PR events from GitHub via gh CLI."""

    def __init__(self, lookback_days: int = DEFAULT_LOOKBACK_DAYS, repos: list[str] | None = None) -> None:
        self.lookback_days = lookback_days
        self.repos = repos or DEFAULT_REPOS_SCOPE

    def fetch_events_since(self, last_seen_at: str | None) -> list[dict[str, Any]]:
        """Fetch normalized github:pr_merged events since timestamp."""
        cutoff = self._compute_cutoff(last_seen_at)
        events: list[dict[str, Any]] = []

        for repo in self.repos:
            raw_prs = self._fetch_merged_prs(repo, cutoff)
            for pr in raw_prs:
                events.append(self._normalize_pr(pr))

        events.sort(key=lambda e: e.get("merged_at") or "")
        return events

    def _compute_cutoff(self, last_seen_at: str | None) -> datetime:
        if last_seen_at:
            return datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - timedelta(days=self.lookback_days)

    def _fetch_merged_prs(self, repo: str, cutoff: datetime) -> list[dict[str, Any]]:
        date_str = cutoff.strftime("%Y-%m-%d")
        query = f"is:pr merged:>{date_str} repo:{repo} org:living"

        cmd = [
            "gh",
            "api",
            "search/issues",
            "-f",
            f"q={query}",
            "--jq",
            ".items[]",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception:
            return []

        if result.returncode != 0:
            return []

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        out: list[dict[str, Any]] = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def _normalize_pr(self, pr: dict[str, Any]) -> dict[str, Any]:
        repo = (pr.get("repository") or {}).get("full_name", "")
        pr_number = pr.get("number")
        event_id = f"{repo}#{pr_number}" if repo and pr_number is not None else str(pr_number)

        return {
            "source": "github",
            "type": "pr_merged",
            "id": event_id,
            "event_type": "github:pr_merged",
            "pr_number": pr_number,
            "title": pr.get("title"),
            "merged_at": pr.get("merged_at"),
            "created_at": pr.get("created_at"),
            "author": pr.get("user", {}),
            "repo": repo,
            "merged": pr.get("merged", False),
        }

    def fetch_pr(self, pr_number: int) -> dict[str, Any]:
        """Compatibility helper for pipeline context stage.

        Research pipeline already receives normalized event payload from `fetch_events_since`.
        For now, we return a minimal payload containing author metadata shape used by resolver.
        """
        return {
            "pr_number": pr_number,
            "author": {},
        }
