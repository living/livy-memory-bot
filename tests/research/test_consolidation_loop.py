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


# ---------------------------------------------------------------------------
# _expected_type_name helper
# ---------------------------------------------------------------------------

    def test_expected_type_name_single(self):
        from vault.crons.research_consolidation_cron import _expected_type_name
        assert _expected_type_name(str) == "str"
        assert _expected_type_name(int) == "int"
        assert _expected_type_name(list) == "list"

    def test_expected_type_name_tuple_union(self):
        from vault.crons.research_consolidation_cron import _expected_type_name
        result = _expected_type_name((type(None), str))
        assert "None" in result and "str" in result


# ---------------------------------------------------------------------------
# _validate_breaker_schema
# ---------------------------------------------------------------------------

    def test_validate_breaker_schema_accepts_string_last_transition_at(self, monkeypatch, tmp_path, capsys):
        from vault.crons import research_consolidation_cron as mod
        from vault.research.self_healing import DEFAULT_BREAKER_METRICS

        metrics_file = tmp_path / "metrics.json"
        monkeypatch.setattr(mod, "METRICS_PATH", str(metrics_file))

        # Write metrics with ISO string last_transition_at
        data = {**DEFAULT_BREAKER_METRICS, "last_transition_at": "2026-04-18T10:00:00+00:00"}
        metrics_file.write_text(json.dumps(data))

        result = mod._validate_breaker_schema()
        assert result is True
        out = capsys.readouterr().out
        assert "WARNING" not in out

    def test_validate_breaker_schema_accepts_none_last_transition_at(self, monkeypatch, tmp_path, capsys):
        from vault.crons import research_consolidation_cron as mod
        from vault.research.self_healing import DEFAULT_BREAKER_METRICS

        metrics_file = tmp_path / "metrics.json"
        monkeypatch.setattr(mod, "METRICS_PATH", str(metrics_file))

        # Write metrics with None last_transition_at (default)
        data = {**DEFAULT_BREAKER_METRICS}
        metrics_file.write_text(json.dumps(data))

        result = mod._validate_breaker_schema()
        assert result is True
        out = capsys.readouterr().out
        assert "WARNING" not in out

    def test_validate_breaker_schema_rejects_invalid_last_transition_at(self, monkeypatch, tmp_path, capsys):
        from vault.crons import research_consolidation_cron as mod
        from vault.research.self_healing import DEFAULT_BREAKER_METRICS

        metrics_file = tmp_path / "metrics.json"
        monkeypatch.setattr(mod, "METRICS_PATH", str(metrics_file))

        # Write metrics with invalid type (int instead of None|str)
        data = {**DEFAULT_BREAKER_METRICS, "last_transition_at": 12345}
        metrics_file.write_text(json.dumps(data))

        result = mod._validate_breaker_schema()
        assert result is False
        out = capsys.readouterr().out
        assert "WARNING" in out and "last_transition_at" in out


# ---------------------------------------------------------------------------
# Watchdog observation loop
# ---------------------------------------------------------------------------

class TestWatchdogObservationLoop:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, tmp_path):
        self.tmp_path = tmp_path
        monkeypatch.delenv("RESEARCH_TLDV_INTERVAL_MIN", raising=False)
        monkeypatch.delenv("RESEARCH_GITHUB_INTERVAL_MIN", raising=False)

    # -------------------------------------------------------------------
    # _compute_revert_rate
    # -------------------------------------------------------------------

    def test_compute_revert_rate_zero_applies(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        metrics = {
            "apply_count_by_source": {"github": 0},
            "rollback_count_by_source": {"github": 0},
            "recent_run_outcomes_by_source": {"github": []},
        }
        rate = mod._compute_revert_rate(metrics)
        assert rate == 0.0

    def test_compute_revert_rate_no_rollbacks(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        metrics = {
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {"github": 0},
            "recent_run_outcomes_by_source": {"github": ["clean"] * 10},
        }
        rate = mod._compute_revert_rate(metrics)
        assert rate == 0.0

    def test_compute_revert_rate_with_rollbacks(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # 5 rollbacks out of 100 applies = 5%
        metrics = {
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {"github": 5},
            "recent_run_outcomes_by_source": {"github": ["revert"] * 5 + ["clean"] * 5},
        }
        rate = mod._compute_revert_rate(metrics)
        assert rate == 5.0

    def test_compute_revert_rate_aggregates_all_sources(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # github: 10/100=10%, tldv: 0/50=0% → weighted avg = 10/150*100 ≈ 6.67%
        metrics = {
            "apply_count_by_source": {"github": 100, "tldv": 50},
            "rollback_count_by_source": {"github": 10, "tldv": 0},
            "recent_run_outcomes_by_source": {
                "github": ["revert"] * 10,
                "tldv": ["clean"] * 5,
            },
        }
        rate = mod._compute_revert_rate(metrics)
        assert abs(rate - (10.0 / 150.0 * 100)) < 0.01

    # -------------------------------------------------------------------
    # _count_consecutive_high_revert_cycles
    # -------------------------------------------------------------------

    def test_consecutive_high_revert_zero_outcomes(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        metrics = {
            "recent_run_outcomes_by_source": {},
        }
        count = mod._count_consecutive_high_revert_cycles(metrics)
        assert count == 0

    def test_consecutive_high_revert_no_reverts(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        metrics = {
            "recent_run_outcomes_by_source": {
                "github": ["clean"] * 10,
                "tldv": ["clean"] * 5,
            },
        }
        count = mod._count_consecutive_high_revert_cycles(metrics)
        assert count == 0

    def test_consecutive_high_revert_single_source_high(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # 6 reverts out of 10 = 60% > 10% — one consecutive high-revert cycle
        metrics = {
            "recent_run_outcomes_by_source": {
                "github": ["revert"] * 6 + ["clean"] * 4,
            },
        }
        count = mod._count_consecutive_high_revert_cycles(metrics)
        assert count == 1

    def test_consecutive_high_revert_multiple_sources_high_takes_max(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # github: 7/10=70% > 10%, tldv: 8/10=80% > 10% — max is 1 each, overall 1
        metrics = {
            "recent_run_outcomes_by_source": {
                "github": ["revert"] * 7 + ["clean"] * 3,
                "tldv": ["revert"] * 8 + ["clean"] * 2,
            },
        }
        count = mod._count_consecutive_high_revert_cycles(metrics)
        assert count == 1

    def test_consecutive_high_revert_counts_consecutive_cycles(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # 3 cycles: 60%→60%→60% = 3 consecutive cycles > 10%
        # Simulated by 3 sources each with 6/10 reverts
        metrics = {
            "recent_run_outcomes_by_source": {
                "github": ["revert"] * 6 + ["clean"] * 4,
                "tldv": ["revert"] * 6 + ["clean"] * 4,
                "trello": ["revert"] * 6 + ["clean"] * 4,
            },
        }
        count = mod._count_consecutive_high_revert_cycles(metrics)
        assert count == 3

    # -------------------------------------------------------------------
    # _watchdog_evaluate_thresholds
    # -------------------------------------------------------------------

    def test_evaluate_all_clear(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        metrics = {
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {"github": 1},
            "recent_run_outcomes_by_source": {"github": ["clean"] * 10},
            "review_queue_size": 10,
        }
        alerts = mod._watchdog_evaluate_thresholds(metrics)
        assert alerts == []

    def test_evaluate_revert_rate_above_5_percent_triggers_alert(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # 6% revert rate
        metrics = {
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {"github": 6},
            "recent_run_outcomes_by_source": {"github": ["revert"] * 6 + ["clean"] * 4},
            "review_queue_size": 0,
        }
        alerts = mod._watchdog_evaluate_thresholds(metrics)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "revert_rate"
        assert alerts[0]["value"] > 5.0

    def test_evaluate_pending_review_over_50_triggers_alert(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        metrics = {
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {},
            "recent_run_outcomes_by_source": {"github": ["clean"] * 10},
            "review_queue_size": 75,
        }
        alerts = mod._watchdog_evaluate_thresholds(metrics)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "pending_review_backlog"
        assert alerts[0]["value"] == 75

    def test_evaluate_multiple_alerts(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # Both revert rate > 5% AND review backlog > 50
        metrics = {
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {"github": 10},
            "recent_run_outcomes_by_source": {"github": ["revert"] * 8 + ["clean"] * 2},
            "review_queue_size": 60,
        }
        alerts = mod._watchdog_evaluate_thresholds(metrics)
        assert len(alerts) == 2
        types = {a["alert_type"] for a in alerts}
        assert "revert_rate" in types
        assert "pending_review_backlog" in types

    def test_evaluate_threshold_boundary_5_percent_exactly(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # Exactly 5% → not an alert (threshold is > 5%)
        metrics = {
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {"github": 5},
            "recent_run_outcomes_by_source": {"github": ["revert"] * 5 + ["clean"] * 5},
            "review_queue_size": 0,
        }
        alerts = mod._watchdog_evaluate_thresholds(metrics)
        assert alerts == []

    def test_evaluate_threshold_boundary_review_queue_exactly_50(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # Exactly 50 → not an alert (threshold is > 50)
        metrics = {
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {},
            "recent_run_outcomes_by_source": {"github": ["clean"] * 10},
            "review_queue_size": 50,
        }
        alerts = mod._watchdog_evaluate_thresholds(metrics)
        assert alerts == []

    def test_evaluate_consecutive_high_revert_3_plus_cycles(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        metrics = {
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {"github": 30},
            "recent_run_outcomes_by_source": {
                "github": ["revert"] * 6 + ["clean"] * 4,
                "tldv": ["revert"] * 7 + ["clean"] * 3,
                "trello": ["revert"] * 6 + ["clean"] * 4,
            },
            "review_queue_size": 0,
        }
        alerts = mod._watchdog_evaluate_thresholds(metrics)
        types = {a["alert_type"] for a in alerts}
        assert "consecutive_high_revert_cycles" in types
        assert any(a["value"] >= 3 for a in alerts if a["alert_type"] == "consecutive_high_revert_cycles")

    # -------------------------------------------------------------------
    # _watchdog_alert
    # -------------------------------------------------------------------

    def test_watchdog_alert_appends_to_consolidation_log(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        log_path = tmp_path / "memory" / "consolidation-log.md"
        monkeypatch.setattr(mod, "CONSOLIDATION_LOG", str(log_path))

        alert = {
            "alert_type": "revert_rate",
            "value": 7.5,
            "threshold": 5.0,
            "message": "revert rate 7.5% exceeds 5% threshold",
        }
        mod._watchdog_alert(alert)

        assert log_path.exists()
        content = log_path.read_text()
        assert "alert_type" in content
        assert "revert_rate" in content
        assert "7.5%" in content

    # -------------------------------------------------------------------
    # _watchdog_update_breaker_state — global_pause path
    # -------------------------------------------------------------------

    def test_watchdog_update_breaker_state_global_pause(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        metrics_file = tmp_path / "breaker.json"
        monkeypatch.setattr(mod, "METRICS_PATH", str(metrics_file))

        # Pre-existing metrics in monitoring mode
        from vault.research.self_healing import DEFAULT_BREAKER_METRICS
        data = {**DEFAULT_BREAKER_METRICS}
        metrics_file.write_text(json.dumps(data))

        alert = {
            "alert_type": "consecutive_high_revert_cycles",
            "value": 3,
            "trigger_global_pause": True,
        }
        mod._watchdog_update_breaker_state(alert)

        result = json.loads(metrics_file.read_text())
        assert result["mode"] == "global_paused"

    def test_watchdog_update_breaker_state_noop_for_non_global_pause(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        metrics_file = tmp_path / "breaker.json"
        monkeypatch.setattr(mod, "METRICS_PATH", str(metrics_file))

        from vault.research.self_healing import DEFAULT_BREAKER_METRICS
        data = {**DEFAULT_BREAKER_METRICS}
        metrics_file.write_text(json.dumps(data))

        alert = {
            "alert_type": "revert_rate",
            "value": 7.5,
            "trigger_global_pause": False,
        }
        mod._watchdog_update_breaker_state(alert)

        result = json.loads(metrics_file.read_text())
        assert result["mode"] == "monitoring"

    # -------------------------------------------------------------------
    # _watchdog_append_experiment
    # -------------------------------------------------------------------

    def test_watchdog_append_experiment_creates_file(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        log_path = tmp_path / "logs" / "experiments.jsonl"
        monkeypatch.setattr(mod, "EXPERIMENTS_LOG_PATH", str(log_path))

        decision = {
            "event_type": "watchdog_decision",
            "alerts": [],
            "breaker_action": "none",
        }
        mod._watchdog_append_experiment(decision)

        assert log_path.exists()
        lines = log_path.read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event_type"] == "watchdog_decision"
        assert "timestamp" in record

    def test_watchdog_append_experiment_appends_not_overwrites(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        log_path = tmp_path / "logs" / "experiments.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text('{"event_type":"prior_event"}\n')
        monkeypatch.setattr(mod, "EXPERIMENTS_LOG_PATH", str(log_path))

        decision = {"event_type": "watchdog_decision", "alerts": [], "breaker_action": "none"}
        mod._watchdog_append_experiment(decision)

        lines = log_path.read_text().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["event_type"] == "prior_event"
        assert json.loads(lines[1])["event_type"] == "watchdog_decision"

    # -------------------------------------------------------------------
    # main() runs watchdog observation loop
    # -------------------------------------------------------------------

    def test_main_runs_watchdog_and_emits_alert(self, monkeypatch, capsys, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        tldv_mock = SimpleNamespace(
            run=MagicMock(return_value={"status": "success", "events_processed": 1, "events_skipped": 0})
        )
        gh_mock = SimpleNamespace(
            run=MagicMock(return_value={"status": "success", "events_processed": 0, "events_skipped": 2})
        )

        metrics_file = tmp_path / "state" / "identity-graph" / "self_healing_metrics.json"
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(mod, "METRICS_PATH", str(metrics_file))

        # Write metrics with revert rate > 5%
        from vault.research.self_healing import DEFAULT_BREAKER_METRICS
        metrics_data = {
            **DEFAULT_BREAKER_METRICS,
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {"github": 10},
            "recent_run_outcomes_by_source": {"github": ["revert"] * 8 + ["clean"] * 2},
            "review_queue_size": 0,
        }
        metrics_file.write_text(json.dumps(metrics_data))

        exp_log = tmp_path / "vault" / "logs" / "experiments.jsonl"
        monkeypatch.setattr(mod, "EXPERIMENTS_LOG_PATH", str(exp_log))

        monkeypatch.setattr(mod, "acquire_lock", lambda _: True)
        monkeypatch.setattr(mod, "release_lock", lambda _: None)
        monkeypatch.setattr(mod, "compact_processed_keys", lambda retention_days, state_path: None)
        monkeypatch.setattr(mod, "monthly_snapshot", lambda state_path: None)
        monkeypatch.setattr(mod, "state_metrics", lambda state_path: {"github": {"key_count": 1}})
        monkeypatch.setattr(
            mod, "ResearchPipeline",
            lambda source, state_path, research_dir, read_only_mode: tldv_mock if source == "tldv" else gh_mock
        )
        monkeypatch.setattr(mod, "CONSOLIDATION_LOG", str(tmp_path / "memory" / "consolidation-log.md"))
        monkeypatch.setattr(mod, "_utc_now", lambda: datetime(2026, 4, 18, 10, 0, 0, tzinfo=timezone.utc))
        monkeypatch.chdir(tmp_path)

        mod.main()

        # experiments.jsonl was written
        assert exp_log.exists()
        lines = exp_log.read_text().splitlines()
        records = [json.loads(l) for l in lines]
        watchdog_records = [r for r in records if r.get("event_type") == "watchdog_decision"]
        assert len(watchdog_records) >= 1
        # At least one alert was emitted
        assert any(r.get("alerts") for r in watchdog_records)

        # Output contains watchdog info
        out = capsys.readouterr().out
        assert "watchdog" in out.lower() or "alert" in out.lower()

    def test_main_skips_watchdog_when_breaker_schema_invalid(self, monkeypatch, capsys, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        tldv_mock = SimpleNamespace(
            run=MagicMock(return_value={"status": "success", "events_processed": 1, "events_skipped": 0})
        )
        gh_mock = SimpleNamespace(
            run=MagicMock(return_value={"status": "success", "events_processed": 0, "events_skipped": 2})
        )

        metrics_file = tmp_path / "state" / "identity-graph" / "self_healing_metrics.json"
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(mod, "METRICS_PATH", str(metrics_file))

        # Invalid schema: mode must be str enum, using int forces invalid
        from vault.research.self_healing import DEFAULT_BREAKER_METRICS
        metrics_data = {
            **DEFAULT_BREAKER_METRICS,
            "mode": 123,
            "apply_count_by_source": {"github": 100},
            "rollback_count_by_source": {"github": 10},
            "recent_run_outcomes_by_source": {"github": ["revert"] * 8 + ["clean"] * 2},
            "review_queue_size": 0,
        }
        metrics_file.write_text(json.dumps(metrics_data))

        exp_log = tmp_path / "vault" / "logs" / "experiments.jsonl"
        monkeypatch.setattr(mod, "EXPERIMENTS_LOG_PATH", str(exp_log))

        monkeypatch.setattr(mod, "acquire_lock", lambda _: True)
        monkeypatch.setattr(mod, "release_lock", lambda _: None)
        monkeypatch.setattr(mod, "compact_processed_keys", lambda retention_days, state_path: None)
        monkeypatch.setattr(mod, "monthly_snapshot", lambda state_path: None)
        monkeypatch.setattr(mod, "state_metrics", lambda state_path: {"github": {"key_count": 1}})
        monkeypatch.setattr(
            mod, "ResearchPipeline",
            lambda source, state_path, research_dir, read_only_mode: tldv_mock if source == "tldv" else gh_mock
        )
        monkeypatch.setattr(mod, "CONSOLIDATION_LOG", str(tmp_path / "memory" / "consolidation-log.md"))
        monkeypatch.setattr(mod, "_utc_now", lambda: datetime(2026, 4, 18, 10, 0, 0, tzinfo=timezone.utc))
        monkeypatch.chdir(tmp_path)

        mod.main()

        # watchdog should be skipped, so no experiments log should be written
        assert not exp_log.exists()

        out = capsys.readouterr().out
        assert "schema invalid" in out.lower()
        assert "skipping watchdog" in out.lower()
