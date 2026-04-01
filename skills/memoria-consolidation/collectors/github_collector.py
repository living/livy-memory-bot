#!/usr/bin/env python3
"""
github_collector.py — Collects merged PR signals from GitHub REST API.
Priority: 3 (tertiary — secondary evidence)

Key endpoints:
  GET /repos/{owner}/{repo}/pulls?state=closed → merged PRs with merged_at
  GET /repos/{owner}/{repo}/pulls/{number}/comments → PR comments

Env: GITHUB_PERSONAL_ACCESS_TOKEN (personal access token)
"""
import os, requests
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_bus import SignalEvent

GITHUB_TOKEN = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
GITHUB_ORG = os.environ.get("GITHUB_ORG", "living")

REPO_TOPIC_MAP = {
    "livy-bat-jobs": "bat-conectabot-observability.md",
    "livy-delphos-jobs": "delphos-video-vistoria.md",
    "livy-tldv-jobs": "tldv-pipeline-state.md",
    "livy-forge-platform": "forge-platform.md",
}


class GitHubCollector:
    source = "github"
    priority = 3

    def __init__(self, token: str = None, org: str = None):
        self.token = token or GITHUB_TOKEN
        self.org = org or GITHUB_ORG
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, url: str, params: dict = None) -> requests.Response:
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    def fetch_merged_prs(self, repo: str, since: str = None) -> list[dict]:
        """Fetch merged PRs for a repo since ISO timestamp."""
        url = f"https://api.github.com/repos/{self.org}/{repo}/pulls"
        params = {"state": "closed", "per_page": 30, "sort": "updated", "direction": "desc"}
        if since:
            params["since"] = since
        resp = self._get(url, params)
        prs = resp.json()
        # Filter to only merged (have merged_at)
        return [pr for pr in prs if pr.get("merged_at")]

    def collect(self, since_days: int = 7) -> list[SignalEvent]:
        """
        Collect merged PR signals across all living/ repos.
        Only PRs with meaningful description → signal_type=correction (if revert/rollback)
          or evidence for TLDV decisions.
        """
        signals = []
        import time
        since = datetime.now(timezone.utc).isoformat()

        repos = list(REPO_TOPIC_MAP.keys())

        for repo in repos:
            try:
                prs = self.fetch_merged_prs(repo)
                for pr in prs[:10]:  # latest 10
                    topic_ref = REPO_TOPIC_MAP.get(repo)
                    title = pr.get("title", "")
                    body = pr.get("body", "") or ""
                    merged_at = pr.get("merged_at", "")
                    pr_number = pr.get("number")

                    # Check if it's a revert/rollback → correction signal
                    if any(kw in title.lower() for kw in ["revert", "rollback", "undo"]):
                        sig = SignalEvent(
                            source="github",
                            priority=3,
                            topic_ref=topic_ref,
                            signal_type="correction",
                            payload={
                                "description": f"PR #{pr_number} revert/rollback: {title}",
                                "evidence": pr.get("html_url"),
                                "confidence": 1.0,
                            },
                            origin_id=f"PR#{pr_number}",
                            origin_url=pr.get("html_url"),
                        )
                        signals.append(sig)
                    elif body and topic_ref:
                        # Use PR description as evidence for topic
                        sig = SignalEvent(
                            source="github",
                            priority=3,
                            topic_ref=topic_ref,
                            signal_type="decision",
                            payload={
                                "description": f"PR #{pr_number}: {title}",
                                "evidence": pr.get("html_url"),
                                "confidence": 0.6,
                            },
                            origin_id=f"PR#{pr_number}",
                            origin_url=pr.get("html_url"),
                        )
                        signals.append(sig)
                time.sleep(0.3)  # rate limit guard
            except Exception as e:
                import logging
                logging.warning(f"GitHub fetch failed for {repo}: {e}")
        return signals
