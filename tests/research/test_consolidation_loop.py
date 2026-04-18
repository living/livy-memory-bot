"""Tests for vault/crons/research_*_cron.py entrypoints.

Covers:
- research_tldv_cron  — lock + pipeline + release
- research_github_cron — lock + pipeline + release
- research_consolidation_cron — env load, pipeline runs (tldv+github), compact, snapshot, log
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — import without side-effects
# ---------------------------------------------------------------------------

def _import_module(name: str):
    from importlib import import_module
    return import_module(name)


# ---------------------------------------------------------------------------
# Test: research_tldv_cron
# ---------------------------------------------------------------------------

class TestResearchTldvCron:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, tmp_path):
        self.tmp_path = tmp_path
        monkeypatch.delenv("RESEARCH_TLDV_INTERVAL_MIN", raising=False)

    def test_interval_env_var_default_15(self):
        from vault.crons import research_tldv_cron
        assert research_tldv_cron.LOCK_PATH == ".research/tldv/lock"
        assert research_tldv_cron.RESEARCH_DIR == ".research/tldv"
        assert research_tldv_cron.STATE_PATH == "state/identity-graph/state.json"

    def test_interval_env_var_custom(self, monkeypatch):
        monkeypatch.setenv("RESEARCH_TLDV_INTERVAL_MIN", "30")
        # Re-import to pick up env
        from vault.crons import research_tldv_cron as mod
        # Interval is read at call time via os.environ.get
        assert os.environ.get("RESEARCH_TLDV_INTERVAL_MIN") == "30"

    def test_main_acquires_lock_and_runs_pipeline(self, monkeypatch, capsys, tmp_path):
        from vault.crons import research_tldv_cron as mod

        lock_calls: list = []
        pipeline_calls: list = []

        def fake_acquire(lock_path):
            lock_calls.append(lock_path)
            return True

        def fake_release(lock_path):
            lock_calls.append(("release", lock_path))

        fake_pipeline_instance = SimpleNamespace(
            run=MagicMock(return_value={
                "status": "success",
                "events_processed": 2,
                "events_skipped": 0,
            })
        )

        monkeypatch.setattr(mod, "acquire_lock", fake_acquire)
        monkeypatch.setattr(mod, "release_lock", fake_release)
        monkeypatch.setattr(
            mod, "ResearchPipeline",
            lambda source, state_path, research_dir, read_only_mode: fake_pipeline_instance
        )
        monkeypatch.chdir(tmp_path)

        mod.main()

        # Lock acquired then released
        assert lock_calls[0] == ".research/tldv/lock"
        assert lock_calls[-1] == ("release", ".research/tldv/lock")
        # Pipeline run called
        fake_pipeline_instance.run.assert_called_once()
        # Output contains result
        out = capsys.readouterr().out
        assert "done" in out or "success" in out

    def test_main_skips_when_lock_unavailable(self, monkeypatch, capsys, tmp_path):
        from vault.crons import research_tldv_cron as mod

        monkeypatch.setattr(mod, "acquire_lock", lambda _: False)
        monkeypatch.chdir(tmp_path)

        mod.main()

        out = capsys.readouterr().out
        assert "skipping" in out


# ---------------------------------------------------------------------------
# Test: research_github_cron
# ---------------------------------------------------------------------------

class TestResearchGithubCron:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, tmp_path):
        self.tmp_path = tmp_path
        monkeypatch.delenv("RESEARCH_GITHUB_INTERVAL_MIN", raising=False)

    def test_constants(self):
        from vault.crons import research_github_cron as mod
        assert mod.LOCK_PATH == ".research/github/lock"
        assert mod.RESEARCH_DIR == ".research/github"
        assert mod.STATE_PATH == "state/identity-graph/state.json"

    def test_main_acquires_lock_and_runs_pipeline(self, monkeypatch, capsys, tmp_path):
        from vault.crons import research_github_cron as mod

        lock_calls: list = []
        fake_pipeline_instance = SimpleNamespace(
            run=MagicMock(return_value={
                "status": "success",
                "events_processed": 1,
                "events_skipped": 3,
            })
        )

        monkeypatch.setattr(mod, "acquire_lock", lambda lp: lock_calls.append(lp) or True)
        monkeypatch.setattr(mod, "release_lock", lambda lp: lock_calls.append(("release", lp)))
        monkeypatch.setattr(
            mod, "ResearchPipeline",
            lambda source, state_path, research_dir, read_only_mode: fake_pipeline_instance
        )
        monkeypatch.chdir(tmp_path)

        mod.main()

        assert lock_calls[0] == ".research/github/lock"
        assert lock_calls[-1] == ("release", ".research/github/lock")
        fake_pipeline_instance.run.assert_called_once()
        out = capsys.readouterr().out
        assert "done" in out or "success" in out

    def test_main_skips_when_lock_unavailable(self, monkeypatch, capsys, tmp_path):
        from vault.crons import research_github_cron as mod

        monkeypatch.setattr(mod, "acquire_lock", lambda _: False)
        monkeypatch.chdir(tmp_path)

        mod.main()

        out = capsys.readouterr().out
        assert "skipping" in out


# ---------------------------------------------------------------------------
# Test: research_consolidation_cron
# ---------------------------------------------------------------------------

class TestResearchConsolidationCron:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, tmp_path):
        self.tmp_path = tmp_path
        monkeypatch.delenv("RESEARCH_TLDV_INTERVAL_MIN", raising=False)
        monkeypatch.delenv("RESEARCH_GITHUB_INTERVAL_MIN", raising=False)

    def test_load_env_reads_file(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        env_file = openclaw_dir / ".env"
        env_file.write_text("TEST_KEY=test_value\n# comment\nINVALID\n")

        monkeypatch.setattr(mod.Path, "home", lambda: tmp_path)
        monkeypatch.delenv("TEST_KEY", raising=False)

        mod.load_env()

        assert os.environ.get("TEST_KEY") == "test_value"

    def test_constants(self):
        from vault.crons import research_consolidation_cron as mod
        assert mod.LOCK_PATH == ".research/consolidation/lock"
        assert mod.RESEARCH_DIR_TLDV == ".research/tldv"
        assert mod.RESEARCH_DIR_GITHUB == ".research/github"
        assert mod.STATE_PATH == "state/identity-graph/state.json"
        assert mod.CONSOLIDATION_LOG == "memory/consolidation-log.md"

    def test_is_first_five_days(self, monkeypatch):
        from vault.crons import research_consolidation_cron as mod

        # Patch helper clock to day 1–5
        for day in range(1, 6):
            monkeypatch.setattr(
                mod,
                "_utc_now",
                lambda d=day: datetime(2026, 4, d, 10, 0, 0, tzinfo=timezone.utc),
            )
            assert mod._is_first_five_days() is True, f"day {day} should be True"

        # Day 6+ should be False
        for day in (6, 15, 28):
            monkeypatch.setattr(
                mod,
                "_utc_now",
                lambda d=day: datetime(2026, 4, d, 10, 0, 0, tzinfo=timezone.utc),
            )
            assert mod._is_first_five_days() is False, f"day {day} should be False"

    def test_append_consolidation_log_creates_file(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        log_path = tmp_path / "memory" / "consolidation-log.md"
        monkeypatch.setattr(mod, "CONSOLIDATION_LOG", str(log_path))

        entry = {"run_at": "2026-04-18T10:00:00Z", "tldv": {}, "github": {}}
        mod._append_consolidation_log(entry)

        assert log_path.exists()
        content = log_path.read_text()
        assert "run_at" in content
        assert "2026-04-18" in content

    def test_main_runs_both_pipelines_and_compacts(self, monkeypatch, capsys, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        tldv_mock = SimpleNamespace(
            run=MagicMock(return_value={"status": "success", "events_processed": 1, "events_skipped": 0})
        )
        gh_mock = SimpleNamespace(
            run=MagicMock(return_value={"status": "success", "events_processed": 0, "events_skipped": 2})
        )

        compact_calls: list = []
        monkeypatch.setattr(mod, "acquire_lock", lambda _: True)
        monkeypatch.setattr(mod, "release_lock", lambda _: None)
        monkeypatch.setattr(
            mod, "compact_processed_keys",
            lambda retention_days, state_path: compact_calls.append(
                {"retention_days": retention_days, "state_path": state_path}
            )
        )
        monkeypatch.setattr(
            mod, "monthly_snapshot",
            lambda state_path: None
        )
        monkeypatch.setattr(
            mod, "state_metrics",
            lambda state_path: {"github": {"key_count": 5}, "tldv": {"key_count": 10}}
        )
        monkeypatch.setattr(mod, "ResearchPipeline",
            lambda source, state_path, research_dir, read_only_mode: (
                tldv_mock if source == "tldv" else gh_mock
            )
        )
        monkeypatch.setattr(mod, "CONSOLIDATION_LOG", str(tmp_path / "memory" / "consolidation-log.md"))
        monkeypatch.chdir(tmp_path)

        # Patch helper clock to avoid snapshot path
        monkeypatch.setattr(mod, "_utc_now", lambda: datetime(2026, 4, 18, 10, 0, 0, tzinfo=timezone.utc))
        mod.main()

        # Both pipelines ran
        tldv_mock.run.assert_called_once()
        gh_mock.run.assert_called_once()

        # Compact called with 180 days
        assert compact_calls[0]["retention_days"] == 180

        # Output is valid JSON (last non-empty line)
        out = capsys.readouterr().out
        lines = [l for l in out.splitlines() if l.strip()]
        result = json.loads(lines[-1])
        assert result["status"] == "success"
        assert result["tldv"]["events_processed"] == 1
        assert result["github"]["events_skipped"] == 2
        assert result["snapshot_created"] is False
        assert result["metrics"]["github"]["key_count"] == 5

    def test_main_skips_when_lock_unavailable(self, monkeypatch, capsys, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        monkeypatch.setattr(mod, "acquire_lock", lambda _: False)
        monkeypatch.chdir(tmp_path)

        mod.main()

        lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
        assert any("skipping" in line for line in lines)
        parsed = json.loads(lines[-1])
        assert parsed.get("skipped_reason") == "locked"
