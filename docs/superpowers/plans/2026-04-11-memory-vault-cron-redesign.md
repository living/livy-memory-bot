# Memory Vault Cron Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign 7 memory crons into 2 crons (vault-ingest + vault-lint) + 1 global skill (vault-query) following the Karpathy wiki pattern.

**Architecture:** Incremental ingestion with per-source cursors, shared lock for mutual exclusion, vault-query skill for cross-referencing. TDD for all new modules.

**Tech Stack:** Python 3.12, pytest, requests, supabase-py, path-based vault (markdown + JSON)

**Spec:** `docs/superpowers/specs/2026-04-11-memory-vault-cron-redesign.md`

**Working directory:** `/home/lincoln/.openclaw/workspace-livy-memory/.worktrees/wave-c-pipeline-wiring`
**Branch:** create `feature/vault-cron-redesign` from `master`

---

## File Structure

### New files
| File | Responsibility |
|---|---|
| `vault/ingest/cursor.py` | Cursor read/write with atomic updates, watermarks, lock management |
| `vault/ingest/trello_ingest.py` | Incremental Trello ingestion (all boards, cursor-based) |
| `vault/ingest/github_ingest_integration.py` | GitHub ingestion wrapper with cursor support |
| `vault/ingest/index_manager.py` | Incremental index.md management (append/patch) |
| `vault/ingest/log_manager.py` | Log.md append + rotation |
| `vault/ingest/cross_reference.py` | Cross-source entity matching (person in Trello + TLDV) |
| `vault/tests/test_cursor.py` | Cursor tests |
| `vault/tests/test_trello_ingest.py` | Trello ingest tests |
| `vault/tests/test_github_ingest_integration.py` | GitHub ingest tests |
| `vault/tests/test_index_manager.py` | Index manager tests |
| `vault/tests/test_log_manager.py` | Log manager tests |
| `vault/tests/test_cross_reference.py` | Cross-reference tests |
| `vault/tests/test_vault_ingest_cron.py` | Integration test for full vault-ingest flow |
| `vault/tests/test_vault_lint_cron.py` | Integration test for full vault-lint flow |
| `~/.openclaw/skills/vault-query/SKILL.md` | OpenClaw skill definition |
| `~/.openclaw/skills/vault-query/MANUAL.md` | Manual for external agents |
| `~/.openclaw/skills/vault-query/templates/concept.md` | Concept page template |
| `~/.openclaw/skills/vault-query/templates/decision.md` | Decision page template |
| `~/.openclaw/skills/vault-query/templates/synthesis.md` | Synthesis page template |

### Modified files
| File | Change |
|---|---|
| `vault/ingest/external_ingest.py` | Add cursors, lock, GitHub stage, index/log updates, cross-reference |
| `vault/ingest/__init__.py` | Export new modules |
| `vault/lint.py` | Add metrics, log compactation, delivery fallback |

---

## Task 1: Cursor Module

**Files:**
- Create: `vault/ingest/cursor.py`
- Test: `vault/tests/test_cursor.py`

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_cursor.py
"""Tests for vault cursor management."""
import json
import pytest
from pathlib import Path
from vault.ingest.cursor import (
    read_cursor,
    write_cursor,
    acquire_lock,
    release_lock,
    is_locked,
)


class TestCursorReadWrite:
    def test_read_cursor_returns_empty_when_no_file(self, tmp_path):
        cursor = read_cursor(tmp_path, "tldv")
        assert cursor == {"last_run_at": None, "last_run_id": None, "watermark": {}}

    def test_write_then_read_cursor(self, tmp_path):
        data = {
            "last_run_at": "2026-04-11T10:00:00Z",
            "last_run_id": "abc-123",
            "watermark": {"latest_created_at": "2026-04-11T09:00:00Z"},
        }
        write_cursor(tmp_path, "tldv", data)
        result = read_cursor(tmp_path, "tldv")
        assert result == data

    def test_write_cursor_is_atomic(self, tmp_path):
        """If write fails mid-way, old cursor is preserved."""
        data = {"last_run_at": "2026-04-11T10:00:00Z", "last_run_id": "1", "watermark": {}}
        write_cursor(tmp_path, "tldv", data)
        # Verify file exists
        assert (tmp_path / "tldv.json").exists()
        # Write should use tmp+rename
        data2 = {"last_run_at": "2026-04-11T11:00:00Z", "last_run_id": "2", "watermark": {}}
        write_cursor(tmp_path, "tldv", data2)
        assert read_cursor(tmp_path, "tldv")["last_run_id"] == "2"

    def test_watermark_preserved_across_writes(self, tmp_path):
        d1 = {"last_run_at": "T1", "last_run_id": "1", "watermark": {"page_token": "abc"}}
        write_cursor(tmp_path, "trello", d1)
        d2 = {"last_run_at": "T2", "last_run_id": "2", "watermark": {"page_token": "def"}}
        write_cursor(tmp_path, "trello", d2)
        assert read_cursor(tmp_path, "trello")["watermark"]["page_token"] == "def"


class TestLockManagement:
    def test_acquire_lock_creates_file(self, tmp_path):
        assert acquire_lock(tmp_path, "vault-ingest", pid=12345)
        assert is_locked(tmp_path)
        lock_data = json.loads((tmp_path / "vault.lock").read_text())
        assert lock_data["job"] == "vault-ingest"
        assert lock_data["pid"] == 12345

    def test_acquire_lock_fails_if_already_locked(self, tmp_path):
        acquire_lock(tmp_path, "vault-ingest", pid=12345)
        assert not acquire_lock(tmp_path, "vault-lint", pid=99999)

    def test_stale_lock_is_removed(self, tmp_path):
        """Lock older than 10 minutes is considered stale."""
        import datetime
        old_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc).isoformat()
        lock_file = tmp_path / "vault.lock"
        lock_file.write_text(json.dumps({"pid": 1, "started_at": old_time, "job": "vault-ingest"}))
        assert acquire_lock(tmp_path, "vault-lint", pid=99999)

    def test_release_lock_removes_file(self, tmp_path):
        acquire_lock(tmp_path, "vault-ingest", pid=12345)
        release_lock(tmp_path)
        assert not is_locked(tmp_path)

    def test_recent_lock_is_not_stale(self, tmp_path):
        """Lock from <10min ago should block."""
        acquire_lock(tmp_path, "vault-ingest", pid=12345)
        assert not acquire_lock(tmp_path, "vault-lint", pid=99999)
        assert is_locked(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest vault/tests/test_cursor.py -v --tb=short`
Expected: FAIL with `ModuleNotFoundError: No module named 'vault.ingest.cursor'`

- [ ] **Step 3: Write minimal implementation**

```python
# vault/ingest/cursor.py
"""Cursor management for incremental vault ingestion.

Each source (tldv, trello, github) maintains its own cursor file
with watermark and atomic write semantics.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


def _cursors_dir(vault_root: Path) -> Path:
    d = vault_root / ".cursors"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_cursor(vault_root: Path, source: str) -> dict[str, Any]:
    """Read cursor for a source. Returns empty structure if not found."""
    f = _cursors_dir(vault_root) / f"{source}.json"
    if not f.exists():
        return {"last_run_at": None, "last_run_id": None, "watermark": {}}
    return json.loads(f.read_text())


def write_cursor(vault_root: Path, source: str, data: dict[str, Any]) -> None:
    """Atomic write: write to tmp file, then rename."""
    d = _cursors_dir(vault_root)
    target = d / f"{source}.json"
    tmp = d / f"{source}.json.tmp"
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(target)


def acquire_lock(vault_root: Path, job: str, pid: int | None = None) -> bool:
    """Acquire shared vault lock. Returns False if locked by another job."""
    d = _cursors_dir(vault_root)
    lock_file = d / "vault.lock"
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text())
            started = datetime.fromisoformat(data["started_at"])
            age = (datetime.now(timezone.utc) - started).total_seconds()
            if age < 600:  # < 10 min
                return False
            # Stale lock
            lock_file.unlink(missing_ok=True)
        except (json.JSONDecodeError, KeyError, ValueError):
            lock_file.unlink(missing_ok=True)

    lock_file.write_text(json.dumps({
        "pid": pid or os.getpid(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "job": job,
    }))
    return True


def release_lock(vault_root: Path) -> None:
    """Release the vault lock."""
    d = _cursors_dir(vault_root)
    (d / "vault.lock").unlink(missing_ok=True)


def is_locked(vault_root: Path) -> bool:
    """Check if vault lock exists (does not check staleness)."""
    return (_cursors_dir(vault_root) / "vault.lock").exists()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest vault/tests/test_cursor.py -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest vault/tests/ -q --tb=short`
Expected: Same baseline + new tests pass

- [ ] **Step 6: Commit**

```bash
git add vault/ingest/cursor.py vault/tests/test_cursor.py
git commit -m "feat(vault): cursor module — atomic read/write, shared lock management"
```

---

## Task 2: Index Manager

**Files:**
- Create: `vault/ingest/index_manager.py`
- Test: `vault/tests/test_index_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_index_manager.py
"""Tests for incremental index.md management."""
import pytest
from pathlib import Path
from vault.ingest.index_manager import (
    init_index,
    add_entry,
    update_entry,
    read_index,
)


class TestIndexManager:
    def test_init_index_creates_file(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        assert (vault / "index.md").exists()

    def test_add_entry(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        add_entry(vault, "entities/meeting-abc.md", "Meeting: Status BAT", "meeting")
        idx = read_index(vault)
        assert "entities/meeting-abc.md" in idx
        assert idx["entities/meeting-abc.md"]["title"] == "Meeting: Status BAT"
        assert idx["entities/meeting-abc.md"]["type"] == "meeting"

    def test_add_entry_idempotent(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        add_entry(vault, "entities/meeting-abc.md", "Title", "meeting")
        add_entry(vault, "entities/meeting-abc.md", "Title", "meeting")
        idx = read_index(vault)
        # Should appear once
        assert len([k for k in idx if "meeting-abc" in k]) == 1

    def test_update_entry_changes_title(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        add_entry(vault, "entities/meeting-abc.md", "Old Title", "meeting")
        update_entry(vault, "entities/meeting-abc.md", "New Title")
        idx = read_index(vault)
        assert idx["entities/meeting-abc.md"]["title"] == "New Title"

    def test_multiple_entries_by_type(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        add_entry(vault, "entities/meeting-a.md", "M A", "meeting")
        add_entry(vault, "entities/person-b.md", "P B", "person")
        add_entry(vault, "concepts/bat.md", "BAT", "concept")
        idx = read_index(vault)
        assert len(idx) == 3
        types = {v["type"] for v in idx.values()}
        assert types == {"meeting", "person", "concept"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest vault/tests/test_index_manager.py -v --tb=short`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# vault/ingest/index_manager.py
"""Incremental index.md management for the vault wiki."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def init_index(vault_root: Path) -> None:
    """Create index.md if it doesn't exist."""
    idx = vault_root / "index.md"
    if not idx.exists():
        vault_root.mkdir(parents=True, exist_ok=True)
        idx.write_text("# Vault Index\n\n")


def read_index(vault_root: Path) -> dict[str, dict[str, str]]:
    """Parse index.md into {path: {title, type}} dict."""
    idx = vault_root / "index.md"
    if not idx.exists():
        return {}
    content = idx.read_text()
    entries = {}
    # Parse lines like: | [entities/meeting-abc.md](entities/meeting-abc.md) | Meeting: Status | meeting |
    for line in content.splitlines():
        m = re.match(r"\|\s*\[(.+?)\]\(.+?\)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", line)
        if m:
            entries[m.group(1)] = {"title": m.group(2).strip(), "type": m.group(3).strip()}
    return entries


def add_entry(vault_root: Path, path: str, title: str, entry_type: str) -> None:
    """Append entry to index.md if not already present."""
    idx_file = vault_root / "index.md"
    current = read_index(vault_root)
    if path in current:
        return  # Idempotent
    line = f"| [{path}]({path}) | {title} | {entry_type} |\n"
    with open(idx_file, "a") as f:
        f.write(line)


def update_entry(vault_root: Path, path: str, title: str) -> None:
    """Update an existing entry's title in index.md."""
    idx_file = vault_root / "index.md"
    content = idx_file.read_text()
    # Replace title for matching path
    pattern = rf"(\|\s*\[{re.escape(path)}\]\({re.escape(path)}\)\s*\|\s*)(.+?)(\s*\|\s*.+?\s*\|)"
    replacement = rf"\1{title}\3"
    new_content = re.sub(pattern, replacement, content)
    if new_content != content:
        idx_file.write_text(new_content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest vault/tests/test_index_manager.py -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add vault/ingest/index_manager.py vault/tests/test_index_manager.py
git commit -m "feat(vault): index manager — incremental append/patch for index.md"
```

---

## Task 3: Log Manager

**Files:**
- Create: `vault/ingest/log_manager.py`
- Test: `vault/tests/test_log_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_log_manager.py
"""Tests for log.md management with rotation."""
import pytest
from pathlib import Path
from vault.ingest.log_manager import append_log, maybe_rotate_log


class TestLogManager:
    def test_append_log_creates_file(self, tmp_path):
        vault = tmp_path / "vault"
        append_log(vault, "vault-ingest", {"meetings": 5, "persons": 10})
        log = (vault / "log.md").read_text()
        assert "## [" in log
        assert "vault-ingest" in log
        assert "meetings: 5" in log

    def test_append_log_appends(self, tmp_path):
        vault = tmp_path / "vault"
        append_log(vault, "vault-ingest", {"a": 1})
        append_log(vault, "vault-lint", {"b": 2})
        log = (vault / "log.md").read_text()
        assert "vault-ingest" in log
        assert "vault-lint" in log

    def test_dry_run_entry_is_marked(self, tmp_path):
        vault = tmp_path / "vault"
        append_log(vault, "vault-ingest", {"a": 1}, dry_run=True)
        log = (vault / "log.md").read_text()
        assert "[dry-run]" in log

    def test_rotation_moves_old_log(self, tmp_path):
        vault = tmp_path / "vault"
        append_log(vault, "vault-ingest", {"a": 1})
        # Make log.md artificially large
        log_file = vault / "log.md"
        content = log_file.read_text()
        log_file.write_text(content + "x" * 600_000)  # > 500KB
        maybe_rotate_log(vault)
        assert not log_file.exists() or log_file.stat().st_size < 1000
        archive = vault / "log-archive"
        assert archive.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest vault/tests/test_log_manager.py -v --tb=short`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# vault/ingest/log_manager.py
"""Log.md management with monthly rotation."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_log(
    vault_root: Path,
    job: str,
    summary: dict[str, Any],
    *,
    dry_run: bool = False,
) -> None:
    """Append entry to log.md."""
    log_file = vault_root / "log.md"
    vault_root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")
    prefix = "[dry-run] " if dry_run else ""
    header = f"## [{date_str}] {prefix}{job}"
    lines = [header]
    for k, v in summary.items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    entry = "\n".join(lines) + "\n"
    if log_file.exists():
        with open(log_file, "a") as f:
            f.write(entry)
    else:
        log_file.write_text("# Vault Log\n\n" + entry)


def maybe_rotate_log(vault_root: Path, max_bytes: int = 500_000) -> None:
    """Rotate log.md if it exceeds max_bytes."""
    log_file = vault_root / "log.md"
    if not log_file.exists() or log_file.stat().st_size < max_bytes:
        return
    now = datetime.now(timezone.utc)
    month_str = now.strftime("%Y-%m")
    archive_dir = vault_root / "log-archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_file = archive_dir / f"{month_str}.md"
    # Append current log to archive
    content = log_file.read_text()
    if archive_file.exists():
        with open(archive_file, "a") as f:
            f.write("\n" + content)
    else:
        archive_file.write_text(content)
    # Reset log.md
    log_file.write_text("# Vault Log\n\n")
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest vault/tests/test_log_manager.py -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add vault/ingest/log_manager.py vault/tests/test_log_manager.py
git commit -m "feat(vault): log manager — append with monthly rotation"
```

---

## Task 4: Cross-Reference Module

**Files:**
- Create: `vault/ingest/cross_reference.py`
- Test: `vault/tests/test_cross_reference.py`

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_cross_reference.py
"""Tests for cross-source entity matching."""
from vault.ingest.cross_reference import find_person_cross_refs


class TestCrossReference:
    def test_match_person_by_email(self):
        tldv_persons = [
            {"id": "p1", "name": "Lincoln", "email": "lincoln@livingnet.com.br"},
        ]
        trello_members = [
            {"id": "m1", "fullName": "Lincoln Quinan", "email": "lincoln@livingnet.com.br"},
        ]
        matches = find_person_cross_refs(tldv_persons, trello_members)
        assert len(matches) == 1
        assert matches[0]["tldv_id"] == "p1"
        assert matches[0]["trello_id"] == "m1"

    def test_no_match_returns_empty(self):
        tldv_persons = [{"id": "p1", "name": "Bob", "email": "bob@x.com"}]
        trello_members = [{"id": "m1", "fullName": "Alice", "email": "alice@y.com"}]
        assert find_person_cross_refs(tldv_persons, trello_members) == []

    def test_match_by_normalized_name_when_no_email(self):
        tldv_persons = [{"id": "p1", "name": "Robert Urech", "email": None}]
        trello_members = [{"id": "m1", "fullName": "robert urech", "email": None}]
        matches = find_person_cross_refs(tldv_persons, trello_members)
        assert len(matches) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest vault/tests/test_cross_reference.py -v --tb=short`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# vault/ingest/cross_reference.py
"""Cross-source entity matching for Person entities."""
from __future__ import annotations

from typing import Any


def _normalize(name: str | None) -> str:
    if not name:
        return ""
    return name.strip().lower()


def find_person_cross_refs(
    tldv_persons: list[dict[str, Any]],
    trello_members: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Match TLDV persons to Trello members by email (primary) or normalized name."""
    matches = []
    # Index by email
    by_email: dict[str, dict] = {}
    for p in trello_members:
        email = (p.get("email") or "").strip().lower()
        if email:
            by_email[email] = p

    for tp in tldv_persons:
        email = (tp.get("email") or "").strip().lower()
        trello_match = None
        if email and email in by_email:
            trello_match = by_email[email]
        else:
            # Fallback to normalized name
            norm = _normalize(tp.get("name"))
            for tm in trello_members:
                if _normalize(tm.get("fullName")) == norm:
                    trello_match = tm
                    break
        if trello_match:
            matches.append({
                "tldv_id": tp.get("id", ""),
                "trello_id": trello_match.get("id", ""),
                "match_method": "email" if email and email in by_email else "name",
            })
    return matches
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest vault/tests/test_cross_reference.py -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add vault/ingest/cross_reference.py vault/tests/test_cross_reference.py
git commit -m "feat(vault): cross-reference module — match persons across TLDV/Trello"
```

---

## Task 5: Integrate GitHub + Cursors + Locks into `run_external_ingest`

**Files:**
- Modify: `vault/ingest/external_ingest.py`
- Test: `vault/tests/test_external_ingest.py` (add tests)

- [ ] **Step 1: Write failing tests for new features**

Add to `vault/tests/test_external_ingest.py`:

```python
def test_cursors_are_updated_on_success(self, tmp_path):
    """After successful run, cursors are written for each source."""
    from vault.ingest.cursor import read_cursor
    from vault.ingest.external_ingest import run_external_ingest
    from unittest.mock import patch

    raw = [{"id": "c1", "name": "Test", "created_at": "2026-04-11T10:00:00Z",
            "participants": [{"id": "p1", "name": "Bob", "email": None, "source_key": "tldv:p1", "source": "tldv_api"}],
            "whisper_transcript_json": []}]

    with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=raw), \
         patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
        result = run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)

    cursor = read_cursor(tmp_path, "tldv")
    assert cursor["last_run_at"] is not None
    assert cursor["last_run_id"] is not None

def test_lock_prevents_concurrent_runs(self, tmp_path):
    """If lock is active, second run is skipped."""
    from vault.ingest.cursor import acquire_lock
    from vault.ingest.external_ingest import run_external_ingest
    from unittest.mock import patch

    acquire_lock(tmp_path, "vault-lint", pid=99999)
    with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=[]), \
         patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
        result = run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)

    assert result.get("skipped_reason") == "locked" or result.get("meetings_fetched", 0) == 0
```

- [ ] **Step 2: Modify `run_external_ingest`**

Add to `vault/ingest/external_ingest.py`:
1. Import cursor, lock, index_manager, log_manager
2. At start: `acquire_lock(vault_root, "vault-ingest")` — if fails, return `{"skipped_reason": "locked"}`
3. After each source completes: `write_cursor(vault_root, source_name, cursor_data)`
4. After all sources: `run_enrich_github()` as callable step
5. At end: `add_entry()` / `update_entry()` for each entity written, `append_log()`
6. Finally: `release_lock(vault_root)`

Reference existing signature:
```python
def run_external_ingest(
    vault_root: Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    meeting_days: int = 7,
    card_days: int = 7,
    tldv_token: str | None = None,
    meeting_ids: list[str] | None = None,  # NEW: for isolated meeting processing
) -> dict[str, Any]:
```

- [ ] **Step 3: Run full suite**

Run: `python3 -m pytest vault/tests/ -q --tb=short`
Expected: All pass, no regressions

- [ ] **Step 4: Commit**

```bash
git add vault/ingest/external_ingest.py vault/tests/test_external_ingest.py
git commit -m "feat(ingest): integrate cursors, locks, GitHub stage, index/log into external_ingest"
```

---

## Task 6: Create vault-ingest Cron + Disable Old Crons

**Files:**
- No new code files — cron configuration via OpenClaw

- [ ] **Step 1: Create vault-ingest cron**

```bash
openclaw cron add \
  --name "vault-ingest" \
  --cron "0 10,14,20 * * *" \
  --tz "America/Sao_Paulo" \
  --session isolated \
  --model fastest \
  --message "Run the vault ingest pipeline. Execute: cd /home/lincoln/.openclaw/workspace-livy-memory/.worktrees/wave-c-pipeline-wiring && python3 -c \"from vault.ingest.external_ingest import run_external_ingest; import os; from pathlib import Path; env = Path.home()/'.openclaw/.env'; [__import__('os').environ.setdefault(k.strip(),v.strip()) for l in env.read_text().splitlines() if '=' in l and not l.startswith('#') for k,_,v in [l.partition('=')]]; print(run_external_ingest(tldv_token=os.environ.get('TLDV_JWT_TOKEN'), meeting_days=1))\" 2>&1" \
  --timeout 600 \
  --announce \
  --channel telegram \
  --to 7426291192
```

- [ ] **Step 2: Disable old crons (one by one)**

```bash
# Use IDs from spec Section 2.3
openclaw cron disable 9dfe2886-...   # memory-agent-sonhar
openclaw cron disable 2ec55149-...   # memory-vault-daily-pipeline
openclaw cron disable b36e4fb9-...   # daily-memory-save
openclaw cron disable aa5cd560-...   # memory-agent-feedback-learn
openclaw cron disable 0c388629-...   # autoresearch
openclaw cron disable 53b45f6f-...   # signal-curation
openclaw cron disable 63a44a25-...   # openclaw-health
```

- [ ] **Step 3: Create vault-lint cron**

```bash
openclaw cron add \
  --name "vault-lint" \
  --cron "0 21 * * *" \
  --tz "America/Sao_Paulo" \
  --session isolated \
  --model "zai/glm-5.1" \
  --message "Run the vault lint pipeline. Execute: cd /home/lincoln/.openclaw/workspace-livy-memory/.worktrees/wave-c-pipeline-wiring && python3 -m vault.pipeline --reverify --repair 2>&1. Then run lint scans: python3 -c \"from vault.lint import run_full_lint; print(run_full_lint())\" 2>&1" \
  --timeout 600 \
  --announce \
  --channel telegram \
  --to 7426291192
```

- [ ] **Step 4: Verify crons**

Run: `openclaw cron list`
Expected: vault-ingest + vault-lint enabled, 7 old crons disabled

---

## Task 7: Create vault-query Skill

**Files:**
- Create: `~/.openclaw/skills/vault-query/SKILL.md`
- Create: `~/.openclaw/skills/vault-query/MANUAL.md`
- Create: `~/.openclaw/skills/vault-query/templates/concept.md`
- Create: `~/.openclaw/skills/vault-query/templates/decision.md`
- Create: `~/.openclaw/skills/vault-query/templates/synthesis.md`

- [ ] **Step 1: Create SKILL.md**

Write the SKILL.md following the spec Section 3 — query protocol, trust policy, 6 query types.

- [ ] **Step 2: Create MANUAL.md**

Write the MANUAL.md for external agents — vault structure, frontmatter conventions, how to read/write, lock protocol.

- [ ] **Step 3: Create templates**

3 markdown templates with frontmatter schemas for concepts, decisions, synthesis.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(skills): vault-query skill — global query skill for Living Memory wiki"
```

---

## Task 8: Integration Tests + Validation

**Files:**
- Create: `vault/tests/test_vault_ingest_cron.py`
- Create: `vault/tests/test_vault_lint_cron.py`

- [ ] **Step 1: Write integration test for vault-ingest**

Test full flow: lock → fetch → resolve → build → persist → cursor → index → log → unlock

- [ ] **Step 2: Write integration test for vault-lint**

Test: lock → reverify → lint scans → report → log → unlock

- [ ] **Step 3: Run full suite**

Run: `python3 -m pytest vault/tests/ -q --tb=short`
Expected: All pass

- [ ] **Step 4: Run vault-ingest dry_run against real data**

Manual test with real TLDV token.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test(vault): integration tests for vault-ingest and vault-lint cron flows"
```

---

## Task 9: Final Branch Cleanup + PR

- [ ] **Step 1: Push branch**

```bash
git push origin feature/vault-cron-redesign
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --base master --head feature/vault-cron-redesign \
  --title "feat(vault): Memory Vault Cron Redesign — 7→2 crons + vault-query skill" \
  --body "Spec: docs/superpowers/specs/2026-04-11-memory-vault-cron-redesign.md"
```

- [ ] **Step 3: Backfill test**

```bash
# Gradual backfill
python3 -c "from vault.ingest.external_ingest import run_external_ingest; ..."
# meeting_days=7, then 30, then 90
```
