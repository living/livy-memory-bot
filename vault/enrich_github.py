"""
vault/enrich_github.py — Enrich PR-based decision pages with official github_api source.

Behavior:
- Scans memory/vault/decisions/*.md
- Finds source ref like https://github.com/{owner}/{repo}/pull/{number}
- Calls GitHub API for PR metadata
- Inserts a new source item `type: github_api` under sources if missing
- Preserves existing confidence (no forced promotion/demotion)
"""
from __future__ import annotations

import os
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
VAULT_DECISIONS = ROOT / "memory" / "vault" / "decisions"

GITHUB_API = "https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
PR_REF_RE = re.compile(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)")


def _split_frontmatter(text: str) -> tuple[str, str, str]:
    m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", text, flags=re.DOTALL)
    if not m:
        return "", "", text
    return m.group(1), m.group(2), m.group(4)


def _has_github_api_source(text: str) -> bool:
    return "type: github_api" in text


def _extract_pr_ref(text: str) -> Optional[tuple[str, str, str, str]]:
    m = PR_REF_RE.search(text)
    if not m:
        return None
    owner, repo, number = m.group(1), m.group(2), m.group(3)
    return owner, repo, number, m.group(0)


def _fetch_pr(owner: str, repo: str, number: str) -> dict:
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "livy-memory-agent",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = GITHUB_API.format(owner=owner, repo=repo, number=number)
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    return {
        "state": data.get("state"),
        "merged_at": data.get("merged_at"),
        "author": (data.get("user") or {}).get("login"),
        "html_url": data.get("html_url", url.replace("api.github.com/repos", "github.com").replace("/pulls/", "/pull/")),
    }


def _inject_github_source(text: str, pr_meta: dict) -> str:
    opening, fm, rest = _split_frontmatter(text)
    if not opening:
        return text

    retrieved = datetime.now(timezone.utc).date().isoformat()
    merged = pr_meta.get("merged_at") or "null"
    author = pr_meta.get("author") or "unknown"
    state = pr_meta.get("state") or "unknown"
    ref = pr_meta.get("html_url")

    block = (
        "  - type: github_api\n"
        f"    ref: {ref}\n"
        f"    retrieved: {retrieved}\n"
        f"    note: pr_state={state}; merged_at={merged}; author={author}\n"
    )

    # Prefer inserting after first source item (signal_event)
    if "sources:\n  - type: signal_event\n" in fm:
        fm2 = fm.replace("sources:\n  - type: signal_event\n", "sources:\n  - type: signal_event\n" + block, 1)
    elif "sources:\n" in fm:
        fm2 = fm.replace("sources:\n", "sources:\n" + block, 1)
    else:
        fm2 = fm + "\nsources:\n" + block

    return f"{opening}{fm2}\n---\n{rest}"


def run_enrich_github(decisions_dir: Path = VAULT_DECISIONS, dry_run: bool = False) -> dict:
    updated = 0
    skipped_no_pr = 0
    skipped_has_github_api = 0
    failed = 0

    for path in sorted(decisions_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")

        if _has_github_api_source(text):
            skipped_has_github_api += 1
            continue

        pr_ref = _extract_pr_ref(text)
        if not pr_ref:
            skipped_no_pr += 1
            continue

        owner, repo, number, _ = pr_ref
        try:
            meta = _fetch_pr(owner, repo, number)
            new_text = _inject_github_source(text, meta)
            if new_text != text:
                updated += 1
                if not dry_run:
                    path.write_text(new_text, encoding="utf-8")
        except Exception:
            failed += 1

    return {
        "updated": updated,
        "skipped_no_pr": skipped_no_pr,
        "skipped_has_github_api": skipped_has_github_api,
        "failed": failed,
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    result = run_enrich_github()
    print(json.dumps(result, ensure_ascii=False, indent=2))
