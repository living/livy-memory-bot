"""Cross-platform deduplication and intersection finding."""
from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Any

GH_RE = re.compile(
    r"(?:https?://)?github\.com/([\w.-]+)/([\w.-]+)/(?:pull|issues)/(\d+)",
    re.IGNORECASE
)
TR_RE = re.compile(r"(?:https?://)?trello\.com/c/([a-zA-Z0-9]+)", re.IGNORECASE)


def extract_hours_plugin(desc: str) -> float | None:
    """Extrai horas logadas do plugin de horas no desc do card Trello."""
    patterns = [
        r"(?:horas|hours|logged|h)[:\s]+(\d+(?:[.,]\d+)?)\s*h?",
        r"(\d+(?:[.,]\d+)?)\s*horas?\s*trabalhadas?",
    ]
    for p in patterns:
        m = re.search(p, desc, re.IGNORECASE)
        if m:
            val = m.group(1).replace(",", ".")
            return float(val)
    return None


def extract_github_url(desc: str) -> str | None:
    """Extrai URL de PR/issue do GitHub no desc do card Trello."""
    m = GH_RE.search(desc)
    if m:
        return f"https://github.com/{m.group(1)}/{m.group(2)}/pull/{m.group(3)}"
    return None


def extract_trello_url(desc: str) -> str | None:
    """Extrai URL de card Trello no desc de um PR/issue GitHub."""
    m = TR_RE.search(desc)
    if m:
        return f"https://trello.com/c/{m.group(1)}"
    return None


def find_intersections(
    trello_items: list[dict[str, Any]],
    github_items: list[dict[str, Any]],
    tldv_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Find cross-platform intersections between Trello cards, GitHub PRs, and TLDV meetings.
    Returns list of intersection dicts with cross_platform list.
    """
    intersections: list[dict[str, Any]] = []

    trello_by_gh_url = {}
    for item in trello_items:
        gh_url = item.get("github_pr_url")
        if gh_url:
            trello_by_gh_url[gh_url.lower()] = item

    github_by_tr_url = {}
    for item in github_items:
        tr_url = item.get("trello_card_url")
        if tr_url:
            github_by_tr_url[tr_url.lower()] = item

    # Trello ↔ GitHub
    for gh_url, trello_item in trello_by_gh_url.items():
        if gh_url in github_by_tr_url:
            gh_item = github_by_tr_url[gh_url]
            intersections.append({
                "type": "trello_github",
                "trello_card": trello_item.get("card_name"),
                "github_pr": gh_item.get("pr_title"),
                "github_url": gh_url,
                "cross_platform": ["trello", "github"],
            })

    return intersections
