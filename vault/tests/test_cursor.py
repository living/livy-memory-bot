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
        data = {"last_run_at": "2026-04-11T10:00:00Z", "last_run_id": "1", "watermark": {}}
        write_cursor(tmp_path, "tldv", data)
        assert (tmp_path / ".cursors" / "tldv.json").exists()
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
        acquire_lock(tmp_path, "vault-ingest", pid=12345)
        assert not acquire_lock(tmp_path, "vault-lint", pid=99999)
        assert is_locked(tmp_path)


class TestCircuitBreaker:
    def test_circuit_breaker_opens_after_3_failures(self, tmp_path):
        source = "tldv"
        for i in range(3):
            record_failure(tmp_path, source)
        assert check_circuit_breaker(tmp_path, source, max_failures=3) is True

    def test_circuit_breaker_resets_on_success(self, tmp_path):
        source = "github"
        record_failure(tmp_path, source)
        record_failure(tmp_path, source)
        record_success(tmp_path, source)
        assert check_circuit_breaker(tmp_path, source, max_failures=3) is False

    def test_circuit_breaker_skips_for_1h(self, tmp_path):
        import datetime, json
        source = "trello"
        failure_file = tmp_path / ".cursors" / f"{source}_failures.json"
        failure_file.parent.mkdir(parents=True, exist_ok=True)
        failure_file.write_text(json.dumps({
            "count": 3,
            "last_failure": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }))
        assert check_circuit_breaker(tmp_path, source, max_failures=3) is True

    def test_circuit_breaker_allows_after_1h_cooldown(self, tmp_path):
        import datetime, json
        source = "github"
        old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
        failure_file = tmp_path / ".cursors" / f"{source}_failures.json"
        failure_file.parent.mkdir(parents=True, exist_ok=True)
        failure_file.write_text(json.dumps({
            "count": 3,
            "last_failure": old_time.isoformat(),
        }))
        assert check_circuit_breaker(tmp_path, source, max_failures=3) is False


def _try_acquire_for_test(vault_root, results_list, idx):
    """Module-level helper for concurrent lock test (must be picklable)."""
    from vault.ingest.cursor import acquire_lock
    import os
    got = acquire_lock(vault_root, "vault-ingest", pid=os.getpid())
    results_list.append((idx, got))


class TestEdgeCases:
    def test_write_cursor_survives_corrupted_existing(self, tmp_path):
        cursors_dir = tmp_path / ".cursors"
        cursors_dir.mkdir(parents=True, exist_ok=True)
        (cursors_dir / "tldv.json").write_text("not valid json {\"}")
        cursor = read_cursor(tmp_path, "tldv")
        assert cursor == {"last_run_at": None, "last_run_id": None, "watermark": {}}
        data = {"last_run_at": "2026-04-11T10:00:00Z", "last_run_id": "abc", "watermark": {}}
        write_cursor(tmp_path, "tldv", data)
        assert read_cursor(tmp_path, "tldv")["last_run_id"] == "abc"

    def test_lock_ttl_greater_than_cron_timeout(self, tmp_path):
        import datetime
        recent = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)).isoformat()
        lock_file = tmp_path / ".cursors" / "vault.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text(json.dumps({"pid": 1, "started_at": recent, "job": "vault-ingest"}))
        assert not acquire_lock(tmp_path, "vault-lint", pid=99999)

    def test_lock_concurrent_processes(self, tmp_path):
        import multiprocessing

        ctx = multiprocessing.get_context("spawn")
        manager = ctx.Manager()
        results = manager.list()

        p0 = ctx.Process(target=_try_acquire_for_test, args=(tmp_path, results, 0))
        p0.start()
        p0.join()

        p1 = ctx.Process(target=_try_acquire_for_test, args=(tmp_path, results, 1))
        p1.start()
        p1.join()

        results_dict = dict(results)
        assert results_dict[0] is True
        assert results_dict[1] is False
