#!/usr/bin/env python3
"""
honcho_capture.py — ETL para extrair lições de GitHub PRs e escrever em memory/vault/lessons/

Usage:
    python3 vault/insights/honcho_capture.py --days 7
    python3 vault/insights/honcho_capture.py --repos living/livy-memory-bot living/livy-tldv-jobs --days 30
    python3 vault/insights/honcho_capture.py --repos all --min-activity 1 --days 7

Idempotência: path do ficheiro = date + slugify(subject) + sha256(source_ref)[:6]
Se o ficheiro já existe, skip — nunca sobrescreve lições manuais.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── SLUGIFY (language-agnostic, per spec) ───────────────────────────────────

def slugify(text: str) -> str:
    text = text.replace("\u2014", " ").replace("\u2013", " ").replace("#", " ")
    text = text.lower()
    text = re.sub(r"[^a-z0-9- ]", "", text)  # keep spaces & hyphens
    text = text.replace(" ", "-")
    return re.sub(r"-+", "-", text).strip("-")


# ─── LLM EXTRACTION ───────────────────────────────────────────────────────────

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are a senior engineer writing a concise lesson from a GitHub PR.
Output ONLY valid YAML frontmatter + lesson body in Portuguese (BR).
No markdown code fences around the YAML. No commentary.

Rules:
- type: lesson
- source: github
- source_ref: "{org}/{repo}/pull/{pr_number}"
- date: YYYY-MM-DD (BRT = UTC-3)
- subject: "PR #N — title"
- author: extracted from PR data or 'unknown'
- tags: [category tags]

Format:
## O que aconteceu
[neutral description — what was the change, why was it made]

## Decisão / Solução
[what was decided/done — the architectural choice, the approach taken]

## Lessons
- [lesson 1 — specific, actionable]
- [lesson 2 — specific, actionable]
- [lesson 3 — specific, actionable]

## Source
[GitHub PR URL]

If the PR is trivial (typo fix, chore, dependency bump, docs-only) with no meaningful decision or lesson, output ONLY:
---
type: lesson
skip_reason: trivial
---
"""


def extract_lesson_via_llm(
    org: str,
    repo: str,
    pr_number: int,
    pr_title: str,
    pr_body: str,
    merged_at: str,
    pr_url: str,
    model: str,
) -> str | None:
    """Call LLM to extract a lesson from a PR. Returns YAML+body or None on failure."""
    source_ref = f"{org}/{repo}/pull/{pr_number}"
    user_prompt = f"""PR #{pr_number}: {pr_title}

{('Body:\n' + pr_body) if pr_body else '(no body)'}

Merged: {merged_at}
URL: {pr_url}"""

    try:
        import urllib.request
        import urllib.error

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(org=org, repo=repo, pr_number=pr_number)},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 800,
        }

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"    [WARN] LLM call failed: {e}", file=sys.stderr)
        return None


def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from lesson content. Returns {} if none."""
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return {}
    import yaml
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


# ─── GITHUB QUERY ────────────────────────────────────────────────────────────

def list_org_repos(org: str) -> list[str]:
    """Return list of active repo names for an org."""
    try:
        result = subprocess.run(
            ["gh", "repo", "list", org, "--limit", "100", "--json", "name,isArchived"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"    [WARN] gh repo list failed: {result.stderr}", file=sys.stderr)
            return []
        repos = json.loads(result.stdout)
        return [r["name"] for r in repos if not r["isArchived"]]
    except Exception as e:
        print(f"    [WARN] gh repo list error: {e}", file=sys.stderr)
        return []


def get_merged_prs(org: str, repo: str, since_days: int) -> list[dict]:
    """Return list of merged PRs from repo in last N days via gh pr list.
    Date filtering is done in Python (gh pr list has no --merged-after flag)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    try:
        result = subprocess.run(
            ["gh", "pr", "list",
             "--repo", f"{org}/{repo}",
             "--state", "merged",
             "--limit", "100",
             "--json", "number,title,body,mergedAt,url,labels"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
        all_prs = json.loads(result.stdout)
        prs = []
        for pr in all_prs:
            try:
                merged = datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
                if merged >= cutoff:
                    prs.append(pr)
            except (KeyError, ValueError):
                continue
        prs.sort(key=lambda p: p.get("mergedAt", ""), reverse=True)
        return prs
    except Exception:
        return []


def count_merged_prs(org: str, repo: str, since_days: int) -> int:
    """Fast count of merged PRs in period — used for min-activity filtering."""
    return len(get_merged_prs(org, repo, since_days))


# ─── MAIN ────────────────────────────────────────────────────────────────────

LESSONS_DIR = Path(__file__).parent.parent.parent / "memory" / "vault" / "lessons"
DEFAULT_ORG = "living"


def build_lesson_path(merged_at: str, org: str, repo: str, pr_number: int, subject: str) -> Path:
    """Build idempotent lesson path: YYYY-MM-DD-slug-subhash.md"""
    date_brazil = None
    try:
        date_brazil = datetime.fromisoformat(merged_at.replace("Z", "+00:00")) - timedelta(hours=3)
    except Exception:
        date_brazil = datetime.now()
    date_str = date_brazil.strftime("%Y-%m-%d")
    slug = slugify(subject)
    source_ref = f"{org}/{repo}/pull/{pr_number}"
    subhash = hashlib.sha256(source_ref.encode()).hexdigest()[:6]
    return LESSONS_DIR / f"{date_str}-{slug}-{subhash}.md"


def run(
    org: str,
    repos: list[str] | None,
    since_days: int,
    model: str,
    dry_run: bool,
    min_activity: int,
) -> dict:
    """
    Main extraction loop. Returns JSON-serializable summary.

    If repos is None, discover active repos (those with merged PRs in period).
    Filter to repos with >= min_activity merged PRs.
    """
    # Discover repos if not specified
    if repos is None:
        print(f"[honcho_capture] Discovering repos in org {org} with >= {min_activity} merged PRs in last {since_days} days...")
        all_repos = list_org_repos(org)
        discovered = []
        for repo in all_repos:
            count = count_merged_prs(org, repo, since_days)
            if count >= min_activity:
                discovered.append((repo, count))
        repos = [r[0] for r in discovered]
        print(f"[honcho_capture] Discovered {len(repos)} active repos: {repos}")
    else:
        print(f"[honcho_capture] Processing {len(repos)} repos: {repos}")

    summary = {
        "lessons_written": 0,
        "sources": {},
        "skipped": 0,
        "errors": [],
    }

    for repo in repos:
        prs = get_merged_prs(org, repo, since_days)
        summary["sources"][repo] = {
            "prs_found": len(prs),
            "processed": 0,
            "skipped_existing": 0,
            "errors": 0,
        }

        print(f"\n[honcho_capture] {org}/{repo}: {len(prs)} merged PRs in last {since_days} days")

        for pr in prs:
            number = pr["number"]
            title = pr["title"]
            body = pr.get("body") or ""
            merged_at = pr["mergedAt"]
            url = pr["url"]
            labels = pr.get("labels", []) or []

            subject = f"PR #{number} — {title}"
            path = build_lesson_path(merged_at, org, repo, number, subject)

            # Idempotency check
            if path.exists():
                print(f"  [SKIP] {path.name} already exists")
                summary["sources"][repo]["skipped_existing"] += 1
                summary["skipped"] += 1
                continue

            if dry_run:
                print(f"  [DRY] Would write: {path.name}")
                summary["sources"][repo]["processed"] += 1
                continue

            # Extract via LLM
            summary["sources"][repo]["processed"] += 1
            print(f"  [PROC] PR #{number}: {title[:60]}")

            content = extract_lesson_via_llm(
                org, repo, number, title, body, merged_at, url, model
            )
            if content is None:
                summary["sources"][repo]["errors"] += 1
                summary["errors"].append(f"{org}/{repo}#{number}: LLM call failed")
                continue

            # Check if trivial
            fm = parse_frontmatter(content)
            if fm.get("skip_reason") == "trivial":
                print(f"    [SKIP] Trivial PR — no lesson written")
                summary["skipped"] += 1
                summary["sources"][repo]["skipped_existing"] += 1
                continue

            # Write
            try:
                path.write_text(content.strip() + "\n")
                print(f"    [WROTE] {path.name}")
                summary["lessons_written"] += 1
            except Exception as e:
                summary["sources"][repo]["errors"] += 1
                summary["errors"].append(f"{org}/{repo}#{number}: write failed — {e}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="honcho_capture — extract lessons from GitHub PRs")
    parser.add_argument("--org", default=DEFAULT_ORG, help=f"GitHub org (default: {DEFAULT_ORG})")
    parser.add_argument("--repos", nargs="*", default=None,
                        help="Specific repos (default: auto-discover active repos)")
    parser.add_argument("--days", type=int, default=1, help="Look back N days (default: 1)")
    parser.add_argument("--min-activity", type=int, default=1,
                        help="Min merged PRs in period to process a repo (default: 1)")
    parser.add_argument("--model", type=str, default=MODEL, help=f"OpenAI model (default: {MODEL})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be written")
    args = parser.parse_args()

    result = run(
        org=args.org,
        repos=args.repos,
        since_days=args.days,
        model=args.model,
        dry_run=args.dry_run,
        min_activity=args.min_activity,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
