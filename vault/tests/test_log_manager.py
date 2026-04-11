"""Tests for log.md management with rotation."""
from vault.ingest.log_manager import append_log, maybe_rotate_log, log_delivery_failure


class TestLogManager:
    def test_append_log_creates_file(self, tmp_path):
        vault = tmp_path / "vault"
        append_log(vault, "vault-ingest", {"meetings": 5, "persons": 10}, run_id="run-001")
        log = (vault / "log.md").read_text()
        assert "## [" in log
        assert "vault-ingest" in log
        assert "meetings: 5" in log
        assert "run-001" in log

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
        log_file = vault / "log.md"
        content = log_file.read_text()
        log_file.write_text(content + "x" * 600_000)
        maybe_rotate_log(vault)
        assert not log_file.exists() or log_file.stat().st_size < 1000
        archive = vault / "log-archive"
        assert archive.exists()

    def test_delivery_failure_log_creates_jsonl(self, tmp_path):
        vault = tmp_path / "vault"
        log_delivery_failure(vault, "vault-ingest", {"meetings": 5}, run_id="run-001")
        log_file = vault / ".delivery-failures.jsonl"
        assert log_file.exists()
        import json
        record = json.loads(log_file.read_text().strip())
        assert record["job"] == "vault-ingest"
        assert record["run_id"] == "run-001"

    def test_delivery_failure_appends_jsonl(self, tmp_path):
        vault = tmp_path / "vault"
        log_delivery_failure(vault, "vault-ingest", {"a": 1}, run_id="run-001")
        log_delivery_failure(vault, "vault-lint", {"b": 2}, run_id="run-002")
        lines = (vault / ".delivery-failures.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
