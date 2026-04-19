"""GitHub PR parsers: fetch PR+reviews and convert to normalized claims."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from vault.research.github_rich_client import GitHubRichClient


GITHUB_REF_PATTERN = re.compile(
    r"(?:"
    r"#(\d+)"
    r"|([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)#(\d+)"
    r"|https?://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)/(issues|pull)/(\d+)"
    r")"
)


@dataclass
class ParsedGitHubPR:
    """Normalized parsed GitHub PR with reviews and approvers."""
    pr_number: int
    repo: str
    title: str
    body: str
    state: str
    merged: bool
    merged_at: str | None
    created_at: str
    author_login: str
    url: str
    labels: list[str]
    milestone: str | None
    assignees: list[str]
    reviews: list[dict[str, Any]] = field(default_factory=list)
    approvers: list[str] = field(default_factory=list)


class GitHubParsers:
    """Collection of GitHub parsing utilities (wraps GitHubRichClient)."""

    @staticmethod
    def fetch_pr_with_reviews(pr_number: int, repo: str) -> dict[str, Any]:
        """Fetch PR payload and reviews via GitHubRichClient; return merged dict with approvers.

        Uses GitHubRichClient (existing rich PR client) to avoid duplicating
        gh API calls. This reuses fetch_rich_pr and fetch_reviews from the
        established GitHubRichClient, consistent with the project architecture.

        Returns:
            {
                "pr": <parsed PR dict>,
                "reviews": <list of review dicts>,
                "approvers": <list[str] of unique logins with APPROVED state>,
                "pr_number": int,
                "repo": str,
            }
        """
        rich = GitHubRichClient()
        pr_data: dict[str, Any] = rich.fetch_rich_pr(pr_number, repo)
        reviews: list[dict[str, Any]] = rich.fetch_reviews(pr_number, repo)

        approvers = list(dict.fromkeys(
            r.get("user", {}).get("login", "")
            for r in reviews
            if r.get("state", "").upper() == "APPROVED" and r.get("user", {}).get("login")
        ))

        return {
            "pr": pr_data,
            "reviews": reviews,
            "approvers": approvers,
            "pr_number": pr_number,
            "repo": repo,
        }

    @staticmethod
    def _parse_body_refs(body: str) -> list[tuple[str, str, str | None]]:
        """Extract (ref, relation) pairs from body text.

        Returns list of (reference_string, relation, matched_text).
        relation is one of: 'implements' (closes/fixes), 'blocks', 'mentions'.
        """
        if not body:
            return []

        refs: list[tuple[str, str, str | None]] = []
        seen: set[str] = set()

        lower = body.lower()
        for match in GITHUB_REF_PATTERN.finditer(body):
            ref_str = match.group(0).lstrip()
            if ref_str in seen:
                continue
            seen.add(ref_str)

            # Determine relation from surrounding context
            relation = "mentions"
            # Get 60 chars before the match for context
            start = max(0, match.start() - 60)
            ctx = body[start:match.start()].lower()

            if any(kw in ctx for kw in ("closes", "close", "fixes", "fix", "implements", "implement", "resolves", "resolve")):
                relation = "implements"
            elif "blocks" in ctx or "blocking" in ctx:
                relation = "blocks"

            refs.append((ref_str, relation, match.group(0)))

        return refs


def pr_to_claims(
    pr_payload: dict[str, Any],
    reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate normalized claims from a GitHub PR payload and reviews.

    Claim types produced:
    - status: PR merged/open state
    - approval: each unique APPROVED review
    - linkage: GitHub refs extracted from body (implements/blocks/mentions)
    - tag: each label on the PR
    - context: milestone when present

    Returns:
        List of claim dicts with: source, claim_type, entity_type, entity_id,
        text, event_timestamp, source_ref, metadata.
    """
    claims: list[dict[str, Any]] = []

    pr_number = pr_payload.get("number")
    repo = pr_payload.get("base", {}).get("repo", {}).get("full_name", "")
    url = pr_payload.get("html_url") or f"https://github.com/{repo}/pull/{pr_number}"
    merged_at = pr_payload.get("merged_at")
    created_at = pr_payload.get("created_at")
    event_timestamp = merged_at or created_at or ""
    title = pr_payload.get("title") or ""
    body = pr_payload.get("body") or ""
    state = pr_payload.get("state") or "open"
    merged = pr_payload.get("merged", False)

    # -------------------------------------------------------------------------
    # Status claim
    # -------------------------------------------------------------------------
    status_text = f"PR #{pr_number}: {title}"
    if merged:
        status_text += f" (merged {merged_at or ''})"
    claims.append({
        "source": "github",
        "claim_type": "status",
        "entity_type": "github_pr",
        "entity_id": f"{repo}#{pr_number}" if repo else str(pr_number),
        "text": status_text,
        "event_timestamp": event_timestamp,
        "source_ref": {"source_id": str(pr_number), "url": url},
        "metadata": {
            "merged": merged,
            "state": state,
            "title": title,
            "author": pr_payload.get("user", {}).get("login", ""),
        },
    })

    # -------------------------------------------------------------------------
    # Approval claims — one per unique approver
    # -------------------------------------------------------------------------
    seen_approvers: set[str] = set()
    for review in reviews:
        state_str = str(review.get("state", "")).upper()
        login = review.get("user", {}).get("login", "")
        if state_str == "APPROVED" and login and login not in seen_approvers:
            seen_approvers.add(login)
            review_body = review.get("body") or ""
            claims.append({
                "source": "github",
                "claim_type": "approval",
                "entity_type": "github_pr",
                "entity_id": f"{repo}#{pr_number}" if repo else str(pr_number),
                "text": f"PR #{pr_number} approved by {login}",
                "event_timestamp": event_timestamp,
                "source_ref": {"source_id": str(pr_number), "url": url},
                "metadata": {
                    "approver": login,
                    "review_body": review_body[:500] if review_body else "",
                    "review_state": state_str,
                },
            })

    # -------------------------------------------------------------------------
    # Linkage claims — GitHub refs from body
    # -------------------------------------------------------------------------
    from vault.research.github_parsers import GitHubParsers
    refs = GitHubParsers._parse_body_refs(body) if body else []
    for ref_str, relation, _ in refs:
        claims.append({
            "source": "github",
            "claim_type": "linkage",
            "entity_type": "github_pr",
            "entity_id": f"{repo}#{pr_number}" if repo else str(pr_number),
            "text": f"PR #{pr_number} {relation} {ref_str}",
            "event_timestamp": event_timestamp,
            "source_ref": {"source_id": str(pr_number), "url": url},
            "metadata": {
                "link_type": "github_ref",
                "relation": relation,
                "ref": ref_str,
            },
        })

    # -------------------------------------------------------------------------
    # Tag claims — labels
    # -------------------------------------------------------------------------
    labels_raw = pr_payload.get("labels", []) or []
    for label in labels_raw:
        if not isinstance(label, dict):
            continue
        label_name = label.get("name", "")
        if not label_name:
            continue
        claims.append({
            "source": "github",
            "claim_type": "tag",
            "entity_type": "github_pr",
            "entity_id": f"{repo}#{pr_number}" if repo else str(pr_number),
            "text": f"PR #{pr_number} tagged with '{label_name}'",
            "event_timestamp": event_timestamp,
            "source_ref": {"source_id": str(pr_number), "url": url},
            "metadata": {
                "label": label_name,
                "color": label.get("color", ""),
            },
        })

    # -------------------------------------------------------------------------
    # Context claim — milestone
    # -------------------------------------------------------------------------
    milestone = pr_payload.get("milestone")
    if milestone and isinstance(milestone, dict):
        ms_title = milestone.get("title", "")
        ms_number = milestone.get("number")
        if ms_title or ms_number:
            claims.append({
                "source": "github",
                "claim_type": "context",
                "entity_type": "github_pr",
                "entity_id": f"{repo}#{pr_number}" if repo else str(pr_number),
                "text": f"PR #{pr_number} in milestone: {ms_title}" + (f" (#{ms_number})" if ms_number else ""),
                "event_timestamp": event_timestamp,
                "source_ref": {"source_id": str(pr_number), "url": url},
                "metadata": {
                    "milestone_number": ms_number,
                    "milestone_title": ms_title,
                },
            })

    return claims
