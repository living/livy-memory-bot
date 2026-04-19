"""GitHub polling client for research pipeline.

Uses gh api search to get PR URLs, then resolves full PR details via
repos/{owner}/{repo}/pulls/{number} to guarantee merged_at, merged,
repository.full_name, and author are available for normalization.
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

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
            pr_summaries = self._search_merged_pr_summaries(repo, cutoff)
            for summary in pr_summaries:
                pr_number = summary.get("number")
                if pr_number is None:
                    continue
                full_pr = self._fetch_pr_details(repo, pr_number)
                if full_pr:
                    events.append(self._normalize_pr(full_pr))

        events.sort(key=lambda e: e.get("merged_at") or "")
        return events

    def _compute_cutoff(self, last_seen_at: str | None) -> datetime:
        if last_seen_at:
            return datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - timedelta(days=self.lookback_days)

    def _search_merged_pr_summaries(self, repo: str, cutoff: datetime) -> list[dict[str, Any]]:
        """Return lightweight PR summaries from search (number + repository URL)."""
        date_str = cutoff.strftime("%Y-%m-%d")
        # NOTE: Do not add `org:living` here.
        # GitHub Search API can unexpectedly widen results when `repo:` and
        # `org:` are combined, returning PR numbers from other repositories.
        # Keep strict repo scoping with `repo:{repo}` only.
        query = f"is:pr merged:>{date_str} repo:{repo}"

        cmd = [
            "gh",
            "api",
            "search/issues",
            "-X",
            "GET",
            "-f",
            f"q={query}",
            "--jq",
            ".items[] | {number, repository_url}",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception as exc:
            logger.warning(
                "source=github repo=%s query=search exception=%s",
                repo,
                exc,
            )
            return []

        if result.returncode != 0:
            logger.warning(
                "source=github repo=%s query=search returncode=%s stderr=%s",
                repo,
                result.returncode,
                result.stderr[:200],
            )
            return []

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        out: list[dict[str, Any]] = []
        for line in lines:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Defensive filtering: search/issues may occasionally return items
            # from other repositories even with repo: scope. Keep only exact repo.
            # Handle both API URL format (api.github.com/repos/) and web URL format
            # (github.com/) — normalize to compare the owner/repo suffix.
            repository_url = str(item.get("repository_url") or "")
            normalized_url = (
                repository_url
                .replace("https://api.github.com/repos/", "")
                .replace("https://github.com/", "")
                .rstrip("/")
            )
            if normalized_url != repo:
                continue

            out.append(item)
        return out

    def _fetch_pr_details(self, repo: str, pr_number: int) -> dict[str, Any] | None:
        """Resolve full PR details from repos/{owner}/{repo}/pulls/{number}.

        Returns None on failure (caller logs and skips the PR).
        """
        cmd = ["gh", "api", f"repos/{repo}/pulls/{pr_number}", "--jq", "."]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception as exc:
            logger.warning(
                "source=github repo=%s pr_number=%s query=pulls exception=%s",
                repo,
                pr_number,
                exc,
            )
            return None

        if result.returncode != 0:
            logger.warning(
                "source=github repo=%s pr_number=%s query=pulls returncode=%s stderr=%s",
                repo,
                pr_number,
                result.returncode,
                result.stderr[:200],
            )
            return None

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.warning(
                "source=github repo=%s pr_number=%s query=pulls parse_error",
                repo,
                pr_number,
            )
            return None

    def _normalize_pr(self, pr: dict[str, Any]) -> dict[str, Any]:
        repo = pr.get("base", {}).get("repo", {}).get("full_name", "")
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
