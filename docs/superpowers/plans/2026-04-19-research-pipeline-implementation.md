# Research Pipeline — Batch-First Self-Evolving: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Spec:** `docs/superpowers/specs/2026-04-19-research-pipeline-design.md`

**Goal:** Implement real GitHub and TLDV clients for ResearchPipeline, migrate crons to 4x/day batch cadence, add cadence state persistence, and add cost metrics schema.

**Architecture:** One `ResearchPipeline` engine (already exists) with two new source clients (GitHub, TLDV) wired in. Cron jobs call the engine with different source/client. Cadence state persisted in `state/identity-graph/cadence.json`.

**Tech Stack:** Python, `requests` (GitHub REST), `supabase` Py client, `gh` CLI for GitHub auth, existing `vault/research/` infrastructure.

---

## Scope

Three independent tasks — can be implemented in any order or parallel:

1. **GitHub client** — `vault/research/github_client.py` + tests
2. **TLDV client** — `vault/research/tldv_client.py` + tests
3. **Cadence + cron migration** — update `vault/research/pipeline.py`, cron schedules, add cost metrics schema

---

## Task 1: GitHub Client

**Files:**
- Create: `vault/research/github_client.py`
- Test: `tests/research/test_github_client.py`
- Ref: `vault/ingest/github_ingest.py` (existing lookback window logic)

- [ ] **Step 1: Write failing test — GitHubClient.fetch_events_since returns PR events**

```python
# tests/research/test_github_client.py
from unittest.mock import MagicMock, patch
from vault.research.github_client import GitHubClient

def test_fetch_events_since_returns_pr_events(monkeypatch):
    """Returns normalized github:pr_merged events from gh api search."""
    fake_prs = {
        "items": [
            {
                "number": 42,
                "title": "fix: pipeline",
                "state": "closed",
                "merged_at": "2026-04-14T10:00:00Z",
                "created_at": "2026-04-13T09:00:00Z",
                "repository": {"full_name": "living/livy-memory-bot"},
                "user": {"login": "lincolnqjunior", "id": 445449},
                "merged": True,
            }
        ]
    }

    class FakeResp:
        status_code = 200
        def json(self): return fake_prs

    with patch("requests.get", return_value=FakeResp()):
        client = GitHubClient()
        events = client.fetch_events_since("2026-04-13T00:00:00Z")

    assert len(events) == 1
    assert events[0]["event_type"] == "github:pr_merged"
    assert events[0]["pr_number"] == 42
    assert events[0]["author"]["login"] == "lincolnqjunior"

def test_fetch_events_since_no_last_seen_uses_default_window(monkeypatch):
    """When last_seen_at is None, uses default 7-day lookback."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"items": []})
        client = GitHubClient()
        client.fetch_events_since(None)
        # gh api search query must include date cutoff
        call_args = mock_get.call_args
        assert any("merged:>" in str(call_args) for call_args in [call_args])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/research/test_github_client.py -v --tb=short 2>&1 | tail -20`
Expected: FAIL — module `vault.research.github_client` not found

- [ ] **Step 3: Write minimal GitHubClient implementation**

Create `vault/research/github_client.py`:

```python
"""GitHub polling client for research pipeline.

Uses gh api search to fetch PRs merged within a lookback window.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Any


DEFAULT_LOOKBACK_DAYS = 7
GH_SEARCH_QUERY = "is:pr merged:{date_cutoff} org:living"
REPOS_SCOPE = ["living/livy-memory-bot", "living/livy-bat-jobs", "living/livy-delphos-jobs", "living/livy-tldv-jobs"]


class GitHubClient:
    def __init__(
        self,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        repos: list[str] | None = None,
    ) -> None:
        self.lookback_days = lookback_days
        self.repos = repos or REPOS_SCOPE

    def fetch_events_since(self, last_seen_at: str | None) -> list[dict[str, Any]]:
        cutoff = self._compute_cutoff(last_seen_at)
        events: list[dict[str, Any]] = []

        for repo in self.repos:
            prs = self._fetch_merged_prs(repo, cutoff)
            for pr in prs:
                normalized = self._normalize_pr(pr)
                events.append(normalized)

        events.sort(key=lambda e: e.get("merged_at", ""))
        return events

    def _compute_cutoff(self, last_seen_at: str | None) -> datetime:
        if last_seen_at:
            dt = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
            return dt
        return datetime.now(timezone.utc) - timedelta(days=self.lookback_days)

    def _fetch_merged_prs(self, repo: str, cutoff: datetime) -> list[dict[str, Any]]:
        date_str = cutoff.strftime("%Y-%m-%d")
        query = f"is:pr merged:>{date_str} repo:{repo}"
        try:
            result = subprocess.run(
                ["gh", "api", "search/issues",
                 "--jq", ".items[]",
                 "--template", '{"number": .number, "title": .title, "state": .state, "merged_at": .merged_at, "created_at": .created_at, "user": .user, "merged": .merged, "repository": .repository}"',
                 "-q", query],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return []
            import json
            lines = [l for l in result.stdout.strip().split("\n") if l]
            return [json.loads(line) for line in lines]
        except Exception:
            return []

    def _normalize_pr(self, pr: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": "github",
            "event_type": "github:pr_merged",
            "pr_number": pr.get("number"),
            "title": pr.get("title"),
            "merged_at": pr.get("merged_at"),
            "created_at": pr.get("created_at"),
            "author": pr.get("user", {}),
            "repo": pr.get("repository", {}).get("full_name", ""),
            "merged": pr.get("merged", False),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/research/test_github_client.py -v --tb=short 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vault/research/github_client.py tests/research/test_github_client.py
git commit -m "feat(research): add GitHubClient for PR polling via gh api"
```

---

## Task 2: TLDV Client

**Files:**
- Create: `vault/research/tldv_client.py`
- Test: `tests/research/test_tldv_client.py`
- Ref: `vault/ingest/meeting_ingest.py` (existing Supabase fetching logic)

- [ ] **Step 1: Write failing test — TLDVClient.fetch_events_since returns meeting events**

```python
# tests/research/test_tldv_client.py
from unittest.mock import MagicMock, patch
from vault.research.tldv_client import TLDVClient

def test_fetch_events_since_returns_meeting_events():
    """Returns normalized github:pr_merged events from gh api search."""
    fake_meetings = [
        {
            "id": "meet_abc123",
            "name": "Daily 2026-04-14",
            "created_at": "2026-04-14T10:00:00Z",
            "updated_at": "2026-04-14T11:00:00Z",
        }
    ]

    class FakeResp:
        status_code = 200
        def json(self): return {"data": fake_meetings}

    with patch("requests.get", return_value=FakeResp()):
        client = TLDVClient()
        events = client.fetch_events_since("2026-04-13T00:00:00Z")

    assert len(events) == 1
    assert events[0]["event_type"] == "tldv:meeting"
    assert events[0]["meeting_id"] == "meet_abc123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/research/test_tldv_client.py -v --tb=short 2>&1 | tail -20`
Expected: FAIL — module `vault.research.tldv_client` not found

- [ ] **Step 3: Write minimal TLDVClient implementation**

Create `vault/research/tldv_client.py`:

```python
"""TLDV polling client for research pipeline.

Uses Supabase REST to fetch meetings updated within lookback window.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any
import requests


DEFAULT_LOOKBACK_DAYS = 7


class TLDVClient:
    def __init__(
        self,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
    ) -> None:
        self.lookback_days = lookback_days
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    def fetch_events_since(self, last_seen_at: str | None) -> list[dict[str, Any]]:
        if not self.supabase_url or not self.supabase_key:
            return []

        cutoff = self._compute_cutoff(last_seen_at)
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
        params = {
            "select": "id,name,created_at,updated_at,meeting_id",
            "order": "updated_at.desc",
            "limit": 100,
        }
        if last_seen_at:
            params["updated_at"] = f"gte.{cutoff.isoformat()}"

        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/meetings",
                headers=headers,
                params=params,
                timeout=30,
            )
            if resp.status_code != 200:
                return []
            rows = resp.json() or []
            return [self._normalize_meeting(row) for row in rows]
        except Exception:
            return []

    def fetch_meeting(self, meeting_id: str) -> dict[str, Any]:
        if not self.supabase_url or not self.supabase_key:
            return {}
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/meetings",
                headers=headers,
                params={"id": f"eq.{meeting_id}", "limit": 1},
                timeout=15,
            )
            if resp.status_code == 200:
                rows = resp.json() or []
                if rows:
                    return self._normalize_meeting(rows[0])
        except Exception:
            pass
        return {}

    def _compute_cutoff(self, last_seen_at: str | None) -> datetime:
        if last_seen_at:
            dt = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
            return dt
        return datetime.now(timezone.utc) - timedelta(days=self.lookback_days)

    def _normalize_meeting(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": "tldv",
            "event_type": "tldv:meeting",
            "meeting_id": row.get("id") or row.get("meeting_id"),
            "name": row.get("name"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "raw": row,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/research/test_tldv_client.py -v --tb=short 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vault/research/tldv_client.py tests/research/test_tldv_client.py
git commit -m "feat(research): add TLDVClient for Supabase meetings polling"
```

---

## Task 3: Wire Clients into Pipeline + Cadence + Cron Migration

**Files:**
- Modify: `vault/research/pipeline.py:116-145` (swap stub clients for real ones)
- Modify: `vault/crons/research_trello_cron.py`, `research_github_cron.py`, `research_tldv_cron.py` (cron schedules)
- Create: `vault/research/cadence_manager.py`
- Create: `state/identity-graph/cadence.json`
- Add cost metrics schema to `vault/research/self_healing.py`
- Test: `tests/research/test_pipeline_trello.py` (existing)

- [ ] **Step 1: Write failing test — pipeline wires real GitHubClient**

```python
# tests/research/test_pipeline_wiring.py
def test_pipeline_wires_github_client():
    """ResearchPipeline(source='github') uses GitHubClient (not stub)."""
    from vault.research.pipeline import ResearchPipeline
    with patch("vault.research.pipeline.GitHubClient") as mock_cls:
        mock_cls.return_value.fetch_events_since.return_value = []
        p = ResearchPipeline(
            source="github",
            state_path=":memory:",
            research_dir="/tmp/rp_test",
        )
        p.run()
        mock_cls.return_value.fetch_events_since.assert_called_once()

def test_pipeline_wires_tldv_client():
    """ResearchPipeline(source='tldv') uses TLDVClient (not stub)."""
    from vault.research.pipeline import ResearchPipeline
    with patch("vault.research.pipeline.TLDVClient") as mock_cls:
        mock_cls.return_value.fetch_events_since.return_value = []
        p = ResearchPipeline(
            source="tldv",
            state_path=":memory:",
            research_dir="/tmp/rp_test",
        )
        p.run()
        mock_cls.return_value.fetch_events_since.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/research/test_pipeline_wiring.py -v --tb=short 2>&1 | tail -20`
Expected: FAIL — stub classes still used in pipeline

- [ ] **Step 3: Update pipeline.py to wire real clients**

In `vault/research/pipeline.py`, replace the stub class definitions (lines ~116-135) with imports:

```python
# REPLACE stub classes (~116-135) with:
from vault.research.github_client import GitHubClient
from vault.research.trello_client import TrelloClient
from vault.research.tldv_client import TLDVClient
```

And update the `run()` method to use these imports directly (remove the inline stub class definitions).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/research/test_pipeline_wiring.py -v --tb=short`
Expected: PASS

- [ ] **Step 5: Write cadence manager**

Create `vault/research/cadence_manager.py`:

```python
"""Cadence state manager for research pipeline.

Persists per-source interval preference to state/identity-graph/cadence.json.
Hard floor: 4h. Escalation: 6h when budget exceeded.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_STATE_PATH = Path("state/identity-graph/cadence.json")
DEFAULT_INTERVAL_HOURS = 4
ESCALATED_INTERVAL_HOURS = 6


def load_cadence_state(state_path: Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    if not state_path.exists():
        return _default_state()
    return json.loads(state_path.read_text())


def save_cadence_state(state: dict[str, Any], state_path: Path = DEFAULT_STATE_PATH) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))


def _default_state() -> dict[str, Any]:
    return {
        "interval_hours": DEFAULT_INTERVAL_HOURS,
        "last_escalated_at": None,
        "last_reduced_at": None,
        "consecutive_budget_warnings": 0,
    }


def get_interval_hours(state_path: Path = DEFAULT_STATE_PATH) -> int:
    state = load_cadence_state(state_path)
    return state.get("interval_hours", DEFAULT_INTERVAL_HOURS)


def record_budget_warning(state_path: Path = DEFAULT_STATE_PATH) -> None:
    state = load_cadence_state(state_path)
    state["consecutive_budget_warnings"] = state.get("consecutive_budget_warnings", 0) + 1
    if (state["consecutive_budget_warnings"] >= 3
            and state.get("interval_hours", DEFAULT_INTERVAL_HOURS) == DEFAULT_INTERVAL_HOURS):
        state["interval_hours"] = ESCALATED_INTERVAL_HOURS
        state["last_escalated_at"] = _iso_now()
    save_cadence_state(state, state_path)


def record_healthy_run(state_path: Path = DEFAULT_STATE_PATH) -> None:
    state = load_cadence_state(state_path)
    if state.get("interval_hours") == ESCALATED_INTERVAL_HOURS:
        state["interval_hours"] = DEFAULT_INTERVAL_HOURS
        state["last_reduced_at"] = _iso_now()
    state["consecutive_budget_warnings"] = 0
    save_cadence_state(state, state_path)


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 6: Update cron schedules**

Update `vault/crons/research_trello_cron.py`, `research_github_cron.py`, and `research_tldv_cron.py` schedule expressions from `*/20 * * * *`, `*/10 * * * *`, `*/15 * * * *` to `0 0,6,12,18 * * *` (4x/day at 0h, 6h, 12h, 18h BRT).

```bash
# Example for research_trello_cron.py — change schedule field only
# openclaw cron update <job-id> --schedule "0 0,6,12,18 * * *"
```

- [ ] **Step 7: Add CROSS_SOURCE_IDENTITY_ENABLED flag**

Add to `vault/research/pipeline.py`:
```python
import os
CROSS_SOURCE_IDENTITY_ENABLED = os.environ.get("CROSS_SOURCE_IDENTITY_ENABLED", "false").lower() == "true"
```

And to `vault/research/pipeline.py` `__init__`:
```python
self.cross_source_identity_enabled = CROSS_SOURCE_IDENTITY_ENABLED
```

- [ ] **Step 8: Run full test suite**

Run: `python3 -m pytest tests/research/ -q --tb=line 2>&1 | tail -15`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add vault/research/pipeline.py vault/research/cadence_manager.py
git add vault/crons/research_trello_cron.py vault/crons/research_github_cron.py vault/crons/research_tldv_cron.py
git commit -m "feat(research): wire real GitHub/TLDV clients, add cadence manager, 4x/day cron"

git add tests/research/test_pipeline_wiring.py
git commit -m "test(research): wire tests for GitHub/TLDV client integration"
```

---

## Cost Metrics Schema (add to run output)

Each pipeline `run()` already returns `events_processed`, `events_skipped`, `status`.
Extend the run result dict to include (minimum schema per spec):

```python
{
    "status": "success",
    "events_processed": N,
    "events_skipped": N,
    # new fields:
    "token_used": 0,          # placeholder — populated when LLM calls added
    "api_calls": N,           # count of external API calls made
    "cost_usd_estimate": 0.0, # API cost estimate (GitHub free; TLDV/Supabase minimal)
}
```

Add to `vault/research/pipeline.py` `run()` return dict.
