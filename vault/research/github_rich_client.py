"""GitHub rich PR client for research pipeline enrichment.

This module provides an additive client (does not replace GitHubClient) that fetches
full PR metadata, reviews, comments, and linked issues, preserving a dual model:
- raw payload: immutable fetched snapshot
- sanitized view: deduplicated and lightly cleaned projection
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class GitHubRichClient:
    """Client for fetching rich GitHub PR data via gh CLI."""

    def __init__(self) -> None:
        self._last_raw: dict[str, Any] = {}
        self._last_sanitized: dict[str, Any] = {}

    def _run_gh(self, cmd: list[str]) -> str:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.warning("source=github_rich command_failed returncode=%s", result.returncode)
            return ""
        return result.stdout or ""

    def _parse_json(self, text: str, default: Any) -> Any:
        if not text.strip():
            return default
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return default

    def fetch_rich_pr(self, pr_number: int, repo: str) -> dict[str, Any]:
        """Fetch full PR payload including body and metadata fields."""
        out = self._run_gh(["gh", "api", f"repos/{repo}/pulls/{pr_number}", "--jq", "."])
        return self._parse_json(out, {})

    def fetch_reviews(self, pr_number: int, repo: str) -> list[dict[str, Any]]:
        """Fetch all PR reviews (APPROVED, CHANGES_REQUESTED, etc.)."""
        out = self._run_gh(["gh", "api", f"repos/{repo}/pulls/{pr_number}/reviews", "--paginate", "--jq", "."])
        parsed = self._parse_json(out, [])
        return parsed if isinstance(parsed, list) else []

    def fetch_issue_comments(self, pr_number: int, repo: str) -> list[dict[str, Any]]:
        """Fetch issue-level comments for the PR thread."""
        out = self._run_gh(["gh", "api", f"repos/{repo}/issues/{pr_number}/comments", "--paginate", "--jq", "."])
        parsed = self._parse_json(out, [])
        return parsed if isinstance(parsed, list) else []

    def fetch_review_comments(self, pr_number: int, repo: str) -> list[dict[str, Any]]:
        """Fetch review line comments for the PR."""
        out = self._run_gh(["gh", "api", f"repos/{repo}/pulls/{pr_number}/comments", "--paginate", "--jq", "."])
        parsed = self._parse_json(out, [])
        return parsed if isinstance(parsed, list) else []

    def fetch_linked_issues(self, pr_number: int, repo: str) -> list[dict[str, Any]]:
        """Fetch linked issues/PRs from GraphQL crossReferences."""
        owner, name = repo.split("/", 1) if "/" in repo else ("", repo)
        query = (
            "query($owner:String!, $name:String!, $number:Int!) {"
            " repository(owner:$owner, name:$name) {"
            "  pullRequest(number:$number) {"
            "   crossReferences(first: 100) {"
            "    nodes {"
            "      target {"
            "        __typename number title url"
            "      }"
            "    }"
            "   }"
            "  }"
            " }"
            "}"
        )
        cmd = [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={pr_number}",
            "--jq",
            ".",
        ]
        out = self._run_gh(cmd)
        parsed = self._parse_json(out, {})
        nodes = (
            parsed.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("crossReferences", {})
            .get("nodes", [])
        )
        linked: list[dict[str, Any]] = []
        for node in nodes:
            target = node.get("target", {}) if isinstance(node, dict) else {}
            if not isinstance(target, dict):
                continue
            linked.append(
                {
                    "type": target.get("__typename"),
                    "number": target.get("number"),
                    "title": target.get("title"),
                    "url": target.get("url"),
                }
            )
        return linked

    def _derive_state(self, pr: dict[str, Any]) -> str:
        if pr.get("merged") or pr.get("merged_at"):
            return "merged"
        if pr.get("draft") and pr.get("state") == "open":
            return "draft"
        if pr.get("state") == "open" and not pr.get("draft"):
            return "ready_for_review"
        if pr.get("state") == "closed":
            return "closed"
        return pr.get("state") or "open"

    def normalize_rich_event(self, full_pr: int | dict[str, Any], repo: str | None = None) -> dict[str, Any]:
        """Build full normalized rich event from either PR number+repo or pre-fetched PR."""
        if isinstance(full_pr, int):
            pr_number = full_pr
            repo_name = repo or ""
            pr = self.fetch_rich_pr(pr_number, repo_name)
        else:
            pr = full_pr
            pr_number = int(pr.get("number") or 0)
            repo_name = repo or pr.get("base", {}).get("repo", {}).get("full_name", "")

        if not pr_number:
            pr_number = int(pr.get("number") or 0)
        if not repo_name:
            repo_name = pr.get("base", {}).get("repo", {}).get("full_name", "")

        reviews = self.fetch_reviews(pr_number, repo_name) if pr_number and repo_name else []
        issue_comments = self.fetch_issue_comments(pr_number, repo_name) if pr_number and repo_name else []
        review_comments = self.fetch_review_comments(pr_number, repo_name) if pr_number and repo_name else []
        linked_issues = self.fetch_linked_issues(pr_number, repo_name) if pr_number and repo_name else []

        self._last_raw = {
            "pr": json.dumps(pr, ensure_ascii=False),
            "reviews": json.dumps(reviews, ensure_ascii=False),
            "issue_comments": json.dumps(issue_comments, ensure_ascii=False),
            "review_comments": json.dumps(review_comments, ensure_ascii=False),
            "linked_issues": json.dumps(linked_issues, ensure_ascii=False),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "repo": repo_name,
            "pr_number": pr_number,
        }

        body = self._sanitize_text(pr.get("body") or "")
        event = {
            "source": "github",
            "type": "pr_rich",
            "event_type": "github:pr_rich",
            "id": f"{repo_name}#{pr_number}" if repo_name and pr_number else str(pr_number),
            "repo": repo_name,
            "pr_number": pr_number,
            "state": self._derive_state(pr),
            "title": pr.get("title"),
            "body": body,
            "created_at": pr.get("created_at"),
            "updated_at": pr.get("updated_at"),
            "merged_at": pr.get("merged_at"),
            "author": pr.get("user", {}),
            "labels": pr.get("labels", []) or [],
            "milestone": pr.get("milestone"),
            "assignees": pr.get("assignees", []) or [],
            "requested_reviewers": pr.get("requested_reviewers", []) or [],
            "reviews": self._dedupe_items(reviews),
            "issue_comments": self._dedupe_items(issue_comments),
            "review_comments": self._dedupe_items(review_comments),
            "linked_issues": linked_issues,
            "event_at": pr.get("updated_at") or pr.get("merged_at") or pr.get("created_at"),
        }

        self._last_sanitized = copy.deepcopy(event)
        return event

    def raw_payload(self) -> dict[str, Any]:
        """Return immutable snapshot of the last fetched payload."""
        return copy.deepcopy(self._last_raw)

    def sanitized_view(self) -> dict[str, Any]:
        """Return deduplicated sanitized projection of the last normalized event."""
        return copy.deepcopy(self._last_sanitized)

    def _sanitize_text(self, text: str) -> str:
        """Remove mechanical noise while preserving meaningful references and content."""
        if not text:
            return ""

        out = text.replace("\r\n", "\n")
        # Remove common mechanical trailers/signatures
        out = re.sub(r"^\s*Co-authored-by:.*$", "", out, flags=re.MULTILINE | re.IGNORECASE)
        out = re.sub(r"^\s*Signed-off-by:.*$", "", out, flags=re.MULTILINE | re.IGNORECASE)
        # Remove obvious bot markers/boilerplate lines
        out = re.sub(r"^\s*\[[^\]]*bot[^\]]*\].*$", "", out, flags=re.MULTILINE | re.IGNORECASE)
        out = re.sub(r"^\s*Generated by .*automation.*$", "", out, flags=re.MULTILINE | re.IGNORECASE)
        # Collapse blank lines
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out.strip()

    def _item_hash(self, item: dict[str, Any]) -> str:
        body = self._sanitize_text(str(item.get("body") or ""))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _dedupe_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[Any, str]] = set()
        out: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            key = (item.get("id"), self._item_hash(item))
            if key in seen:
                continue
            seen.add(key)
            item_copy = dict(item)
            if "body" in item_copy:
                item_copy["body"] = self._sanitize_text(str(item_copy.get("body") or ""))
            out.append(item_copy)
        return out

    def _extract_trello_urls(self, text: str) -> list[str]:
        """Extract Trello URLs from arbitrary text."""
        if not text:
            return []
        raw = re.findall(r"(?:https?://)?trello\.com/[cb]/[A-Za-z0-9]+", text)
        out: list[str] = []
        for url in raw:
            if not url.startswith("http"):
                url = f"https://{url}"
            out.append(url)
        # preserve order, dedupe
        return list(dict.fromkeys(out))

    def _extract_github_refs(self, text: str) -> list[str]:
        """Extract GitHub issue/PR refs from text (#123, owner/repo#123, URLs)."""
        if not text:
            return []
        refs: list[str] = []
        refs.extend(re.findall(r"#[0-9]+", text))
        refs.extend(re.findall(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[0-9]+", text))

        for owner, repo, kind, num in re.findall(
            r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/(issues|pull)/([0-9]+)",
            text,
        ):
            refs.append(f"{owner}/{repo}#{num}")
            suffix = kind if kind.endswith("s") else f"{kind}s"
            refs.append(f"{suffix}/{num}")

        return list(dict.fromkeys(refs))
