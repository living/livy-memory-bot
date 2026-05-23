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

import sys
from pathlib import Path

# Ensure project root is on sys.path so `vault.research.*` imports work
_WS_ROOT = Path(__file__).resolve().parents[2]
if str(_WS_ROOT) not in sys.path:
    sys.path.insert(0, str(_WS_ROOT))

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

# ─── HONCHO CONFIG ─────────────────────────────────────────────────────────────

HONCHO_BASE = os.environ.get("HONCHO_BASE", "http://100.121.74.111:8000")
HONCHO_API_KEY = os.environ.get("HONCHO_API_KEY", "")
HONCHO_WORKSPACE = os.environ.get("HONCHO_WORKSPACE_ID", "openclaw")
HONCHO_AGENT_PEER = os.environ.get("HONCHO_AGENT_PEER", "agent-memory-agent")


def _honcho_headers() -> dict:
    return {"Authorization": f"Bearer {HONCHO_API_KEY}"} if HONCHO_API_KEY else {}


def index_lesson_to_honcho(path: Path) -> bool:
    """Index a lesson file to Honcho conclusions API.
    
    Reads frontmatter + body, posts to POST /v3/workspaces/{id}/conclusions.
    Returns True on success, False on failure.
    Silently skips on error (lesson is already on disk).
    """
    try:
        content = path.read_text()
        lines = content.split("\n")
        frontmatter = {}
        in_fm = False
        fm_lines, body_lines = [], []
        for l in lines:
            if l.strip() == "---":
                in_fm = not in_fm
                continue
            (fm_lines if in_fm else body_lines).append(l)
        for l in fm_lines:
            if ":" in l:
                k, v = l.split(":", 1)
                frontmatter[k.strip()] = v.strip().strip('"')
        body = "\n".join(body_lines).strip()
        subject = frontmatter.get("subject", path.stem)
        date = frontmatter.get("date", "")
        body_short = body[:1000].replace("\n", " ")
        payload = {
            "conclusions": [{
                "content": f"{subject} | {date} | {body_short}",
                "observer_id": HONCHO_AGENT_PEER,
                "observed_id": HONCHO_AGENT_PEER,
            }]
        }
        r = httpx.post(
            f"{HONCHO_BASE}/v3/workspaces/{HONCHO_WORKSPACE}/conclusions",
            json=payload,
            headers=_honcho_headers(),
            timeout=15,
        )
        if r.status_code == 201:
            cid = r.json()[0].get("id", "?")[:12]
            print(f"    [HONCHO] indexed {cid}")
            return True
        else:
            print(f"    [HONCHO] index failed ({r.status_code}): {r.text[:80]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"    [HONCHO] index error: {e}", file=sys.stderr)
        return False


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

SYSTEM_PROMPT_TEMPLATE = """You are a senior engineer writing a concise lesson from a GitHub {item_type}.
Output ONLY valid YAML frontmatter + lesson body in Portuguese (BR).
No markdown code fences around the YAML. No commentary.

Rules:
- type: lesson
- source: github
- source_ref: "{source_ref}"
- date: {item_date} (BRT = UTC-3)
- subject: "{item_type} #N — title"
- author: extracted from data or 'unknown'
- cycle_time: {cycle_time}  (time from first commit to merge, e.g. "2h 30m")
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
[GitHub URL]

If the item is trivial (typo fix, chore, dependency bump, docs-only) with no meaningful decision or lesson, output ONLY:
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
    source_type: str = "pr",
    item_date: str | None = None,
    created_at: str = "",
) -> str | None:
    """Call LLM to extract a lesson from a PR or Issue. Returns YAML+body or None on failure."""
    if source_type == "issues":
        source_ref = f"{org}/{repo}/issues/{pr_number}"
        item_type = "Issue"
    else:
        source_ref = f"{org}/{repo}/pull/{pr_number}"
        item_type = "PR"
    # Compute cycle_time: merged_at - created_at
    cycle_time = ""
    if created_at and merged_at:
        try:
            c = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            m = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
            delta = m - c
            total_minutes = int(delta.total_seconds() / 60)
            if total_minutes < 60:
                cycle_time = f"{total_minutes}m"
            elif total_minutes < 1440:
                cycle_time = f"{total_minutes//60}h {total_minutes%60}m"
            else:
                cycle_time = f"{total_minutes//1440}d {(total_minutes%1440)//60}h"
        except Exception:
            cycle_time = ""
    user_prompt = f"""{item_type} #{pr_number}: {pr_title}

{('Body:\n' + pr_body) if pr_body else '(no body)'}

Created: {created_at}
Merged: {merged_at}
Cycle time: {cycle_time}
URL: {pr_url}"""

    try:
        import urllib.request
        import urllib.error

        if item_date is None:
            try:
                item_date = (datetime.fromisoformat(merged_at.replace("Z", "+00:00")) - timedelta(hours=3)).strftime("%Y-%m-%d")
            except Exception:
                item_date = "YYYY-MM-DD"
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(item_type=item_type, source_ref=source_ref, item_date=item_date, cycle_time=cycle_time or "N/A")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
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


def get_merged_prs(org: str, repo: str, since_days: int = 1, after: str | None = None, before: str | None = None) -> list[dict]:
    """Return merged PRs from repo. Date range: lookback cutoff + optional after/before range."""
    # cutoff only applies when no explicit date range given
    has_explicit_range = bool(after or before)
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days) if not has_explicit_range else None
    try:
        result = subprocess.run(
            ["gh", "pr", "list",
             "--repo", f"{org}/{repo}",
             "--state", "merged",
             "--limit", "100",
             "--json", "number,title,body,mergedAt,url,labels,createdAt"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
        all_prs = json.loads(result.stdout)
        prs = []
        for pr in all_prs:
            try:
                merged = datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
                if cutoff and merged < cutoff:
                    continue
                if after:
                    after_dt = datetime.fromisoformat(after).replace(tzinfo=timezone.utc)
                    if merged < after_dt:
                        continue
                if before:
                    before_dt = datetime.fromisoformat(before).replace(tzinfo=timezone.utc)
                    if merged > before_dt:
                        continue
                prs.append(pr)
            except (KeyError, ValueError):
                continue
        prs.sort(key=lambda p: p.get("mergedAt", ""), reverse=True)
        return prs
    except Exception:
        return []


def count_merged_prs(org: str, repo: str, since_days: int, after: str | None = None, before: str | None = None) -> int:
    """Fast count of merged PRs in period — used for min-activity filtering."""
    return len(get_merged_prs(org, repo, since_days, after=after, before=before))


def get_closed_issues(org: str, repo: str, since_days: int = 1, after: str | None = None, before: str | None = None) -> list[dict]:
    """Return closed issues from last N days. Date range: lookback cutoff + optional after/before."""
    has_explicit_range = bool(after or before)
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days) if not has_explicit_range else None
    try:
        result = subprocess.run(
            ["gh", "issue", "list",
             "--repo", f"{org}/{repo}",
             "--state", "closed",
             "--limit", "100",
             "--json", "number,title,body,closedAt,url,labels"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
        all_issues = json.loads(result.stdout)
        issues = []
        for issue in all_issues:
            try:
                closed = datetime.fromisoformat(issue["closedAt"].replace("Z", "+00:00"))
                if cutoff and closed < cutoff:
                    continue
                if after:
                    after_dt = datetime.fromisoformat(after).replace(tzinfo=timezone.utc)
                    if closed < after_dt:
                        continue
                if before:
                    before_dt = datetime.fromisoformat(before).replace(tzinfo=timezone.utc)
                    if closed > before_dt:
                        continue
                issues.append(issue)
            except (KeyError, ValueError):
                continue
        issues.sort(key=lambda i: i.get("closedAt", ""), reverse=True)
        return issues
    except Exception:
        return []


# ─── MAIN ────────────────────────────────────────────────────────────────────

LESSONS_DIR = Path(__file__).parent.parent.parent / "memory" / "vault" / "lessons"
DEFAULT_ORG = "living"


def build_lesson_path(merged_at: str, org: str, repo: str, pr_number: int, subject: str, source_type: str = "pr") -> Path:
    """Build idempotent lesson path: YYYY-MM-DD-slug-subhash.md"""
    date_brazil = None
    try:
        date_brazil = datetime.fromisoformat(merged_at.replace("Z", "+00:00")) - timedelta(hours=3)
    except Exception:
        date_brazil = datetime.now()
    date_str = date_brazil.strftime("%Y-%m-%d")
    slug = slugify(subject)
    if source_type == "issues":
        source_ref = f"{org}/{repo}/issues/{pr_number}"
    else:
        source_ref = f"{org}/{repo}/pull/{pr_number}"
    subhash = hashlib.sha256(source_ref.encode()).hexdigest()[:6]
    return LESSONS_DIR / f"{date_str}-{slug}-{subhash}.md"


def build_trello_lesson_path(updated_at: str, board_name: str, card_id: str, card_name: str) -> Path:
    """Build lesson path for a Trello card."""
    date_brazil = None
    try:
        date_brazil = datetime.fromisoformat(updated_at.replace("Z", "+00:00")) - timedelta(hours=3)
    except Exception:
        date_brazil = datetime.now()
    date_str = date_brazil.strftime("%Y-%m-%d")
    slug = slugify(card_name)
    source_ref = f"trello/{card_id}"
    subhash = hashlib.sha256(source_ref.encode()).hexdigest()[:6]
    return LESSONS_DIR / f"{date_str}-{slug}-{subhash}.md"


def build_tldv_lesson_path(meeting_id: str, meeting_name: str, meeting_date: str) -> Path:
    """Build lesson path for a TLDV meeting. Uses meeting_id for uniqueness."""
    slug = slugify(meeting_name)
    source_ref = f"tldv/{meeting_id}"
    subhash = hashlib.sha256(source_ref.encode()).hexdigest()[:6]
    return LESSONS_DIR / f"{meeting_date}-{slug}-{subhash}.md"


def inject_tldv_frontmatter(lesson_body: str, meeting_id: str, meeting_name: str, meeting_date: str, project: str) -> str:
    """Inject YAML frontmatter if lesson body doesn't have it.
    The LLM often skips frontmatter; this ensures every lesson has one.
    """
    if lesson_body.strip().startswith("---"):
        return lesson_body  # already has frontmatter

    import re
    # Try to extract subject and date from first heading: ## Meeting: {name} ({date})
    m = re.match(r"##\s+Meeting:\s+(.+?)\s+\((\d{4}-\d{2}-\d{2})\)", lesson_body.strip())
    if m:
        extracted_name = m.group(1).strip()
        extracted_date = m.group(2).strip()
    else:
        extracted_name = meeting_name
        extracted_date = meeting_date

    fm_lines = [
        "---",
        f"type: lesson",
        f"source: tldv",
        f"source_ref: \"tldv/{meeting_id}\"",
        f"date: {extracted_date}",
        f"subject: \"{extracted_name}\"",
        f"project: {project}",
        f"tags: [{project.lower()}, tldv, meeting]",
        "---",
        "",
    ]
    return "\n".join(fm_lines) + lesson_body.strip()


# ─── TLDV SYNTHESIS ───────────────────────────────────────────────────────────


def extract_project_tag(name: str) -> str | None:
    """Extract project tag from meeting name (case-insensitive).
    Returns the first known tag found in the name (left-to-right).
    E.g. 'Status Kaba/BAT/BOT' -> 'KABA' (first occurrence in name).
    """
    import re
    KNOWN = {"DELPHOS", "BAT", "HYDRA", "FORGE", "TLDV", "LIVY", "SVD", "KABA", "BOT"}
    name_upper = name.upper()
    # Find all known tags that appear in the name, in order of appearance
    found = []
    for tag in KNOWN:
        if tag in name_upper:
            idx = name_upper.index(tag)
            found.append((idx, tag))
    if found:
        found.sort(key=lambda x: x[0])
        return found[0][1]
    return None


def synthesize_tldv_via_llm(project: str, transcripts: list[dict], model: str, lesson_date: str | None = None, n_meetings: int = 0) -> str | None:
    """Synthesize multiple meeting transcripts into one lesson via LLM."""
    if lesson_date is None:
        lesson_date = datetime.now().strftime("%Y-%m-%d")
    transcript_summary = "\n\n".join(
        f"=== {t['name']} ({t['date']}) ===\n{t['transcript'][:2000]}"
        for t in transcripts
    )
    prompt = f"""You are a senior engineer synthesizing {n_meetings} meeting transcripts into one concise lesson.
Project: {project}

TRANSCRIPTS:
{transcript_summary}

Task: Identify recurring decisions, agreements, action items, and blockers across these meetings.
Output ONLY valid YAML frontmatter + lesson body in Portuguese (BR). No code fences.

Rules:
- type: lesson
- source: tldv
- source_ref: "tldv/{project}/synthesis"
- date: {lesson_date}
- subject: "[Síntese] {project} — {n_meetings} reuniões"
- tags: [{project.lower()}, synthesis, meetings]

Format:
## O que aconteceu
[What was discussed across these meetings]

## Decisões identificadas
[List of specific decisions made]

## Lessons
- [lesson 1]
- [lesson 2]
- [lesson 3]

## Source
Auto-generated from TLDV transcripts (Azure Blob)
"""

    try:
        import urllib.request

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 800,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"    [WARN] LLM call failed: {e}", file=sys.stderr)
        return None


def extract_tldv_lessons(since_days: int, model: str, dry_run: bool = False,
                          after: str | None = None, before: str | None = None) -> list[tuple[str,str,str,str,str]]:
    """
    Extract one lesson per TLDV meeting transcript (individual, not grouped).
    Fetches all meetings in lookback window, then filters by after/before range.
    For each meeting with a transcript, extracts a full lesson with:
      - to-do / action items
      - decisions made
      - blockers / open questions
      - participants
    Transcript source: Azure Blob primary + Supabase fallback.
    """
    from vault.research.tldv_client import TLDVClient
    from vault.capture.azure_blob_client import load_transcript_segments

    effective_days = max(since_days, 90)
    client = TLDVClient(lookback_days=effective_days)

    try:
        meetings = client.fetch_events_since(None)
    except Exception as e:
        print(f"    [WARN] TLDV client error: {e}", file=sys.stderr)
        return []

    # Filter by date range
    if after or before:
        after_dt = datetime.fromisoformat(after).replace(tzinfo=timezone.utc) if after else None
        before_dt = datetime.fromisoformat(before).replace(tzinfo=timezone.utc) if before else None
        filtered = []
        for m in meetings:
            date_val = m.get("created_at") or m.get("updated_at") or ""
            if not date_val:
                continue
            try:
                dt = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                if after_dt and dt < after_dt:
                    continue
                if before_dt and dt > before_dt:
                    continue
                filtered.append(m)
            except Exception:
                continue
        meetings = filtered
        print(f"    [TLDV] {len(meetings)} meetings in date range")

    lessons = []
    for meeting in meetings:
        meeting_id = meeting.get("meeting_id", "") or meeting.get("id", "")
        if not meeting_id:
            continue

        # Extract transcript
        try:
            segments = load_transcript_segments(meeting_id)
            if not segments:
                continue
            transcript = " ".join(s.get("text", "") or "" for s in segments)
            if len(transcript.strip()) < 50:
                continue
        except Exception:
            continue

        # Date in BRT
        date_val = meeting.get("created_at") or meeting.get("updated_at", "")
        try:
            date_br = datetime.fromisoformat(date_val.replace("Z", "+00:00")) - timedelta(hours=3)
            date_str = date_br.strftime("%Y-%m-%d")
        except Exception:
            date_str = datetime.now().strftime("%Y-%m-%d")

        name = meeting.get("name", "meeting")
        project = extract_project_tag(name) or "general"

        print(f"  [PROC] TLDV: {name[:50]} ({date_str})")
        lesson = extract_tldv_lesson_via_llm(
            meeting_id=meeting_id,
            meeting_name=name,
            meeting_date=date_str,
            project=project,
            transcript=transcript[:8000],  # generous but bounded
            model=model,
        )
        if lesson:
            # Inject frontmatter (LLM often skips it)
            lesson = inject_tldv_frontmatter(lesson, meeting_id, name, date_str, project)
            lessons.append((meeting_id, name, date_str, project, lesson))
    return lessons


def extract_tldv_lesson_via_llm(
    meeting_id: str,
    meeting_name: str,
    meeting_date: str,
    project: str,
    transcript: str,
    model: str,
) -> str | None:
    """Extract a structured lesson from a single meeting transcript."""
    prompt = f"""You are a senior engineer extracting a structured lesson from a meeting transcript.
Extract ALL of the following with maximum fidelity:

1. **To-do / Action items**: exact tasks assigned, who is responsible
2. **Decisions made**: specific conclusions reached, with context
3. **Blockers / Open questions**: what is blocked, why, who can unblock
4. **Deliverables / Outcomes**: what was produced, shipped, or decided
5. **Participant list**: names mentioned in the meeting

Meeting: {meeting_name}
Date: {meeting_date}
Project: {project}
Transcript excerpt (first 6000 chars):
{transcript[:6000]}

Output ONLY valid YAML frontmatter + lesson body in Portuguese (BR). No code fences.

Rules:
- type: lesson
- source: tldv
- source_ref: "tldv/{meeting_id}"
- date: {meeting_date}
- subject: "{meeting_name}"
- project: {project}
- tags: [{project.lower()}, tldv, meeting]

Format:
## Meeting: {meeting_name} ({meeting_date})

### To-do / Action Items
- [person]: [exact task] (deadline or context if available)

### Decisões
- [decision made and why]

### Blockers / Open Questions
- [blocker or open question]

### Deliverables / Outcomes
- [what was produced or decided]

### Participantes
- [list of names mentioned]

## Source
Auto-generated from TLDV transcript (Azure Blob)
"""

    try:
        import urllib.request
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1200,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"    [WARN] LLM call failed: {e}", file=sys.stderr)
        return None


def _get_card_metadata(card_id: str, card_desc: str, api_key: str, token: str, base: str) -> dict:
    """Fetch custom fields (effort) and extract PR references from card description.
    
    Returns: {\"effort\": int|None, \"pr_refs\": [str]}"""
    effort = None
    pr_refs = []
    # Extract PR URLs from description
    import re
    pr_urls = re.findall(r'https?://github\.com/([\w-]+)/([\w.-]+)/pull/(\d+)', card_desc)
    for org, repo, pr_num in pr_urls:
        pr_refs.append(f"{org}/{repo}#{pr_num}")
    # Fetch custom fields for this card
    try:
        req = urllib.request.Request(
            f"{base}/cards/{card_id}/customFields?key={api_key}&token={token}",
            headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            fields = json.loads(r.read())
        for field in fields:
            name = field.get("name", "").lower()
            if "effort" in name or "horas" in name or "hora" in name:
                val = field.get("value")
                if val:
                    # number type
                    effort = val.get("number")
    except Exception:
        pass
    return {"effort": effort, "pr_refs": pr_refs}


def get_updated_trello_cards(since_days: int, after: str | None = None, before: str | None = None) -> list[dict]:
    """Return Trello cards updated in date range via ALL boards the token can access.
    Fetches all boards via /1/members/me/boards, then cards from each board.
    Date range: after + before (in addition to lookback cutoff).
    Each card dict includes effort (from custom fields) and pr_refs (from desc URLs)."""
    try:
        import os, urllib.request
        TRELLO_API_KEY = os.environ.get("TRELLO_API_KEY", "")
        TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN", "")
        TRELLO_BASE = "https://api.trello.com/1"
        if not TRELLO_API_KEY or not TRELLO_TOKEN:
            print(f"    [WARN] TRELLO_API_KEY or TRELLO_TOKEN not set", file=sys.stderr)
            return []
        # When after/before are provided, use them as the primary date filter.
        # The since_days cutoff only applies when no explicit after/before is given.
        if after:
            cutoff = datetime.fromisoformat(after.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        # Fetch all boards the token can access
        req = urllib.request.Request(
            f"{TRELLO_BASE}/members/me/boards?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}&fields=id,name",
            headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            boards = json.loads(resp.read())
        print(f"    [TRELLO] Found {len(boards)} boards")
        cards = []
        for board in boards:
            board_id = board["id"]
            board_name = board["name"]
            # Fetch cards for this board
            try:
                req2 = urllib.request.Request(
                    f"{TRELLO_BASE}/boards/{board_id}/cards?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
                    "&fields=id,name,desc,dateLastActivity,shortUrl&idList&limit=1000",
                    headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req2, timeout=15) as r:
                    board_cards = json.loads(r.read())
            except Exception:
                continue
            for card in board_cards:
                try:
                    updated_str = card.get("dateLastActivity", "")
                    if not updated_str:
                        continue
                    updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    if updated < cutoff:
                        continue
                    if after:
                        after_dt = datetime.fromisoformat(after).replace(tzinfo=timezone.utc)
                        if updated < after_dt:
                            continue
                    if before:
                        before_dt = datetime.fromisoformat(before).replace(tzinfo=timezone.utc)
                        if updated > before_dt:
                            continue
                    card_id = card.get("id", "")
                    meta = _get_card_metadata(card_id, card.get("desc", "") or "", TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_BASE)
                    cards.append({
                        "id": card_id,
                        "name": card.get("name", ""),
                        "desc": card.get("desc", "") or "",
                        "dateLastActivity": updated_str,
                        "shortUrl": card.get("shortUrl", ""),
                        "_board_name": board_name,
                        "effort": meta["effort"],
                        "pr_refs": meta["pr_refs"],
                    })
                except Exception:
                    continue
        cards.sort(key=lambda c: c.get("dateLastActivity", ""), reverse=True)
        print(f"    [TRELLO] {len(cards)} cards in date range")
        return cards
    except Exception as e:
        print(f"    [WARN] Trello client error: {e}", file=sys.stderr)
        return []


def extract_trello_lesson_via_llm(card_name: str, card_desc: str, board_name: str, url: str, updated: str, model: str, card_id: str = "", effort: int | None = None, pr_refs: list[str] | None = None) -> str | None:
    """Extract lesson from a Trello card via LLM."""
    pr_refs_str = "\n".join([f"- {r}" for r in (pr_refs or [])]) if pr_refs else "None"
    effort_str = str(effort) if effort is not None else "Not specified"
    user_prompt = f"""Card: {card_name}
Board: {board_name}
Description: {card_desc or '(no description)'}
Updated: {updated}
URL: {url}
Effort (hours): {effort_str}
Linked PRs:
{pr_refs_str}

Extract a lesson if this card represents a meaningful decision, process change, or architectural choice.
If it's a routine task or backlog item, return skip_reason=trivial."""

    system = """You are a senior engineer writing a concise lesson from a Trello card.
Output ONLY valid YAML frontmatter + lesson body in Portuguese (BR). No code fences.

Rules:
- type: lesson
- source: trello
- source_ref: "trello/{card_id}"
- date: YYYY-MM-DD (BRT = UTC-3)
- subject: "Trello: {card_name} [{board_name}]"
- effort: {effort}  (hours, omit if not specified)
- pr_refs: [{pr_refs_str}]  (list of org/repo#pr, omit if none)
- tags: [trello, {board_name_slug}]

Format:
## O que aconteceu
[What this card represents]

## Decisão / Solução
[The decision or process captured]

## Lessons
- [lesson 1]
- [lesson 2]

## Source
[URL]

If trivial (backlog item, routine task, no decision), output ONLY:
---
type: lesson
skip_reason: trivial
---
"""

    try:
        import urllib.request
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system.format(board_name_slug=slugify(board_name), card_id=card_id, card_name=card_name, board_name=board_name, effort=effort_str, pr_refs_str=", ".join(pr_refs) if pr_refs else "none")},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 600,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"    [WARN] LLM call failed: {e}", file=sys.stderr)
        return None


def run(
    org: str,
    repos: list[str] | None,
    since_days: int,
    model: str,
    dry_run: bool,
    min_activity: int,
    source: str = "github-prs",
    after: str | None = None,
    before: str | None = None,
) -> dict:
    """
    Main extraction loop. Returns JSON-serializable summary.

    If repos is None, discover active repos (those with merged PRs in period).
    Filter to repos with >= min_activity merged PRs.
    """
    # Short-circuit: non-GitHub sources skip repo discovery entirely
    if source in ("trello", "tldv-synthesis"):
        summary = {
            "lessons_written": 0,
            "sources": {},
            "skipped": 0,
            "errors": [],
        }
        if source == "trello":
            cards = get_updated_trello_cards(since_days, after=after, before=before)
            summary["sources"]["trello"] = {"cards_found": len(cards), "processed": 0, "skipped_existing": 0, "errors": 0}
            print(f"\n[honcho_capture] Trello: {len(cards)} cards updated in last {since_days} days")
            for card in cards:
                card_id = card.get("id", "")
                name = card.get("name", "")
                desc = card.get("desc", "") or ""
                board_name = card.get("_board_name", "")
                updated = card.get("dateLastActivity", "")
                url = card.get("shortUrl", "")
                effort = card.get("effort")
                pr_refs = card.get("pr_refs") or []
                subject = f"Trello: {name} [{board_name}]"
                source_ref = f"trello/{card.get('id', '')}"
                path = build_trello_lesson_path(updated, board_name, card_id, name)
                if path.exists():
                    print(f"  [SKIP] {path.name} already exists")
                    summary["sources"]["trello"]["skipped_existing"] += 1
                    summary["skipped"] += 1
                    continue
                if dry_run:
                    print(f"  [DRY] Would write: {path.name}")
                    summary["sources"]["trello"]["processed"] += 1
                    continue
                summary["sources"]["trello"]["processed"] += 1
                print(f"  [PROC] Card: {name[:50]}")
                content = extract_trello_lesson_via_llm(name, desc, board_name, url, updated, model, card_id, effort, pr_refs)
                if content is None:
                    summary["sources"]["trello"]["errors"] += 1
                    summary["errors"].append(f"trello/{card_id}: LLM call failed")
                    continue
                fm = parse_frontmatter(content)
                if fm.get("skip_reason") == "trivial":
                    print(f"    [SKIP] Trivial card")
                    summary["skipped"] += 1
                    continue
                try:
                    path.write_text(content.strip() + "\n")
                    print(f"    [WROTE] {path.name}")
                    summary["lessons_written"] += 1
                    index_lesson_to_honcho(path)
                except Exception as e:
                    summary["sources"]["trello"]["errors"] += 1
                    summary["errors"].append(f"trello/{card_id}: write failed — {e}")
        elif source == "tldv-synthesis":
            raw_lessons = extract_tldv_lessons(since_days, model, dry_run, after=after, before=before)
            summary["sources"]["tldv"] = {"found": len(raw_lessons), "processed": 0, "errors": 0}
            for meeting_id, name, date_str, project, lesson in raw_lessons:
                path = build_tldv_lesson_path(meeting_id, name, date_str)
                if path.exists():
                    print(f"  [SKIP] {path.name} already exists")
                    summary["skipped"] += 1
                    continue
                if dry_run:
                    print(f"  [DRY] Would write: {path.name}")
                    summary["sources"]["tldv"]["processed"] += 1
                    continue
                try:
                    path.write_text(lesson.strip() + "\n")
                    print(f"    [WROTE] {path.name}")
                    summary["lessons_written"] += 1
                    summary["sources"]["tldv"]["processed"] += 1
                    index_lesson_to_honcho(path)
                except Exception as e:
                    summary["sources"]["tldv"]["errors"] += 1
                    summary["errors"].append(f"tldv/{meeting_id}: write failed — {e}")
        return summary

    # GitHub sources: discover or validate repos
    if repos is None:
        print(f"[honcho_capture] Discovering repos in org {org} with >= {min_activity} merged PRs in last {since_days} days...")
        all_repos = list_org_repos(org)
        discovered = []
        for repo in all_repos:
            count = count_merged_prs(org, repo, since_days, after=after, before=before)
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
        prs = get_merged_prs(org, repo, since_days, after=after, before=before)
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
            created_at = pr.get("createdAt", "")
            item_date = (datetime.fromisoformat(merged_at.replace("Z", "+00:00")) - timedelta(hours=3)).strftime("%Y-%m-%d")
            url = pr["url"]
            labels = pr.get("labels", []) or []

            subject = f"PR #{number} — {title}"
            path = build_lesson_path(merged_at, org, repo, number, subject, source_type="pr")

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
                org, repo, number, title, body, merged_at, url, model,
                source_type="pr", item_date=item_date, created_at=created_at
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
                index_lesson_to_honcho(path)
            except Exception as e:
                summary["sources"][repo]["errors"] += 1
                summary["errors"].append(f"{org}/{repo}#{number}: write failed — {e}")

        # ── GitHub Issues ────────────────────────────────────────────────────
        if source in ("github-all", "github-issues"):
            issues = get_closed_issues(org, repo, since_days, after=after, before=before)
            summary["sources"][repo]["issues_found"] = len(issues)
            print(f"\n[honcho_capture] {org}/{repo}: {len(issues)} closed issues in last {since_days} days")
            for issue in issues:
                number = issue["number"]
                title = issue["title"]
                body = issue.get("body") or ""
                closed_at = issue["closedAt"]
                item_date = (datetime.fromisoformat(closed_at.replace("Z", "+00:00")) - timedelta(hours=3)).strftime("%Y-%m-%d")
                url = issue["url"]
                labels = issue.get("labels", []) or []

                subject = f"Issue #{number} — {title}"
                path = build_lesson_path(closed_at, org, repo, number, subject, source_type="issues")

                if path.exists():
                    print(f"  [SKIP] {path.name} already exists")
                    summary["sources"][repo]["skipped_existing"] += 1
                    summary["skipped"] += 1
                    continue

                if dry_run:
                    print(f"  [DRY] Would write: {path.name}")
                    summary["sources"][repo]["processed"] += 1
                    continue

                summary["sources"][repo]["processed"] += 1
                print(f"  [PROC] Issue #{number}: {title[:60]}")

                content = extract_lesson_via_llm(
                    org, repo, number, title, body, closed_at, url, model, source_type="issues", item_date=item_date
                )
                if content is None:
                    summary["sources"][repo]["errors"] += 1
                    summary["errors"].append(f"{org}/{repo} issue#{number}: LLM call failed")
                    continue

                fm = parse_frontmatter(content)
                if fm.get("skip_reason") == "trivial":
                    print(f"    [SKIP] Trivial issue")
                    summary["skipped"] += 1
                    summary["sources"][repo]["skipped_existing"] += 1
                    continue

                try:
                    path.write_text(content.strip() + "\n")
                    print(f"    [WROTE] {path.name}")
                    summary["lessons_written"] += 1
                    index_lesson_to_honcho(path)
                except Exception as e:
                    summary["sources"][repo]["errors"] += 1
                    summary["errors"].append(f"{org}/{repo} issue#{number}: write failed — {e}")

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
    parser.add_argument("--source", nargs="*", default=["github-prs"],
                        choices=["github-prs", "github-issues", "github-all", "trello", "tldv-synthesis"],
                        help="Source type(s) to process (default: github-prs). Can specify multiple.")
    parser.add_argument("--after", type=str, default=None,
                        help="ISO date YYYY-MM-DD — only PRs/issues merged/closed on or after this date")
    parser.add_argument("--before", type=str, default=None,
                        help="ISO date YYYY-MM-DD — only PRs/issues merged/closed on or before this date")
    args = parser.parse_args()

    # Normalize: --source github-prs github-issues trello tldv-synthesis
    sources = args.source if args.source else ["github-prs"]
    # Validate each source
    all_choices = {"github-prs", "github-issues", "github-all", "trello", "tldv-synthesis"}
    for s in sources:
        if s not in all_choices:
            parser.error(f"invalid source: {s}")

    if len(sources) == 1:
        # Single source: same as before
        result = run(
            org=args.org,
            repos=args.repos,
            since_days=args.days,
            model=args.model,
            dry_run=args.dry_run,
            min_activity=args.min_activity,
            source=sources[0],
            after=args.after,
            before=args.before,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Multiple sources: run each sequentially, merge summaries
        merged = {
            "lessons_written": 0,
            "sources": {},
            "skipped": 0,
            "errors": [],
        }
        for src in sources:
            print(f"\n{'='*60}")
            print(f"[honcho_capture] Source: {src}")
            print(f"{'='*60}")
            r = run(
                org=args.org,
                repos=args.repos,
                since_days=args.days,
                model=args.model,
                dry_run=args.dry_run,
                min_activity=args.min_activity,
                source=src,
                after=args.after,
                before=args.before,
            )
            merged["lessons_written"] += r.get("lessons_written", 0)
            merged["skipped"] += r.get("skipped", 0)
            merged["errors"].extend(r.get("errors", []))
            for k, v in r.get("sources", {}).items():
                merged["sources"][k] = v
        print(f"\n{'='*60}")
        print(f"[honcho_capture] TOTAL SUMMARY")
        print(f"{'='*60}")
        print(json.dumps(merged, indent=2, ensure_ascii=False))
