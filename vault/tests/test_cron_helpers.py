"""Tests for cron helper scripts."""

import json
from types import SimpleNamespace

from vault.crons import vault_ingest_cron, vault_lint_cron


class TestVaultIngestCron:
    def test_load_env_reads_file(self, tmp_path, monkeypatch):
        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        env_file = openclaw_dir / ".env"
        env_file.write_text("TEST_KEY=test_value\n# comment\nINVALID\n")

        monkeypatch.setattr(vault_ingest_cron.Path, "home", lambda: tmp_path)
        monkeypatch.delenv("TEST_KEY", raising=False)

        vault_ingest_cron.load_env()

        assert vault_ingest_cron.os.environ.get("TEST_KEY") == "test_value"

    def test_main_outputs_json(self, monkeypatch, capsys):
        monkeypatch.setattr(vault_ingest_cron, "load_env", lambda: None)
        monkeypatch.setenv("TLDV_JWT_TOKEN", "token")
        monkeypatch.setenv("VAULT_DRY_RUN", "true")

        def fake_run_external_ingest(**kwargs):
            assert kwargs["meeting_days"] == 1
            assert kwargs["dry_run"] is True
            return {"meetings_fetched": 0, "run_id": "test"}

        monkeypatch.setattr(
            "vault.ingest.external_ingest.run_external_ingest",
            fake_run_external_ingest,
        )

        vault_ingest_cron.main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["meetings_fetched"] == 0


class TestVaultLintCron:
    def test_main_outputs_json(self, monkeypatch, capsys):
        monkeypatch.setattr(vault_lint_cron, "load_env", lambda: None)

        monkeypatch.setattr(
            "vault.ingest.run_context.new_run_context",
            lambda vault_root: SimpleNamespace(run_id="run-123"),
        )
        monkeypatch.setattr("vault.ingest.cursor.acquire_lock", lambda *_args: True)
        monkeypatch.setattr("vault.ingest.cursor.release_lock", lambda *_args: None)
        monkeypatch.setattr("vault.ingest.log_manager.append_log", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(
            "vault.ingest.vault_lint_scanner.run_lint_scans",
            lambda _vault_root: {
                "orphans": [],
                "stale": [],
                "gaps": [],
                "contradictions": [],
                "metrics": {"total_entities": 0},
            },
        )

        vault_lint_cron.main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["run_id"] == "run-123"
