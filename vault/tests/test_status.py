"""Tests for vault status utility."""
import json
import pytest
from pathlib import Path
from vault.commands.status import vault_status


class TestVaultStatus:
    def test_returns_lock_state(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        status = vault_status(vault)
        assert "locked" in status
        assert status["locked"] is False

    def test_detects_active_lock(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        from vault.ingest.cursor import acquire_lock
        acquire_lock(vault, "vault-ingest", pid=12345)
        status = vault_status(vault)
        assert status["locked"] is True
        assert status["lock_job"] == "vault-ingest"

    def test_reports_cursor_state(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        from vault.ingest.cursor import write_cursor
        write_cursor(vault, "tldv", {"last_run_at": "2026-04-11T10:00:00Z", "last_run_id": "abc", "watermark": {}})
        status = vault_status(vault)
        assert "cursors" in status
        assert "tldv" in status["cursors"]
        assert status["cursors"]["tldv"]["last_run_at"] == "2026-04-11T10:00:00Z"

    def test_reports_delivery_failures_count(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        from vault.ingest.log_manager import log_delivery_failure
        log_delivery_failure(vault, "vault-ingest", {"a": 1}, run_id="r1")
        log_delivery_failure(vault, "vault-lint", {"b": 2}, run_id="r2")
        status = vault_status(vault)
        assert status["delivery_failures"] == 2

    def test_reports_circuit_breaker_state(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        from vault.ingest.cursor import record_failure
        for _ in range(3):
            record_failure(vault, "tldv")
        status = vault_status(vault)
        assert "circuit_breakers" in status
        assert status["circuit_breakers"]["tldv"]["open"] is True

    def test_empty_vault_no_crash(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        status = vault_status(vault)
        assert isinstance(status, dict)
        assert status["locked"] is False
        assert status["delivery_failures"] == 0
