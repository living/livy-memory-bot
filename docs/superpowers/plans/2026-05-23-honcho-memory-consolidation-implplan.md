# Honcho Memory Consolidation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full wisdom layer: `honcho_capture.py` ETL (multi-source) + `honcho-query` skill + Honcho peer integration.

**Architecture:** 4-layer: RAW sources → research pipeline → vault/claims (facts) → vault/lessons (wisdom, via honcho_capture) → Honcho (fast cache). Lessons are primary storage (versioned, portable); Honcho is fast semantic retrieval cache. Claude Mem stays until Honcho is mature.

**Tech Stack:** Python (ETL), OpenAI `gpt-4o-mini` (extraction), `gh pr list` (GitHub), `trello_client.py` (existing), `tldv_client.py` (existing), Honcho API (`honcho_search_conclusions`).

**Spec:** `docs/superpowers/specs/2026-05-23-honcho-memory-consolidation-design.md`

---

## Scope

| Source | PRs | Issues | Comments | Cards | Checklists | TLDV |
|--------|-----|--------|----------|-------|------------|------|
| GitHub | ✅ done | QW-3b | QW-3c | — | — | — |
| Trello | — | — | — | QW-3d | QW-3d | — |
| TLDV | — | — | — | — | — | QW-3e |

| Step | Status |
|------|--------|
| QW-0: Validate dates | ✅ done |
| QW-1: `memory/vault/lessons/` + TEMPLATE | ✅ done |
| QW-2: 5 manual lessons (PR #17,18,19,23,24) | ✅ done |
| QW-3: `honcho_capture.py` ETL (PRs only) | ✅ done |
| **QW-3b: GitHub Issues + Comments** | **TODO** |
| **QW-3d: Trello cards/checklists** | **TODO** |
| **QW-3e: TLDV synthesis** | **TODO** |
| **QW-5: `honcho-query` skill** | **TODO** |
| **QW-6: Validate Honcho retrieval** | **TODO** |

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `vault/insights/honcho_capture.py` | ✅ already created (PRs only) |
| `vault/insights/honcho_query.py` | Query skill: fast path Honcho, fallback disk |
| `tests/vault/insights/test_honcho_query.py` | Tests for query |
| `skills/honcho-query/SKILL.md` | OpenClaw skill definition |

### Existing Files (to reuse/extend)

| File | Role |
|------|------|
| `vault/research/github_client.py` | GitHub API (PRs) — already used by honcho_capture |
| `vault/research/trello_client.py` | Trello API — get_card_comments, get_card_checklists |
| `vault/research/tldv_client.py` | TLDV/Supabase — fetch_meeting summaries/decisions |
| `vault/insights/honcho_capture.py` | Extend with `--source github-issues`, `--source trello`, `--source tldv` |

---

## Phase 1 — Complete GitHub PRs (QW-5, QW-6)

### QW-5: Create `honcho-query` Skill

**Files:**
- Create: `vault/insights/honcho_query.py`
- Create: `tests/vault/insights/test_honcho_query.py`
- Create: `skills/honcho-query/SKILL.md`
- Modify: `skills/vault-query/SKILL.md` (add Honcho fallback)

---

#### Task QW-5.1: `honcho_query(query, topK=5)` — Fast Path Honcho

- [ ] **Step 1: Write failing test**

```python
# tests/vault/insights/test_honcho_query.py
import pytest, httpx, json
from unittest.mock import patch, Mock

def test_honcho_fast_path_returns_lessons(monkeypatch):
    """When Honcho returns results, they are returned as lesson dicts."""
    mock_response = {
        "conclusions": [
            {"text": "PR #24 — Enriched Claims Rollout", "id": "c1", "score": 0.95},
            {"text": "PR #23 — Self-Healing Apply V2", "id": "c2", "score": 0.88},
        ]
    }
    monkeypatch.setattr("vault.insights.honcho_query.honcho_health_check", lambda: True)
    with patch("httpx.post", return_value=Mock(json=lambda: mock_response)):
        from vault.insights.honcho_query import honcho_query
        results = honcho_query("enriched claims quality guardrail", topK=2)
        assert len(results) == 2
        assert results[0]["text"] == "PR #24 — Enriched Claims Rollout"
```

- [ ] **Step 2: Run test — verify it FAILS (module doesn't exist)**

Run: `pytest tests/vault/insights/test_honcho_query.py::test_honcho_fast_path_returns_lessons -v`
Expected: `ModuleNotFoundError: No module named 'vault.insights.honcho_query'`

- [ ] **Step 3: Write minimal `honcho_query.py`**

```python
#!/usr/bin/env python3
"""honcho_query.py — Query lessons: fast path Honcho, fallback to disk."""

import os, json, glob, re
from pathlib import Path
from typing import Optional

HONCHO_ENDPOINT = os.environ.get("HONCHO_ENDPOINT", "http://100.121.74.111:8000")
HONCHO_API_KEY = os.environ.get("HONCHO_API_KEY", "")
LESSONS_DIR = Path(__file__).parent.parent.parent / "memory" / "vault" / "lessons"


def honcho_health_check() -> bool:
    """Check if Honcho is reachable."""
    try:
        import httpx
        r = httpx.get(f"{HONCHO_ENDPOINT}/health", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def honcho_search(query: str, topK: int = 5) -> list[dict]:
    """Search Honcho for conclusions matching query. Returns [] on failure."""
    try:
        import httpx
        r = httpx.post(
            f"{HONCHO_ENDPOINT}/v1/search",
            headers={"Authorization": f"Bearer {HONCHO_API_KEY}"},
            json={"query": query, "topK": topK},
            timeout=10.0,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("conclusions", [])
    except Exception:
        return []


def disk_search(query: str, topK: int = 5) -> list[dict]:
    """Fallback: grep-like text search over lesson files."""
    if not LESSONS_DIR.exists():
        return []
    query_lower = query.lower()
    results = []
    for path in sorted(LESSONS_DIR.glob("*.md")):
        if path.name == "TEMPLATE.md":
            continue
        try:
            content = path.read_text()
            # Simple relevance: query words appear in content
            if query_lower in content.lower():
                # Extract subject from frontmatter or first heading
                m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                subject = m.group(1) if m else path.stem
                results.append({"text": subject, "source": str(path), "path": str(path)})
        except Exception:
            continue
        if len(results) >= topK:
            break
    return results


def honcho_query(query: str, topK: int = 5) -> list[dict]:
    """Query lessons. Fast path: Honcho. Fallback: disk grep."""
    if honcho_health_check():
        results = honcho_search(query, topK)
        if results:
            return results
    # Fallback to disk
    return disk_search(query, topK)
```

- [ ] **Step 4: Run test — verify it PASSES**

Run: `pytest tests/vault/insights/test_honcho_query.py::test_honcho_fast_path_returns_lessons -v`
Expected: `PASS`

- [ ] **Step 5: Write disk fallback test**

```python
def test_disk_fallback_when_honcho_unreachable(monkeypatch):
    """When Honcho is unreachable, falls back to disk search."""
    monkeypatch.setattr("vault.insights.honcho_query.honcho_health_check", lambda: False)
    with patch.object(Path, "exists", return_value=True):
        with patch.object(Path, "glob", return_value=[]):
            from vault.insights.honcho_query import disk_search
            results = disk_search("quality guardrail", topK=5)
            assert isinstance(results, list)
```

- [ ] **Step 6: Run fallback test**

Run: `pytest tests/vault/insights/test_honcho_query.py -v`
Expected: both PASS

- [ ] **Step 7: Commit**

```bash
git add vault/insights/honcho_query.py tests/vault/insights/test_honcho_query.py
git commit -m "QW-5: honcho_query skill — fast path Honcho, fallback disk"
```

---

#### Task QW-5.2: OpenClaw Skill Definition

**Files:**
- Create: `skills/honcho-query/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

```markdown
# honcho-query Skill

## Trigger
Use when: user asks about lessons, past decisions, what was decided about X, what happened with PR #N.

## Interface

### `honcho_query(query: str, topK: int = 5) -> list[dict]`

**Fast path:** Searches Honcho peer knowledge base (`honcho_search_conclusions` equivalent via API).

**Fallback:** If Honcho unreachable or empty, performs grep-like search over `memory/vault/lessons/*.md`.

**Returns:**
```python
[
  {"text": "PR #24 — Enriched Claims Rollout", "source": "memory/vault/lessons/2026-04-21-...md"},
  ...
]
```

### `honcho_health_check() -> bool`
Check if Honcho daemon is reachable at `http://100.121.74.111:8000`.

## Usage

```python
from vault.insights.honcho_query import honcho_query, honcho_health_check

# Check health
if honcho_health_check():
    print("Honcho is up")

# Query lessons
results = honcho_query("enriched claims quality guardrail", topK=5)
for r in results:
    print(r["text"], "|", r["source"])
```

## Environment Variables
- `HONCHO_ENDPOINT` — Honcho API URL (default: `http://100.121.74.111:8000`)
- `HONCHO_API_KEY` — API key for Honcho

## Notes
- Lessons are primary storage in `memory/vault/lessons/` (versioned, portable)
- Honcho is a fast semantic cache — not authoritative
- If Honcho returns empty, disk fallback always works
```

- [ ] **Step 2: Commit**

```bash
git add skills/honcho-query/SKILL.md
git commit -m "QW-5: honcho-query skill definition"
```

---

### QW-6: Validate Honcho Retrieval

**Files:**
- Test in existing `tests/vault/insights/test_honcho_query.py`

- [ ] **Step 1: Smoke test against real Honcho**

```bash
# From workspace root
cd /home/lincoln/.openclaw/workspace-livy-memory
python3 -c "
from vault.insights.honcho_query import honcho_health_check, honcho_query
print('Honcho health:', honcho_health_check())
results = honcho_query('quality guardrail', topK=3)
print(f'Results: {len(results)}')
for r in results:
    print(' -', r.get('text', '')[:60])
"
```

Expected: `Honcho health: True/False` + results list (may be empty if no peer memory yet)

- [ ] **Step 2: If Honcho is up, verify lessons appear**

If Honcho returns empty results, this is expected (no peer memory yet). Document in HEARTBEAT.md.

- [ ] **Step 3: Commit**

```bash
git add HEARTBEAT.md  # if updated
git commit -m "QW-6: honcho retrieval validation — smoke test"
```

---

## Phase 2 — Expand to GitHub Issues + Comments (QW-3b)

### QW-3b: Add GitHub Issues to `honcho_capture.py`

**Files:**
- Modify: `vault/insights/honcho_capture.py` — add `--source github-issues` flag

- [ ] **Step 1: Write failing test for issue path building**

```python
# tests/vault/insights/test_honcho_capture.py (add to class)
def test_issue_source_ref_path_hash(self):
    """Issues use 'github/{org}/{repo}/issues/{number}' as source_ref."""
    path = build_lesson_path(
        "2026-05-20T14:00:00Z",
        "living",
        "delphos-svd",
        42,
        "Bug: crypto.randomUUID fails in HTTP"
    )
    # sha256("living/delphos-svd/issues/42")[:6]
    assert path.name.endswith("-eb4f21.md")
```

Run test to verify it FAILS (function signature needs updating to support issues)

- [ ] **Step 2: Add issue fetching to honcho_capture.py**

Add new function:

```python
def get_closed_issues(org: str, repo: str, since_days: int) -> list[dict]:
    """Return closed issues from last N days via gh issue list."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
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
                if closed >= cutoff:
                    issues.append(issue)
            except (KeyError, ValueError):
                continue
        issues.sort(key=lambda i: i.get("closedAt", ""), reverse=True)
        return issues
    except Exception:
        return []
```

- [ ] **Step 3: Add `--source` argument and branch in `run()`**

```python
# In run() function, after processing PRs:
if args.source in ("github-all", "github-issues"):
    issues = get_closed_issues(org, repo, since_days)
    # For each issue: build_lesson_path with source_ref = "github/{org}/{repo}/issues/{n}"
    # Extract via LLM: issue title + body + closedAt + labels
```

- [ ] **Step 4: Run dry-run to verify**

```bash
python3 vault/insights/honcho_capture.py --org living --repos delphos-svd --days 30 --source github-issues --dry-run
```

Expected: Lists closed issues in last 30 days

- [ ] **Step 5: Commit**

```bash
git add vault/insights/honcho_capture.py tests/vault/insights/test_honcho_capture.py
git commit -m "QW-3b: honcho_capture — add GitHub Issues support"
```

---

## Phase 3 — Trello Cards (QW-3d)

### QW-3d: Add Trello to `honcho_capture.py`

**Files:**
- Modify: `vault/insights/honcho_capture.py` — add `--source trello` flag
- Modify: `vault/research/trello_client.py` — already has `get_card_comments()` and `get_card_checklists()`
- Add: Trello lesson extraction logic

- [ ] **Step 1: Verify existing trello_client API**

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from vault.research.trello_client import TrelloClient
# Check available methods
print([m for m in dir(TrelloClient) if not m.startswith('_')])
"
```

Expected output: methods including `get_board_cards`, `get_card_comments`, `get_card_checklists`

- [ ] **Step 2: Write failing test for Trello path building**

```python
def test_trello_card_source_ref_path(self):
    """Trello cards use 'trello/{board_id}/{card_id}' as source_ref."""
    path = build_lesson_path(
        "2026-05-20T14:00:00Z",
        "trello",
        "Living Boards",
        42,
        "Decision: move BAT to Hydra Flow"
    )
    # source_ref = "trello/{board_id}/{card_id}" → sha256 hash
    assert "trello" in path.name or path.name.startswith("2026-")
```

- [ ] **Step 3: Add Trello fetch to honcho_capture.py**

```python
def get_updated_trello_cards(org: str, since_days: int) -> list[dict]:
    """Return Trello cards updated in last N days via existing trello_client."""
    from vault.research.trello_client import TrelloClient
    client = TrelloClient()
    boards = client.list_boards()
    cards = []
    for board in boards:
        board_cards = client.get_board_cards(board["id"])
        for card in board_cards:
            try:
                updated = datetime.fromisoformat(card["dateLastUpdate"].replace("Z", "+00:00"))
                if updated >= (datetime.now(timezone.utc) - timedelta(days=since_days)):
                    cards.append(card)
            except Exception:
                continue
    return cards
```

- [ ] **Step 4: Add `--source trello` to CLI and `run()`**

- [ ] **Step 5: Dry-run**

```bash
python3 vault/insights/honcho_capture.py --source trello --days 30 --dry-run
```

- [ ] **Step 6: Commit**

```bash
git add vault/insights/honcho_capture.py
git commit -m "QW-3d: honcho_capture — add Trello cards support"
```

---

## Phase 4 — TLDV Synthesis (QW-3e)

### QW-3e: Add TLDV Meeting Synthesis to `honcho_capture.py`

**Note:** TLDV meetings are NOT individually converted to lessons (too granular). Instead, synthesize lessons from multiple meetings about the same topic. Use **Azure Blob** for transcript content — not Supabase.

**Files:**
- Modify: `vault/insights/honcho_capture.py` — add `--source tldv-synthesis` flag
- Use: `vault/research/azure_blob_client.py` — `AzureBlobClient.fetch_transcript()` for raw transcript
- Use: `vault/research/tldv_client.py` — meeting metadata (name, date, tags)

**Transcript source priority (per spec):** Azure Blob → Supabase (fallback)

- [ ] **Step 1: Verify tldv_client provides decisions**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from vault.research.tldv_client import TLDVClient
c = TLDVClient()
# Check method signatures
import inspect
for name, method in inspect.getmembers(c, predicate=inspect.ismethod):
    if not name.startswith('_'):
        sig = inspect.signature(method)
        print(f'{name}{sig}')
" 2>&1 | head -20
```

- [ ] **Step 2: Add synthesis function using Azure Blob**

```python
def synthesize_tldv_lessons(since_days: int, model: str) -> list[str]:
    """
    For TLDV: fetch meetings from last N days (via tldv_client),
    load raw transcript from Azure Blob for each meeting,
    group by project/topic, extract decisions, synthesize into lessons.
    NOT one lesson per meeting — synthesize across meetings about same topic.

    Transcript source: Azure Blob primary, Supabase fallback.
    """
    from vault.research.tldv_client import TLDVClient
    from vault.research.azure_blob_client import AzureBlobClient

    client = TLDVClient()
    azure = AzureBlobClient()
    meetings = client.fetch_recent_meetings(days=since_days)

    # Group by project from meeting name/tags
    by_project = {}
    for meeting in meetings:
        name = meeting.get("name", "")
        meeting_id = meeting.get("id", "")
        project = extract_project_tag(name)
        if project:
            by_project.setdefault(project, []).append((meeting, meeting_id))

    lessons = []
    for project, meeting_list in by_project.items():
        if len(meeting_list) < 2:
            continue  # need 2+ meetings to synthesize

        # Load transcripts from Azure Blob for each meeting
        transcript_texts = []
        for meeting, meeting_id in meeting_list:
            transcript = azure.fetch_transcript(meeting_id)
            if transcript:
                transcript_texts.append({
                    "meeting_id": meeting_id,
                    "name": meeting.get("name", ""),
                    "transcript": transcript[:2000],  # truncate for LLM
                })

        if not transcript_texts:
            continue

        # Synthesize via LLM
        lesson = synthesize_tldv_via_llm(project, transcript_texts, model)
        if lesson:
            lessons.append(lesson)

    return lessons


def synthesize_tldv_via_llm(project: str, transcripts: list[dict], model: str) -> str | None:
    """Synthesize multiple meeting transcripts into one lesson via LLM."""
    transcript_summary = "

".join(
        f"=== {t['name']} ===
{t['transcript'][:1500]}"
        for t in transcripts
    )
    prompt = f"""You are a senior engineer synthesizing multiple meeting transcripts into one concise lesson.
Project: {project}

TRANSCRIPTS:
{transcript_summary}

Task: Identify recurring decisions, agreements, and action items across these meetings.
Output ONLY valid YAML frontmatter + lesson body in Portuguese (BR). No code fences.

Rules:
- type: lesson
- source: tldv
- source_ref: "tldv/{project}/synthesis"
- date: YYYY-MM-DD (today)
- subject: "[Síntese] {project} — N reuniões"
- tags: [{project}, synthesis, meetings]

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
    return extract_via_llm(prompt, model)
```

- [ ] **Step 3: Add `--source tldv-synthesis` to CLI**

- [ ] **Step 4: Write test for project tag extraction**

```python
def test_extract_project_tag():
    from vault.insights.honcho_capture import extract_project_tag
    assert extract_project_tag("DELPHOS Sprint Review 2026-05-20") == "DELPHOS"
    assert extract_project_tag("BAT Weekly 2026-05-19") == "BAT"
    assert extract_project_tag("Daily Standup") is None  # no clear project
```

- [ ] **Step 5: Dry-run**

```bash
python3 vault/insights/honcho_capture.py --source tldv-synthesis --days 7 --dry-run
```

- [ ] **Step 6: Commit**

```bash
git add vault/insights/honcho_capture.py tests/vault/insights/test_honcho_capture.py
git commit -m "QW-3e: honcho_capture — add TLDV synthesis (multi-meeting lessons)"
```

---

## Phase 5 — Cron Update

### Task: Update `honcho-lessons-capture` Cron with New Sources

**Files:**
- Modify: cron `honcho-lessons-capture` (via `openclaw cron update`)

- [ ] **Step 1: Update cron message to include all sources**

Current message:
```
python3 vault/insights/honcho_capture.py --days 1 --repos ... --model gpt-4o-mini
```

New message:
```
python3 vault/insights/honcho_capture.py --days 1 \
  --repos livy-memory-bot livy-tldv-jobs hydra-flow delphos-svd \
  --source github-all \
  --source trello \
  --source tldv-synthesis \
  --model gpt-4o-mini
```

Run:
```bash
openclaw cron update honcho-lessons-capture \
  --payload.message "Execute honcho_capture ETL com todas as fontes. Run: cd /home/lincoln/.openclaw/workspace-livy-memory && python3 vault/insights/honcho_capture.py --days 1 --repos livy-memory-bot livy-tldv-jobs hydra-flow delphos-svd --source github-all --source trello --source tldv-synthesis --model gpt-4o-mini. Print JSON summary at end."
```

- [ ] **Step 2: Commit workspace change**

```bash
git add docs/superpowers/plans/2026-05-23-honcho-memory-consolidation-implplan.md
git commit -m "docs: add honcho memory consolidation implementation plan"
```

---

## Test Summary

After all phases:

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python3 -m pytest tests/vault/insights/test_honcho_capture.py tests/vault/insights/test_honcho_query.py -v
```

Expected: all tests PASS

## Notes

- **Idempotência** por path: `source_ref` muda conforme fonte (PR vs issue vs card vs meeting) — garante que a mesma decisão de PR e Issue gera paths diferentes (sem colisão)
- **Honcho TTL**: "tipicamente < 5 min" é estimado — fallback disk sempre funciona
- **YAGNI**: se Trello client não tem auth, adiciona depois — não bloqua o resto
- **Cron frequency**: manter `--days 1` para não duplicar work; se uma fonte falha, próxima run descobre novos items
