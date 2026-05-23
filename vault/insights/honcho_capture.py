#!/usr/bin/env python3
"""
honcho_capture.py — ETL para extrair lições de GitHub PRs e escrever em memory/vault/lessons/

Usage:
    python3 vault/insights/honcho_capture.py --days 1
    python3 vault/insights/honcho_capture.py --days 7 --model gpt-4o-mini

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

# ─── SLUGIFY (language-agnostic, same as spec) ───────────────────────────────

def slugify(text: str) -> str:
    """Slugify per spec: lowercase, spaces→hyphens, strip non-alphanumeric.
    Handles em/en dashes and # by converting to spaces first.
    Example: 'PR #24 — Enriched Claims Rollout' → 'pr-24-enriched-claims-rollout'"""
    text = text.replace("\u2014", " ").replace("\u2013", " ").replace("#", " ")
    text = text.lower()
    text = re.sub(r"[^a-z0-9- ]", "", text)  # strip non-alphanumeric (KEEP spaces & hyphens)
    text = text.replace(" ", "-")
    return re.sub(r"-+", "-", text).strip("-")

# ─── LLM EXTRACTION ───────────────────────────────────────────────────────────

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = "gpt-4o-mini"   # fastest equivalent (gpt-5-mini quando disponível)

SYSTEM_PROMPT = """You are a senior engineer writing a concise lesson from a GitHub PR.
Output ONLY valid YAML frontmatter + lesson body in Portuguese (BR).
No markdown code fences around the YAML. No commentary.

Rules:
- type: lesson
- source: github
- source_ref: "living/livy-memory-bot/pull/{pr_number}"
- date: YYYY-MM-DD (BRT = UTC-3)
- subject: "PR #N — title"
- author: extracted from PR data
- tags: [category tags]
- Format rest as:
## O que aconteceu
[neutral description]

## Decisão / Solução
[what was decided/done]

## Lessons
- [lesson 1]
- [lesson 2]
- [lesson 3]

## Source
[GitHub PR URL]

If the PR is trivial (typo fix, chore, dependency bump) with no meaningful lesson, output ONLY:
---
type: lesson
skip_reason: trivial
---
"""


def extract_lesson_via_llm(pr_title: str, pr_body: str, pr_number: int, merged_at: str, pr_url: str, model: str) -> str | None:
    """Call LLM to extract a lesson from a PR. Returns YAML+body or None on failure."""
    user_prompt = f"""PR #{pr_number}: {pr_title}

{('Body:\n' + pr_body) if pr_body else '(no body)'}

Merged: {merged_at}
URL: {pr_url}
"""

    try:
        import urllib.request
        import urllib.error

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(pr_number=pr_number)},
                {"role": "user", "content": user_prompt}
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

def get_merged_prs(repo: str, since_days: int) -> list[dict]:
    """Return list of merged PRs from last N days via gh pr list.
    Date filtering is done in Python (gh pr list has no --merged-after flag)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    try:
        result = subprocess.run(
            ["gh", "pr", "list",
             "--repo", repo,
             "--state", "merged",
             "--limit", "100",
             "--json", "number,title,body,mergedAt,url,labels"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"    [WARN] gh pr list failed: {result.stderr}", file=sys.stderr)
            return []
        all_prs = json.loads(result.stdout)
        # Filter by mergedAt date in Python
        prs = []
        for pr in all_prs:
            try:
                merged = datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
                if merged >= cutoff:
                    prs.append(pr)
            except (KeyError, ValueError):
                continue
        # Sort by mergedAt descending
        prs.sort(key=lambda p: p.get("mergedAt", ""), reverse=True)
        return prs
    except Exception as e:
        print(f"    [WARN] gh pr list error: {e}", file=sys.stderr)
        return []


# ─── MAIN ────────────────────────────────────────────────────────────────────

LESSONS_DIR = Path(__file__).parent.parent.parent / "memory" / "vault" / "lessons"


def build_lesson_path(merged_at: str, pr_number: int, subject: str) -> Path:
    """Build idempotent lesson path: YYYY-MM-DD-slug-subhash.md"""
    date_brazil = datetime.fromisoformat(merged_at.replace("Z", "+00:00")) - timedelta(hours=3)
    date_str = date_brazil.strftime("%Y-%m-%d")
    slug = slugify(subject)
    source_ref = f"living/livy-memory-bot/pull/{pr_number}"
    subhash = hashlib.sha256(source_ref.encode()).hexdigest()[:6]
    return LESSONS_DIR / f"{date_str}-{slug}-{subhash}.md"


def run(days: int, model: str, dry_run: bool) -> dict:
    """Main extraction loop. Returns JSON-serializable summary."""
    repo = "living/livy-memory-bot"
    prs = get_merged_prs(repo, days)

    summary = {
        "lessons_written": 0,
        "sources": {"github": {"prs_found": len(prs), "processed": 0, "skipped_existing": 0, "errors": 0}},
        "skipped": 0,
        "errors": [],
    }

    print(f"[honcho_capture] Found {len(prs)} merged PRs in last {days} days for {repo}")

    for pr in prs:
        number = pr["number"]
        title = pr["title"]
        body = pr.get("body") or ""
        merged_at = pr["mergedAt"]  # ISO format: "2026-04-22T02:25:27Z"
        url = pr["url"]
        labels = pr.get("labels", []) or []

        subject = f"PR #{number} — {title}"
        path = build_lesson_path(merged_at, number, subject)

        # Idempotency check
        if path.exists():
            print(f"  [SKIP] {path.name} already exists")
            summary["sources"]["github"]["skipped_existing"] += 1
            summary["skipped"] += 1
            continue

        if dry_run:
            print(f"  [DRY] Would write: {path.name}")
            summary["sources"]["github"]["processed"] += 1
            continue

        # Extract via LLM
        summary["sources"]["github"]["processed"] += 1
        print(f"  [PROC] PR #{number}: {title[:60]}")

        content = extract_lesson_via_llm(title, body, number, merged_at, url, model)
        if content is None:
            summary["sources"]["github"]["errors"] += 1
            summary["errors"].append(f"PR #{number}: LLM call failed")
            continue

        # Parse — check if trivial
        fm = parse_frontmatter(content)
        if fm.get("skip_reason") == "trivial":
            print(f"    [SKIP] Trivial PR #{number} — no lesson written")
            summary["skipped"] += 1
            summary["sources"]["github"]["skipped_existing"] += 1
            continue

        # Write
        try:
            path.write_text(content.strip() + "\n")
            print(f"    [WROTE] {path.name}")
            summary["lessons_written"] += 1
        except Exception as e:
            summary["sources"]["github"]["errors"] += 1
            summary["errors"].append(f"PR #{number}: write failed — {e}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="honcho_capture — extract lessons from GitHub PRs")
    parser.add_argument("--days", type=int, default=1, help="Look back N days (default: 1)")
    parser.add_argument("--model", type=str, default=MODEL, help=f"OpenAI model (default: {MODEL})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be written without writing")
    args = parser.parse_args()

    result = run(days=args.days, model=args.model, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
