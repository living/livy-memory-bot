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
| `vault/ingest/vault_lint_scanner.py` | Vault lint scans (orphans, stale, gaps, contradictions, suggestions, metrics) |
| `vault/ingest/stages.py` | IngestStage protocol + PipelineRunner (avoids god-orchestrator in run_external_ingest) |
| `vault/ingest/run_context.py` | RunContext dataclass — run_id, started_at, vault_root, dry_run |
| `vault/ingest/resilience.py` | HTTP retry with backoff + circuit breaker + is_retryable() |
| `vault/crons/vault_ingest_cron.py` | Cron entry point for vault-ingest (env load + pipeline call + error handling) |
| `vault/crons/vault_lint_cron.py` | Cron entry point for vault-lint (env load + pipeline call + error handling) |
| `vault/commands/status.py` | vault status utility — lock state, cursor timestamps, last run, delivery failures, circuit state |
| `vault/tests/test_cursor.py` | Cursor tests |
| `vault/tests/test_trello_ingest.py` | Trello ingest tests |
| `vault/tests/test_github_ingest_integration.py` | GitHub ingest tests |
| `vault/tests/test_index_manager.py` | Index manager tests |
| `vault/tests/test_log_manager.py` | Log manager tests |
| `vault/tests/test_cross_reference.py` | Cross-reference tests |
| `vault/tests/test_vault_lint_scanner.py` | Vault lint scanner tests |
| `vault/tests/test_stages.py` | PipelineRunner tests with mock stages |
| `vault/tests/test_resilience.py` | HTTP resilience tests (retry, circuit breaker) |
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
| `vault/ingest/external_ingest.py` | Add cursors, lock, GitHub stage, index/log updates, cross-reference; refactor to use PipelineRunner from stages.py |
| `vault/ingest/__init__.py` | Export new modules (stages, run_context, resilience) |
| `vault/lint.py` | Add metrics, log compaction, delivery fallback, LintReport TypedDict |

---

## Task 1: Cursor Module

**Acceptance criteria (traceability):**
- All entities MUST include `provenance` frontmatter with `source`, `source_key`, `fetched_at`, `run_id`.

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
    check_circuit_breaker,
    record_failure,
    record_success,
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
        # Verify file exists at the correct path (.cursors/ subdirectory)
        assert (tmp_path / ".cursors" / "tldv.json").exists()
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
        lock_data = json.loads((tmp_path / ".cursors" / "vault.lock").read_text())
        assert lock_data["job"] == "vault-ingest"
        assert lock_data["pid"] == 12345

    def test_acquire_lock_fails_if_already_locked(self, tmp_path):
        acquire_lock(tmp_path, "vault-ingest", pid=12345)
        assert not acquire_lock(tmp_path, "vault-lint", pid=99999)

    def test_stale_lock_is_removed(self, tmp_path):
        """Lock older than 20 minutes (2x cron timeout of 600s) is considered stale."""
        import datetime
        old_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc).isoformat()
        lock_file = tmp_path / ".cursors" / "vault.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text(json.dumps({"pid": 1, "started_at": old_time, "job": "vault-ingest"}))
        assert acquire_lock(tmp_path, "vault-lint", pid=99999)

    def test_release_lock_removes_file(self, tmp_path):
        acquire_lock(tmp_path, "vault-ingest", pid=12345)
        release_lock(tmp_path)
        assert not is_locked(tmp_path)

    def test_recent_lock_is_not_stale(self, tmp_path):
        """Lock from <20min ago should block."""
        acquire_lock(tmp_path, "vault-ingest", pid=12345)
        assert not acquire_lock(tmp_path, "vault-lint", pid=99999)
        assert is_locked(tmp_path)


class TestCircuitBreaker:
    def test_circuit_breaker_opens_after_3_failures(self, tmp_path):
        """Circuit opens after max_failures consecutive failures."""
        source = "tldv"
        for i in range(3):
            record_failure(tmp_path, source)
        assert check_circuit_breaker(tmp_path, source, max_failures=3) is True

    def test_circuit_breaker_resets_on_success(self, tmp_path):
        """A successful call resets the failure counter."""
        source = "github"
        record_failure(tmp_path, source)
        record_failure(tmp_path, source)
        record_success(tmp_path, source)
        # After success, failure count should be 0
        assert check_circuit_breaker(tmp_path, source, max_failures=3) is False

    def test_circuit_breaker_skips_for_1h(self, tmp_path):
        """Circuit stays open for 1 hour after trip."""
        import datetime, json
        source = "trello"
        # Pre-populate a failure file with recent timestamp
        failure_file = tmp_path / ".cursors" / f"{source}_failures.json"
        failure_file.parent.mkdir(parents=True, exist_ok=True)
        failure_file.write_text(json.dumps({
            "count": 3,
            "last_failure": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }))
        assert check_circuit_breaker(tmp_path, source, max_failures=3) is True

    def test_circuit_breaker_allows_after_1h_cooldown(self, tmp_path):
        """After 1 hour cooldown, circuit allows requests again."""
        import datetime, json
        source = "github"
        old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
        failure_file = tmp_path / ".cursors" / f"{source}_failures.json"
        failure_file.parent.mkdir(parents=True, exist_ok=True)
        failure_file.write_text(json.dumps({
            "count": 3,
            "last_failure": old_time.isoformat(),
        }))
        # After 1h cooldown, circuit should allow
        assert check_circuit_breaker(tmp_path, source, max_failures=3) is False


class TestEdgeCases:
    def test_write_cursor_survives_corrupted_existing(self, tmp_path):
        """Corrupted JSON cursor file is treated as empty and overwritten."""
        # Pre-write corrupted data
        cursors_dir = tmp_path / ".cursors"
        cursors_dir.mkdir(parents=True, exist_ok=True)
        (cursors_dir / "tldv.json").write_text("not valid json {\"}")
        # read_cursor should not raise; it should return empty
        cursor = read_cursor(tmp_path, "tldv")
        assert cursor == {"last_run_at": None, "last_run_id": None, "watermark": {}}
        # Write should still succeed (overwrite corrupted file)
        data = {"last_run_at": "2026-04-11T10:00:00Z", "last_run_id": "abc", "watermark": {}}
        write_cursor(tmp_path, "tldv", data)
        assert read_cursor(tmp_path, "tldv")["last_run_id"] == "abc"

    def test_lock_ttl_greater_than_cron_timeout(self, tmp_path):
        """Stale threshold (20min) is 2x the cron timeout (600s).
        A lock held for 15min should still block (15min < 20min stale threshold)."""
        import datetime
        # 15 minutes ago — should still be considered recent (not stale)
        recent = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)).isoformat()
        lock_file = tmp_path / ".cursors" / "vault.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text(json.dumps({"pid": 1, "started_at": recent, "job": "vault-ingest"}))
        # 15min lock should NOT be considered stale (threshold is 20min)
        assert not acquire_lock(tmp_path, "vault-lint", pid=99999)

    def test_lock_concurrent_processes(self, tmp_path):
        """Only one process should acquire the lock; others should fail."""
        import os
        import multiprocessing

        def try_acquire(vault_root, results_list, idx):
            got = acquire_lock(vault_root, "vault-ingest", pid=os.getpid())
            results_list.append((idx, got))

        ctx = multiprocessing.get_context("spawn")
        manager = ctx.Manager()
        results = manager.list()

        # Process 0 acquires first
        p0 = ctx.Process(target=try_acquire, args=(tmp_path, results, 0))
        p0.start()
        p0.join()

        # Process 1 should fail to acquire
        p1 = ctx.Process(target=try_acquire, args=(tmp_path, results, 1))
        p1.start()
        p1.join()

        results_dict = dict(results)
        assert results_dict[0] is True   # First process got the lock
        assert results_dict[1] is False  # Second process blocked


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
from typing import Any, TypedDict, NotRequired


# ── TypedDict Contracts ────────────────────────────────────────────────────────

class CursorState(TypedDict, total=False):
    """Shape of a cursor file on disk."""
    last_run_at: str | None
    last_run_id: str | None
    watermark: dict[str, Any]


class RunSummary(TypedDict, total=False):
    """Shape of a run summary written to log.md and emitted by pipelines."""
    run_id: str
    started_at: str
    finished_at: str
    meetings_fetched: int
    persons_resolved: int
    entities_persisted: int
    relationships_written: int
    sources: list[str]
    dry_run: bool
    skipped_reason: str | None
    error: str | None


# ── Lock TTL ──────────────────────────────────────────────────────────────────

LOCK_STALE_SECONDS = 1200  # 20 min — 2x cron timeout (600s)


def _cursors_dir(vault_root: Path) -> Path:
    d = vault_root / ".cursors"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_cursor(vault_root: Path, source: str) -> dict[str, Any]:
    """Read cursor for a source. Returns empty structure if not found/corrupted."""
    f = _cursors_dir(vault_root) / f"{source}.json"
    if not f.exists():
        return {"last_run_at": None, "last_run_id": None, "watermark": {}}
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return {"last_run_at": None, "last_run_id": None, "watermark": {}}


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
            if age < LOCK_STALE_SECONDS:  # < 20 min
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


# ── Circuit Breaker ────────────────────────────────────────────────────────────

CIRCUIT_COOLDOWN_SECONDS = 3600  # 1 hour


def _failure_file(vault_root: Path, source: str) -> Path:
    return _cursors_dir(vault_root) / f"{source}_failures.json"


def check_circuit_breaker(vault_root: Path, source: str, max_failures: int = 3) -> bool:
    """Returns True if circuit is OPEN (skip this source)."""
    f = _failure_file(vault_root, source)
    if not f.exists():
        return False
    try:
        data = json.loads(f.read_text())
        count = data.get("count", 0)
        if count < max_failures:
            return False
        last = datetime.fromisoformat(data["last_failure"])
        age = (datetime.now(timezone.utc) - last).total_seconds()
        return age < CIRCUIT_COOLDOWN_SECONDS  # Still in cooldown
    except (json.JSONDecodeError, KeyError, ValueError):
        return False


def record_failure(vault_root: Path, source: str) -> None:
    """Record a failure for circuit breaker tracking."""
    f = _failure_file(vault_root, source)
    if f.exists():
        data = json.loads(f.read_text())
    else:
        data = {"count": 0, "last_failure": None}
    data["count"] = data.get("count", 0) + 1
    data["last_failure"] = datetime.now(timezone.utc).isoformat()
    tmp = _cursors_dir(vault_root) / f"{source}_failures.json.tmp"
    tmp.write_text(json.dumps(data))
    tmp.rename(f)


def record_success(vault_root: Path, source: str) -> None:
    """Reset failure count for source."""
    f = _failure_file(vault_root, source)
    if f.exists():
        data = json.loads(f.read_text())
        data["count"] = 0
        f.write_text(json.dumps(data))

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

**Acceptance criteria (traceability):**
- All entities MUST include `provenance` frontmatter with `source`, `source_key`, `fetched_at`, `run_id`.

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

## Task 3: Log Manager + RunContext

**Acceptance criteria (traceability):**
- All entities MUST include `provenance` frontmatter with `source`, `source_key`, `fetched_at`, `run_id`.

**Files:**
- Create: `vault/ingest/log_manager.py`
- Create: `vault/ingest/run_context.py`
- Test: `vault/tests/test_log_manager.py`

- [ ] **Step 0 (NEW): Write failing tests for run_context.py**

```python
# vault/tests/test_run_context.py
"""Tests for RunContext dataclass."""
import pytest
from vault.ingest.run_context import RunContext, new_run_context


class TestRunContext:
    def test_new_run_context_generates_uuid(self):
        ctx = new_run_context(vault_root="/tmp/vault", dry_run=False)
        assert ctx.run_id is not None
        assert len(ctx.run_id) == 36  # UUID4

    def test_run_context_fields(self):
        ctx = new_run_context(vault_root="/tmp/vault", dry_run=True)
        assert ctx.vault_root == "/tmp/vault"
        assert ctx.dry_run is True
        assert ctx.started_at is not None

    def test_run_context_repr_includes_run_id(self):
        ctx = new_run_context(vault_root="/tmp/vault", dry_run=False)
        assert ctx.run_id in repr(ctx)
```

- [ ] **Step 0b (NEW): Write RunContext implementation**

```python
# vault/ingest/run_context.py
"""Run context — carries run_id, started_at, vault_root, dry_run through the pipeline."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RunContext:
    run_id: str
    started_at: str
    vault_root: Path
    dry_run: bool

    def elapsed_seconds(self) -> float:
        """Seconds since started_at."""
        start = datetime.fromisoformat(self.started_at)
        return (datetime.now(timezone.utc) - start).total_seconds()


def new_run_context(vault_root: Path | str, dry_run: bool = False) -> RunContext:
    """Factory: generates a fresh RunContext with a new UUID4 run_id."""
    return RunContext(
        run_id=str(uuid.uuid4()),
        started_at=datetime.now(timezone.utc).isoformat(),
        vault_root=Path(vault_root),
        dry_run=dry_run,
    )
```

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_log_manager.py
"""Tests for log.md management with rotation."""
import pytest
from pathlib import Path
from vault.ingest.log_manager import append_log, maybe_rotate_log, log_delivery_failure


class TestLogManager:
    def test_append_log_creates_file(self, tmp_path):
        vault = tmp_path / "vault"
        append_log(vault, "vault-ingest", {"meetings": 5, "persons": 10}, run_id="run-001")
        log = (vault / "log.md").read_text()
        assert "## [" in log
        assert "vault-ingest" in log
        assert "meetings: 5" in log
        assert "run-001" in log  # run_id is logged

    def test_append_log_appends(self, tmp_path):
        vault = tmp_path / "vault"
        append_log(vault, "vault-ingest", {"a": 1}, run_id="run-001")
        append_log(vault, "vault-lint", {"b": 2}, run_id="run-002")
        log = (vault / "log.md").read_text()
        assert "vault-ingest" in log
        assert "vault-lint" in log

    def test_dry_run_entry_is_marked(self, tmp_path):
        vault = tmp_path / "vault"
        append_log(vault, "vault-ingest", {"a": 1}, dry_run=True, run_id="run-001")
        log = (vault / "log.md").read_text()
        assert "[dry-run]" in log

    def test_rotation_moves_old_log(self, tmp_path):
        vault = tmp_path / "vault"
        append_log(vault, "vault-ingest", {"a": 1}, run_id="run-001")
        # Make log.md artificially large
        log_file = vault / "log.md"
        content = log_file.read_text()
        log_file.write_text(content + "x" * 600_000)  # > 500KB
        maybe_rotate_log(vault)
        assert not log_file.exists() or log_file.stat().st_size < 1000
        archive = vault / "log-archive"
        assert archive.exists()

    def test_delivery_failure_log_creates_jsonl(self, tmp_path):
        vault = tmp_path / "vault"
        job_summary = {"meetings": 5, "cards": 3}
        log_delivery_failure(vault, "vault-ingest", job_summary, run_id="run-001")
        log_file = vault / ".delivery-failures.jsonl"
        assert log_file.exists()
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        import json as _json
        record = _json.loads(lines[0])
        assert record["job"] == "vault-ingest"
        assert record["summary"] == job_summary
        assert "timestamp" in record
        assert record["run_id"] == "run-001"

    def test_delivery_failure_appends_jsonl(self, tmp_path):
        vault = tmp_path / "vault"
        log_delivery_failure(vault, "vault-ingest", {"a": 1}, run_id="run-001")
        log_delivery_failure(vault, "vault-lint", {"b": 2}, run_id="run-002")
        log_file = vault / ".delivery-failures.jsonl"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest vault/tests/test_log_manager.py -v --tb=short`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# vault/ingest/log_manager.py
"""Log.md management with monthly rotation.

All entries include run_id for traceability across cron stdout JSON,
log.md entries, delivery-failures.jsonl, and lint reports.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_log(
    vault_root: Path,
    job: str,
    summary: dict[str, Any],
    *,
    run_id: str,
    dry_run: bool = False,
) -> None:
    """Append entry to log.md."""
    log_file = vault_root / "log.md"
    vault_root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")
    prefix = "[dry-run] " if dry_run else ""
    header = f"## [{date_str}] {prefix}{job}  <!-- run_id={run_id} -->"
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


def log_delivery_failure(
    vault_root: Path,
    job: str,
    summary: dict[str, Any],
    *,
    run_id: str,
) -> None:
    """Append delivery failure payload to .delivery-failures.jsonl."""
    vault_root.mkdir(parents=True, exist_ok=True)
    f = vault_root / ".delivery-failures.jsonl"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job": job,
        "summary": summary,
        "run_id": run_id,
    }
    with open(f, "a") as fh:
        fh.write(__import__("json").dumps(payload) + "\n")
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest vault/tests/test_log_manager.py -v --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add vault/ingest/log_manager.py vault/ingest/run_context.py vault/tests/test_log_manager.py vault/tests/test_run_context.py
git commit -m "feat(vault): add RunContext + run_id traceability in log manager"
```

---

## Task 4: Cross-Reference Module

**Files:**
- Create: `vault/ingest/cross_reference.py`
- Test: `vault/tests/test_cross_reference.py`

**Acceptance criteria (provenance):**
- All entities created by this task MUST include `provenance` frontmatter with `source`, `source_key`, `fetched_at`, `run_id`.

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

## Task 5: Pipeline Orchestration (stages + thin wrapper)

**Files:**
- Create: `vault/ingest/stages.py`
- Modify: `vault/ingest/external_ingest.py`
- Test: `vault/tests/test_external_ingest.py` (add tests)
- Test: `vault/tests/test_stages.py`

**Acceptance criteria (traceability):**
- All generated entities MUST include `provenance` frontmatter with `source`, `source_key`, `fetched_at`, `run_id`.
- Persistence write order is strict and documented in code/tests: **entity → relationships → index → log → cursor**.
- Cursor is always written last and never advanced if earlier write steps fail.

- [ ] **Step 1: Write failing tests for PipelineRunner and orchestration behavior**

Add to `vault/tests/test_stages.py`:

```python
from unittest.mock import Mock
from vault.ingest.stages import PipelineRunner


def test_pipeline_runner_executes_stages_in_order():
    events = []

    class S1:
        name = "s1"
        def run(self, ctx, state):
            events.append("s1")
            state["a"] = 1
            return state

    class S2:
        name = "s2"
        def run(self, ctx, state):
            events.append("s2")
            state["b"] = 2
            return state

    runner = PipelineRunner([S1(), S2()])
    out = runner.run(ctx=Mock(), initial_state={})
    assert events == ["s1", "s2"]
    assert out["a"] == 1 and out["b"] == 2
```

Add to `vault/tests/test_external_ingest.py`:

```python
def test_cursors_are_updated_on_success(tmp_path):
    """After successful run, cursors are written for each successful source."""
    from vault.ingest.cursor import read_cursor
    from vault.ingest.external_ingest import run_external_ingest
    from unittest.mock import patch

    raw = [{"id": "c1", "name": "Test", "created_at": "2026-04-11T10:00:00Z",
            "participants": [{"id": "p1", "name": "Bob", "email": None,
                              "source_key": "tldv:p1", "source": "tldv_api"}],
            "whisper_transcript_json": []}]

    with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=raw), \
         patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
        run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)

    cursor = read_cursor(tmp_path, "tldv")
    assert cursor["last_run_at"] is not None
    assert cursor["last_run_id"] is not None


def test_lock_prevents_concurrent_runs(tmp_path):
    from vault.ingest.cursor import acquire_lock
    from vault.ingest.external_ingest import run_external_ingest

    acquire_lock(tmp_path, "vault-lint", pid=99999)
    result = run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)
    assert result.get("skipped_reason") == "locked"


def test_write_order_cursor_last(tmp_path, monkeypatch):
    """Write order MUST be: entity -> relationships -> index -> log -> cursor."""
    from vault.ingest.external_ingest import run_external_ingest

    calls = []
    monkeypatch.setattr("vault.ingest.external_ingest.persist_entities", lambda *a, **k: calls.append("entity"))
    monkeypatch.setattr("vault.ingest.external_ingest.persist_relationships", lambda *a, **k: calls.append("relationships"))
    monkeypatch.setattr("vault.ingest.external_ingest.update_index", lambda *a, **k: calls.append("index"))
    monkeypatch.setattr("vault.ingest.external_ingest.append_log", lambda *a, **k: calls.append("log"))
    monkeypatch.setattr("vault.ingest.external_ingest.write_cursor", lambda *a, **k: calls.append("cursor"))

    run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)
    assert calls == ["entity", "relationships", "index", "log", "cursor"]


def test_cursor_not_written_if_entity_write_fails(tmp_path, monkeypatch):
    from vault.ingest.external_ingest import run_external_ingest

    cursor_called = False

    def fail_entity(*args, **kwargs):
        raise RuntimeError("entity write failed")

    def mark_cursor(*args, **kwargs):
        nonlocal cursor_called
        cursor_called = True

    monkeypatch.setattr("vault.ingest.external_ingest.persist_entities", fail_entity)
    monkeypatch.setattr("vault.ingest.external_ingest.write_cursor", mark_cursor)

    run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)
    assert cursor_called is False


def test_idempotent_run_no_duplicates(tmp_path):
    """Second run must not duplicate index/log entries for same source payload."""
    from vault.ingest.external_ingest import run_external_ingest

    run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)
    run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)

    index_text = (tmp_path / "index.md").read_text()
    log_text = (tmp_path / "log.md").read_text()
    assert index_text.count("meeting-") == 1
    assert log_text.count("vault-ingest") == 1


def test_partial_source_failure_cursors_correct(tmp_path, monkeypatch):
    """If source A fails, B/C succeed and only B/C cursors are updated."""
    from vault.ingest.cursor import read_cursor
    from vault.ingest.external_ingest import run_external_ingest

    monkeypatch.setattr("vault.ingest.external_ingest.fetch_tldv", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("tldv down")))
    monkeypatch.setattr("vault.ingest.external_ingest.fetch_trello", lambda *a, **k: [])
    monkeypatch.setattr("vault.ingest.external_ingest.fetch_github", lambda *a, **k: [])

    run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)

    assert read_cursor(tmp_path, "tldv")["last_run_at"] is None
    assert read_cursor(tmp_path, "trello")["last_run_at"] is not None
    assert read_cursor(tmp_path, "github")["last_run_at"] is not None


def test_generated_entities_include_provenance(tmp_path):
    """Every generated entity must include source/source_key/fetched_at/run_id provenance."""
    from vault.ingest.external_ingest import run_external_ingest

    run_external_ingest(vault_root=tmp_path, tldv_token="fake", meeting_days=1)
    entity = next((tmp_path / "entities").glob("*.md"))
    content = entity.read_text()
    assert "provenance:" in content
    assert "source:" in content
    assert "source_key:" in content
    assert "fetched_at:" in content
    assert "run_id:" in content
```

- [ ] **Step 2: Implement stages architecture and thin wrapper**

Create `vault/ingest/stages.py` with:
- `IngestStage` protocol (`name: str`, `run(ctx, state) -> dict[str, Any]`)
- `PipelineRunner` class (sequential stage execution, shared mutable state dict, stop-on-fatal)
- Stage classes/functions (one responsibility each):
  1. `lock`
  2. `fetch_tldv`
  3. `fetch_trello`
  4. `fetch_github`
  5. `resolve_participants`
  6. `cross_reference`
  7. `persist`
  8. `update_index`
  9. `update_log`
  10. `write_cursors`
  11. `unlock`

Refactor `run_external_ingest` in `external_ingest.py` to a thin wrapper that:
1. Creates `RunContext` with UUID4 run_id at pipeline start.
2. Builds stage list.
3. Invokes `PipelineRunner`.
4. Returns summarized result.

- [ ] **Step 3: Enforce persistence write order + cursor last**

Explicitly document and enforce in code:
1. persist entity markdown files
2. persist relationships
3. update index
4. append log
5. write cursors (last)

If any step before cursors fails, cursor stage must be skipped.

- [ ] **Step 4: Run full suite**

Run: `python3 -m pytest vault/tests/ -q --tb=short`
Expected: All pass, no regressions

- [ ] **Step 5: Commit**

```bash
git add vault/ingest/stages.py vault/ingest/external_ingest.py vault/tests/test_stages.py vault/tests/test_external_ingest.py
git commit -m "refactor(ingest): stage-based pipeline runner + thin external_ingest wrapper"
```

---

## Task 5b: Vault Lint Scans

**Acceptance criteria (traceability):**
- All entities MUST include `provenance` frontmatter with `source`, `source_key`, `fetched_at`, `run_id`.

**Files:**
- Create: `vault/ingest/vault_lint_scanner.py`
- Test: `vault/tests/test_vault_lint_scanner.py`

- [ ] **Step 1: Write the failing tests**

```python
# vault/tests/test_vault_lint_scanner.py
"""Tests for vault lint scans."""
from pathlib import Path
from vault.ingest.vault_lint_scanner import run_lint_scans


def test_find_orphans(tmp_path):
    """Pages in entities/ not referenced in index.md should be flagged."""
    vault = tmp_path / "vault"
    (vault / "entities").mkdir(parents=True)
    (vault / "entities" / "person-a.md").write_text("---\nid: person-a\n---\n")
    (vault / "index.md").write_text("# Index\n")

    result = run_lint_scans(vault)
    assert any("entities/person-a.md" in item.get("path", "") for item in result["orphans"])


def test_find_stale(tmp_path):
    """Pages with last_seen_at > 30 days and not archived should be stale."""
    import datetime
    vault = tmp_path / "vault"
    (vault / "entities").mkdir(parents=True)
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=45)).date().isoformat()
    (vault / "entities" / "person-b.md").write_text(
        f"---\nid: person-b\nlast_seen_at: {old}\narchived: false\n---\n"
    )

    result = run_lint_scans(vault)
    assert any("person-b" in item.get("id", "") for item in result["stale"])


def test_find_gaps(tmp_path):
    """Concepts referenced in entity frontmatter without concept page should be gaps."""
    vault = tmp_path / "vault"
    (vault / "entities").mkdir(parents=True)
    (vault / "concepts").mkdir(parents=True)
    (vault / "entities" / "meeting-x.md").write_text(
        "---\nid: meeting-x\nconcepts: [bat, delphos]\n---\n"
    )
    (vault / "concepts" / "bat.md").write_text("---\nid: bat\n---\n")

    result = run_lint_scans(vault)
    assert any(item.get("concept") == "delphos" for item in result["gaps"])


def test_find_contradictions(tmp_path):
    """Same id_canonical with conflicting confidence/data should be contradictions."""
    vault = tmp_path / "vault"
    (vault / "entities").mkdir(parents=True)
    (vault / "entities" / "person-1.md").write_text(
        "---\nid: person-1\nid_canonical: robert-urech\nconfidence: 0.90\nrole: CTO\n---\n"
    )
    (vault / "entities" / "person-2.md").write_text(
        "---\nid: person-2\nid_canonical: robert-urech\nconfidence: 0.60\nrole: CEO\n---\n"
    )

    result = run_lint_scans(vault)
    assert any(item.get("id_canonical") == "robert-urech" for item in result["contradictions"])


def test_suggest_cross_refs(tmp_path):
    """Person appearing in 5+ meetings without concept page should generate suggestion."""
    vault = tmp_path / "vault"
    (vault / "entities").mkdir(parents=True)
    (vault / "concepts").mkdir(parents=True)
    (vault / "entities" / "person-lincoln.md").write_text(
        "---\nid: person-lincoln\nname: Lincoln\nmeeting_count: 7\n---\n"
    )

    result = run_lint_scans(vault)
    assert any(item.get("type") == "cross_ref" for item in result["suggestions"])
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest vault/tests/test_vault_lint_scanner.py -v --tb=short`
Expected: FAIL with `ModuleNotFoundError: No module named 'vault.ingest.vault_lint_scanner'`

- [ ] **Step 3: Write minimal implementation with TypedDict contracts**

```python
# vault/ingest/vault_lint_scanner.py
"""Vault lint scanner — orphans, stale, gaps, contradictions, suggestions + metrics."""
from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict, NotRequired


# ── TypedDict Contracts ────────────────────────────────────────────────────────

class LintReport(TypedDict, total=False):
    """Shape returned by run_lint_scans and run_full_lint."""
    orphans: list[dict[str, Any]]
    stale: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    suggestions: list[dict[str, Any]]
    metrics: dict[str, Any]
    run_id: str
    scan_duration_ms: int
    pages_scanned: int
    error_count: int


def run_lint_scans(vault_root: Path) -> LintReport:
    return {
        "orphans": [],
        "stale": [],
        "gaps": [],
        "contradictions": [],
        "suggestions": [],
        "metrics": {
            "total_entities": 0,
            "total_concepts": 0,
            "total_decisions": 0,
            "total_relationships": 0,
            "avg_links_per_page": 0.0,
            "orphans_by_domain": {},
            "avg_age_days": 0.0,
            # Spec §5 SLO-oriented metrics
            "scan_duration_ms": 0,
            "pages_scanned": 0,
            "error_count": 0,
            "lint_coverage_ratio": 0.0,
        },
    }
```

- [ ] **Step 4: Expand implementation to satisfy all scans**

Implement scan functions used by `run_lint_scans(vault_root)`:
- `find_orphans(...)`
- `find_stale(...)`
- `find_gaps(...)`
- `find_contradictions(...)`
- `suggest_cross_refs(...)`

Ensure the return payload follows:

```python
def run_lint_scans(vault_root: Path) -> dict[str, Any]:
    return {
        "orphans": [...],
        "stale": [...],
        "gaps": [...],
        "contradictions": [...],
        "suggestions": [...],
        "metrics": {
            "total_entities": N,
            "total_concepts": N,
            "total_decisions": N,
            "total_relationships": N,
            "avg_links_per_page": N.N,
            "orphans_by_domain": {...},
            "avg_age_days": N.N,
            # Include spec §5 SLO metrics in this dict
        },
    }
```

- [ ] **Step 5: Run tests to verify pass**

Run: `python3 -m pytest vault/tests/test_vault_lint_scanner.py -v --tb=short`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add vault/ingest/vault_lint_scanner.py vault/tests/test_vault_lint_scanner.py
git commit -m "feat(vault): lint scanner — orphans, stale, gaps, contradictions, cross-ref suggestions"
```

---

## Task 6: Create cron helper scripts + configure vault crons

**Files:**
- Create: `vault/crons/vault_ingest_cron.py`
- Create: `vault/crons/vault_lint_cron.py`

- [ ] **Step 1: Write failing tests for cron helpers (optional but recommended)**

Add tests in:
- `vault/tests/test_vault_ingest_cron.py`
- `vault/tests/test_vault_lint_cron.py`

Validate each entry point:
- loads `.openclaw/.env`
- calls pipeline function (`run_external_ingest` / `run_full_lint`)
- returns non-zero exit on uncaught error
- prints summary payload for cron observability

- [ ] **Step 2: Create `vault_ingest_cron.py` entry point**

```python
# vault/crons/vault_ingest_cron.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from vault.ingest.external_ingest import run_external_ingest


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    load_env(Path.home() / ".openclaw/.env")
    try:
        result = run_external_ingest(
            tldv_token=os.environ.get("TLDV_JWT_TOKEN"),
            meeting_days=int(os.environ.get("VAULT_MEETING_DAYS", "1")),
        )
        print(result)
        return 0
    except Exception as e:
        print(f"vault-ingest-cron failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Create `vault_lint_cron.py` entry point**

```python
# vault/crons/vault_lint_cron.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from vault.lint import run_full_lint


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    load_env(Path.home() / ".openclaw/.env")
    try:
        result = run_full_lint()
        print(result)
        return 0
    except Exception as e:
        print(f"vault-lint-cron failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create vault-ingest cron (use helper script, no inline Python)**

```bash
openclaw cron add \
  --name "vault-ingest" \
  --cron "0 10,14,20 * * *" \
  --tz "America/Sao_Paulo" \
  --session isolated \
  --model fastest \
  --message "Run vault ingest cron helper. Execute: cd /home/lincoln/.openclaw/workspace-livy-memory/.worktrees/wave-c-pipeline-wiring && python3 -m vault.crons.vault_ingest_cron 2>&1" \
  --timeout 600 \
  --announce \
  --channel telegram \
  --to 7426291192
```

- [ ] **Step 5: Disable old crons (one by one)**

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

- [ ] **Step 6: Create vault-lint cron (use helper script, no inline Python)**

```bash
openclaw cron add \
  --name "vault-lint" \
  --cron "0 21 * * *" \
  --tz "America/Sao_Paulo" \
  --session isolated \
  --model "zai/glm-5.1" \
  --message "Run vault lint cron helper. Execute: cd /home/lincoln/.openclaw/workspace-livy-memory/.worktrees/wave-c-pipeline-wiring && python3 -m vault.crons.vault_lint_cron 2>&1" \
  --timeout 600 \
  --announce \
  --channel telegram \
  --to 7426291192
```

- [ ] **Step 7: Verify crons**

Run: `openclaw cron list`
Expected: vault-ingest + vault-lint enabled, 7 old crons disabled

- [ ] **Step 8: Commit**

```bash
git add vault/crons/vault_ingest_cron.py vault/crons/vault_lint_cron.py vault/tests/test_vault_ingest_cron.py vault/tests/test_vault_lint_cron.py
git commit -m "feat(vault): cron helper scripts for ingest and lint entry points"
```

---

## Task 6b (NEW): HTTP Resilience Module

**Acceptance criteria (traceability):**
- All entities MUST include `provenance` frontmatter with `source`, `source_key`, `fetched_at`, `run_id`.

**Files:**
- Create: `vault/ingest/resilience.py`
- Test: `vault/tests/test_resilience.py`

- [ ] **Step 1: Write failing tests for resilience**

```python
import pytest
import requests
from vault.ingest.resilience import retry_with_backoff, is_retryable


class TestRetryWithBackoff:
    def test_retries_on_5xx(self):
        calls = []
        def fail_twice():
            calls.append(1)
            if len(calls) < 3:
                raise requests.HTTPError("500 Server Error")
            return "ok"
        result = retry_with_backoff(fail_twice, max_retries=3, backoff_base=0.1)
        assert result == "ok"
        assert len(calls) == 3

    def test_retries_on_timeout(self):
        calls = []
        def fail_twice():
            calls.append(1)
            if len(calls) < 2:
                raise requests.Timeout("timed out")
            return "ok"
        result = retry_with_backoff(fail_twice, max_retries=3, backoff_base=0.1)
        assert result == "ok"
        assert len(calls) == 2

    def test_no_retry_on_4xx_except_429(self):
        calls = []
        def always_fail():
            calls.append(1)
            raise requests.HTTPError("400 Bad Request")
        with pytest.raises(requests.HTTPError):
            retry_with_backoff(always_fail, max_retries=3, backoff_base=0.1)
        assert len(calls) == 1  # No retries

    def test_429_respects_retry_after(self):
        """429 should use Retry-After header if present."""
        calls = []
        def fail_then_ok():
            calls.append(1)
            if len(calls) == 1:
                err = requests.HTTPError("429")
                err.response = requests.Response()
                err.response.status_code = 429
                err.response.headers["Retry-After"] = "0"  # 0 seconds for test speed
                raise err
            return "ok"
        result = retry_with_backoff(fail_then_ok, max_retries=3, backoff_base=1)
        assert result == "ok"

    def test_401_refresh_once_then_retry(self):
        """401 should try token refresh once before retry."""
        calls = []
        def fail_then_ok():
            calls.append(1)
            if len(calls) == 1:
                err = requests.HTTPError("401 Unauthorized")
                err.response = requests.Response()
                err.response.status_code = 401
                raise err
            return "ok"
        result = retry_with_backoff(fail_then_ok, max_retries=3, backoff_base=0.1)
        assert result == "ok"
        assert len(calls) == 2

    def test_non_retryable_exception_raises_immediately(self):
        calls = []
        def fail():
            calls.append(1)
            raise ValueError("not a requests exception")
        with pytest.raises(ValueError):
            retry_with_backoff(fail, max_retries=3, backoff_base=0.1)
        assert len(calls) == 1


class TestIsRetryable:
    def test_5xx_is_retryable(self):
        e = requests.HTTPError("500")
        e.response = requests.Response()
        e.response.status_code = 500
        assert is_retryable(e) is True

    def test_429_is_retryable(self):
        e = requests.HTTPError("429")
        e.response = requests.Response()
        e.response.status_code = 429
        assert is_retryable(e) is True

    def test_400_not_retryable(self):
        e = requests.HTTPError("400")
        e.response = requests.Response()
        e.response.status_code = 400
        assert is_retryable(e) is False

    def test_timeout_is_retryable(self):
        assert is_retryable(requests.Timeout()) is True

    def test_connection_error_is_retryable(self):
        assert is_retryable(requests.ConnectionError()) is True

    def test_other_exception_not_retryable(self):
        assert is_retryable(ValueError("bad")) is False
```

- [ ] **Step 2: Write implementation**

```python
# vault/ingest/resilience.py
"""HTTP retry with backoff + circuit breaker for external source calls."""
from __future__ import annotations

import time
import requests
from typing import Callable, TypeVar

T = TypeVar("T")


def is_retryable(exception: Exception) -> bool:
    """Classify whether an exception warrants a retry."""
    if isinstance(exception, requests.Timeout):
        return True
    if isinstance(exception, requests.ConnectionError):
        return True
    if isinstance(exception, requests.HTTPError):
        code = exception.response.status_code if exception.response else 0
        if code == 429:  # Rate limited — respect Retry-After
            return True
        if 500 <= code < 600:  # Server error
            return True
        if code == 401:  # Auth expired — one refresh attempt
            return True
        return False
    return False


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    backoff_base: float = 30.0,
) -> T:
    """Call fn with exponential backoff for retryable errors.

    - 429: respects Retry-After header + backoff
    - 5xx: retry with backoff
    - 401: one token refresh attempt
    - Timeout/ConnectionError: retry with backoff
    - Other: raise immediately (no retry)
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except requests.HTTPError as e:
            last_exc = e
            if not is_retryable(e):
                raise
            # Handle 401: one token refresh attempt
            if e.response and e.response.status_code == 401:
                if attempt == 0:
                    # Try to refresh token (hook for caller to override)
                    continue
                raise
            # Handle 429: use Retry-After if present
            if e.response and e.response.status_code == 429:
                retry_after = float(e.response.headers.get("Retry-After", backoff_base))
                time.sleep(retry_after)
                continue
            # Exponential backoff for other retryable errors
            if attempt < max_retries:
                wait = backoff_base * (2 ** attempt)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            last_exc = e
            if not is_retryable(e):
                raise
            if attempt < max_retries:
                wait = backoff_base * (2 ** attempt)
                time.sleep(wait)
                continue
            raise
    raise last_exc or RuntimeError("retry_with_backoff: no exception recorded")
```

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest vault/tests/test_resilience.py -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add vault/ingest/resilience.py vault/tests/test_resilience.py
git commit -m "feat(vault): HTTP resilience — retry_with_backoff + is_retryable circuit breaker"
```

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
- Create: `vault/tests/test_vault_ingest_cron.py` (if not created in Task 7)
- Create: `vault/tests/test_vault_lint_cron.py` (if not created in Task 7)

- [ ] **Step 1: Write integration test for vault-ingest (if not covered in Task 7)**

Test full flow: lock → fetch → resolve → build → persist → cursor → index → log → unlock

- [ ] **Step 2: Write integration test for vault-lint (if not covered in Task 7)**

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

## Task 9b (NEW): vault status Utility

**Files:**
- Create: `vault/commands/status.py`
- Test: `vault/tests/test_vault_status.py`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path
from vault.commands.status import vault_status


def test_status_shows_lock_state(tmp_path):
    """vault_status shows current lock state."""
    from vault.ingest.cursor import acquire_lock
    acquire_lock(tmp_path, "vault-ingest", pid=12345)
    result = vault_status(tmp_path)
    assert result["lock"]["active"] is True
    assert result["lock"]["job"] == "vault-ingest"


def test_status_shows_cursor_timestamps(tmp_path):
    """vault_status shows last_run_at for each source cursor."""
    from vault.ingest.cursor import write_cursor
    write_cursor(tmp_path, "tldv", {"last_run_at": "2026-04-11T10:00:00Z", "last_run_id": "r1", "watermark": {}})
    write_cursor(tmp_path, "trello", {"last_run_at": "2026-04-11T11:00:00Z", "last_run_id": "r2", "watermark": {}})
    result = vault_status(tmp_path)
    assert "tldv" in result["cursors"]
    assert "trello" in result["cursors"]
    assert result["cursors"]["tldv"]["last_run_at"] is not None


def test_status_shows_delivery_failure_count(tmp_path):
    """vault_status shows count of delivery failures in .delivery-failures.jsonl."""
    from vault.ingest.log_manager import log_delivery_failure
    log_delivery_failure(tmp_path, "vault-ingest", {"a": 1}, run_id="r1")
    log_delivery_failure(tmp_path, "vault-ingest", {"b": 2}, run_id="r2")
    result = vault_status(tmp_path)
    assert result["delivery_failures"] == 2


def test_status_shows_circuit_breaker_state(tmp_path):
    """vault_status shows which sources have open circuits."""
    from vault.ingest.cursor import record_failure
    for _ in range(3):
        record_failure(tmp_path, "tldv")
    result = vault_status(tmp_path)
    assert "tldv" in result["circuit_breakers"]
    assert result["circuit_breakers"]["tldv"]["open"] is True
```

- [ ] **Step 2: Write implementation**

```python
# vault/commands/status.py
"""vault status — shows lock state, cursor timestamps, last run status,
delivery failure count, and circuit breaker state."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vault.ingest.cursor import (
    is_locked,
    read_cursor,
    check_circuit_breaker,
)


def vault_status(vault_root: Path) -> dict[str, Any]:
    """Return a snapshot of vault operational state."""
    cursors_dir = vault_root / ".cursors"

    # Lock state
    lock_info: dict[str, Any] = {"active": False}
    lock_file = cursors_dir / "vault.lock"
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text())
            started = datetime.fromisoformat(data["started_at"])
            age = (datetime.now(timezone.utc) - started).total_seconds()
            lock_info = {
                "active": True,
                "job": data.get("job"),
                "pid": data.get("pid"),
                "started_at": data["started_at"],
                "age_seconds": round(age, 1),
                "stale": age >= 1200,
            }
        except (json.JSONDecodeError, KeyError, ValueError):
            lock_info = {"active": True, "error": "corrupted"}

    # Cursor timestamps
    cursor_state: dict[str, Any] = {}
    for f in sorted((cursors_dir).glob("*.json")):
        if f.name in ("vault.lock",) or f.name.endswith("_failures.json"):
            continue
        source = f.stem
        try:
            data = json.loads(f.read_text())
            cursor_state[source] = {
                "last_run_at": data.get("last_run_at"),
                "last_run_id": data.get("last_run_id"),
            }
        except json.JSONDecodeError:
            cursor_state[source] = {"error": "corrupted"}

    # Delivery failures
    failures_file = vault_root / ".delivery-failures.jsonl"
    delivery_failures = 0
    if failures_file.exists():
        lines = failures_file.read_text().strip().splitlines()
        delivery_failures = len([l for l in lines if l.strip()])

    # Circuit breakers
    circuits: dict[str, Any] = {}
    for f in sorted((cursors_dir).glob("*_failures.json")):
        source = f.stem.replace("_failures", "")
        data = json.loads(f.read_text())
        circuits[source] = {
            "open": check_circuit_breaker(vault_root, source),
            "failure_count": data.get("count", 0),
            "last_failure": data.get("last_failure"),
        }

    return {
        "vault_root": str(vault_root),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "lock": lock_info,
        "cursors": cursor_state,
        "delivery_failures": delivery_failures,
        "circuit_breakers": circuits,
    }
```

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest vault/tests/test_vault_status.py -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add vault/commands/status.py vault/tests/test_vault_status.py
git commit -m "feat(vault): vault status utility — lock, cursor, failure, and circuit state"
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

---

## Rollback Plan

If the new crons cause issues and need to be reverted to the original 7-cron setup:

- [ ] **Step 1: Disable new crons**

```bash
# Identify new cron IDs from openclaw cron list
openclaw cron disable <vault-ingest-id>
openclaw cron disable <vault-lint-id>
```

- [ ] **Step 2: Re-enable original crons**

```bash
# Use the IDs from spec Section 2.3 (or discovered via openclaw cron list --disabled)
openclaw cron enable 9dfe2886-...   # memory-agent-sonhar
openclaw cron enable 2ec55149-...   # memory-vault-daily-pipeline
openclaw cron enable b36e4fb9-...   # daily-memory-save
openclaw cron enable aa5cd560-...   # memory-agent-feedback-learn
openclaw cron enable 0c388629-...   # autoresearch
openclaw cron enable 53b45f6f-...   # signal-curation
openclaw cron enable 63a44a25-...   # openclaw-health
```

- [ ] **Step 3: Verify crons restored**

```bash
openclaw cron list
```
Expected: 7 original crons enabled, vault-ingest + vault-lint disabled or absent.

- [ ] **Step 4: Roll back branch**

```bash
git checkout master
git pull origin master
```

> **Note:** Entity data written by the new pipeline to the vault is forward-compatible with the original crons (markdown files + cursors). The original crons will simply ignore new files they don't understand.
