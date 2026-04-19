"""Tests for vault/research/self_healing.py — circuit breaker and metrics schema."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from vault.research.self_healing import (
    DEFAULT_BREAKER_METRICS,
    QUALITY_ERROR_THRESHOLD,
    REVERT_WINDOW,
    apply_decision,
    bump_breaker_error,
    bump_breaker_revert,
    bump_clean_run,
    get_breaker_mode,
    is_source_paused,
    load_breaker_metrics,
    record_apply,
    record_rollback,
    reset_breaker,
    save_breaker_metrics,
    transition_breaker,
    emit_breaker_transition,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_breaker_metrics(tmp_path):
    p = tmp_path / "self_healing_metrics.json"
    p.write_text(json.dumps(dict(DEFAULT_BREAKER_METRICS)))
    return p


@pytest.fixture()
def tmp_experiments_log(tmp_path):
    return tmp_path / "experiments.jsonl"


# ---------------------------------------------------------------------------
# DEFAULT_BREAKER_METRICS schema
# ---------------------------------------------------------------------------

def test_breaker_metrics_schema_has_all_required_fields():
    """Verify the default metrics schema contains all required fields."""
    required = {
        "mode",
        "paused_sources",
        "apply_count_by_source",
        "rollback_count_by_source",
        "revert_streak_by_source",
        "error_streak_by_source",
        "availability_error_by_source",
        "review_queue_size",
        "last_transition_at",
        "reason",
        "recent_run_outcomes_by_source",
    }
    assert required.issubset(DEFAULT_BREAKER_METRICS.keys()), (
        f"Missing fields: {required - set(DEFAULT_BREAKER_METRICS.keys())}"
    )


def test_breaker_metrics_mode_is_valid_value():
    """mode must be one of 'monitoring', 'write_paused', 'global_paused'."""
    valid_modes = {"monitoring", "write_paused", "global_paused"}
    assert DEFAULT_BREAKER_METRICS["mode"] in valid_modes


def test_breaker_metrics_paused_sources_is_list():
    """paused_sources must be a list."""
    assert isinstance(DEFAULT_BREAKER_METRICS["paused_sources"], list)


def test_breaker_metrics_apply_count_by_source_is_dict():
    """apply_count_by_source must be a dict."""
    assert isinstance(DEFAULT_BREAKER_METRICS["apply_count_by_source"], dict)


def test_breaker_metrics_rollback_count_by_source_is_dict():
    """rollback_count_by_source must be a dict."""
    assert isinstance(DEFAULT_BREAKER_METRICS["rollback_count_by_source"], dict)


def test_breaker_metrics_revert_streak_is_dict():
    """revert_streak_by_source must be a dict (separate from error_streak)."""
    assert isinstance(DEFAULT_BREAKER_METRICS["revert_streak_by_source"], dict)


def test_breaker_metrics_error_streak_is_dict():
    """error_streak_by_source must be a dict (separate from revert_streak)."""
    assert isinstance(DEFAULT_BREAKER_METRICS["error_streak_by_source"], dict)


def test_breaker_metrics_availability_error_is_dict():
    """availability_error_by_source must be a dict."""
    assert isinstance(DEFAULT_BREAKER_METRICS["availability_error_by_source"], dict)


def test_breaker_metrics_review_queue_size_is_int():
    """review_queue_size must be an int."""
    assert isinstance(DEFAULT_BREAKER_METRICS["review_queue_size"], int)


def test_breaker_metrics_last_transition_at_is_none():
    """last_transition_at starts as None."""
    assert DEFAULT_BREAKER_METRICS["last_transition_at"] is None


def test_breaker_metrics_reason_is_string():
    """reason must be a string."""
    assert isinstance(DEFAULT_BREAKER_METRICS["reason"], str)


# ---------------------------------------------------------------------------
# load_breaker_metrics / save_breaker_metrics
# ---------------------------------------------------------------------------

def test_load_breaker_metrics_returns_defaults(tmp_path):
    """Missing file returns default schema."""
    path = tmp_path / "metrics.json"
    metrics = load_breaker_metrics(path)
    assert metrics["mode"] == "monitoring"
    assert metrics["paused_sources"] == []


def test_load_breaker_metrics_merges_with_defaults(tmp_path):
    """Partial file is merged with defaults."""
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps({"mode": "write_paused", "paused_sources": ["github"]}))
    metrics = load_breaker_metrics(path)
    assert metrics["mode"] == "write_paused"
    assert metrics["paused_sources"] == ["github"]
    # Defaults preserved
    assert metrics["apply_count_by_source"] == {}


def test_save_breaker_metrics_creates_file(tmp_path):
    """save_breaker_metrics creates the file and parent directories."""
    path = tmp_path / "sub" / "self_healing_metrics.json"
    save_breaker_metrics({"mode": "global_paused"}, path)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["mode"] == "global_paused"


# ---------------------------------------------------------------------------
# is_source_paused
# ---------------------------------------------------------------------------

def test_is_source_paused_true_when_in_paused_sources(tmp_breaker_metrics):
    """A source in paused_sources returns True."""
    save_breaker_metrics({"mode": "write_paused", "paused_sources": ["github"]}, tmp_breaker_metrics)
    assert is_source_paused("github", tmp_breaker_metrics) is True


def test_is_source_paused_false_when_not_in_list(tmp_breaker_metrics):
    """A source not in paused_sources returns False."""
    save_breaker_metrics({"mode": "write_paused", "paused_sources": ["github"]}, tmp_breaker_metrics)
    assert is_source_paused("tldv", tmp_breaker_metrics) is False


def test_is_source_paused_false_when_global_paused(tmp_breaker_metrics):
    """When mode is global_paused, all sources are paused."""
    save_breaker_metrics({"mode": "global_paused", "paused_sources": []}, tmp_breaker_metrics)
    assert is_source_paused("github", tmp_breaker_metrics) is True
    assert is_source_paused("tldv", tmp_breaker_metrics) is True


# ---------------------------------------------------------------------------
# get_breaker_mode
# ---------------------------------------------------------------------------

def test_get_breaker_mode_returns_current_mode(tmp_breaker_metrics):
    """Returns the current breaker mode string."""
    save_breaker_metrics({"mode": "monitoring"}, tmp_breaker_metrics)
    assert get_breaker_mode(tmp_breaker_metrics) == "monitoring"


# ---------------------------------------------------------------------------
# bump_breaker_error — quality error increments error_streak
# ---------------------------------------------------------------------------

def test_bump_breaker_error_increments_error_streak(tmp_breaker_metrics):
    """Quality error increments error_streak for the source."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    bump_breaker_error("github", "quality", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["error_streak_by_source"]["github"] == 1


def test_bump_breaker_error_does_not_affect_revert_streak(tmp_breaker_metrics):
    """Quality error does NOT touch revert_streak."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    bump_breaker_error("github", "quality", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["revert_streak_by_source"].get("github", 0) == 0


def test_bump_breaker_error_resets_error_streak_on_availability(tmp_breaker_metrics):
    """Availability error resets error_streak for that source."""
    save_breaker_metrics({
        **DEFAULT_BREAKER_METRICS,
        "error_streak_by_source": {"github": 2},
    }, tmp_breaker_metrics)
    bump_breaker_error("github", "availability", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["error_streak_by_source"]["github"] == 0
    assert metrics["availability_error_by_source"]["github"] == 1


# ---------------------------------------------------------------------------
# bump_breaker_revert — increments revert_streak
# ---------------------------------------------------------------------------

def test_bump_breaker_revert_increments_revert_streak(tmp_breaker_metrics):
    """Revert increments revert_streak for the source."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    bump_breaker_revert("github", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["revert_streak_by_source"]["github"] == 1


def test_bump_breaker_revert_does_not_affect_error_streak(tmp_breaker_metrics):
    """Revert does NOT touch error_streak."""
    save_breaker_metrics({
        **DEFAULT_BREAKER_METRICS,
        "error_streak_by_source": {"github": 2},
    }, tmp_breaker_metrics)
    bump_breaker_revert("github", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["error_streak_by_source"]["github"] == 2


# ---------------------------------------------------------------------------
# bump_clean_run — resets both streaks for source
# ---------------------------------------------------------------------------

def test_bump_clean_run_resets_error_streak(tmp_breaker_metrics):
    """Clean run resets error_streak for the source."""
    save_breaker_metrics({
        **DEFAULT_BREAKER_METRICS,
        "error_streak_by_source": {"github": 2},
    }, tmp_breaker_metrics)
    bump_clean_run("github", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["error_streak_by_source"].get("github", 0) == 0


def test_bump_clean_run_resets_revert_streak(tmp_breaker_metrics):
    """Clean run resets revert_streak for the source."""
    save_breaker_metrics({
        **DEFAULT_BREAKER_METRICS,
        "revert_streak_by_source": {"github": 3},
    }, tmp_breaker_metrics)
    bump_clean_run("github", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["revert_streak_by_source"].get("github", 0) == 0


# ---------------------------------------------------------------------------
# record_apply — increments apply_count_by_source
# ---------------------------------------------------------------------------

def test_record_apply_increments_apply_count(tmp_breaker_metrics):
    """record_apply bumps the per-source apply counter."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    record_apply("github", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["apply_count_by_source"]["github"] == 1


# ---------------------------------------------------------------------------
# record_rollback — increments rollback_count_by_source
# ---------------------------------------------------------------------------

def test_record_rollback_increments_rollback_count(tmp_breaker_metrics):
    """record_rollback bumps the per-source rollback counter."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    record_rollback("github", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["rollback_count_by_source"]["github"] == 1


# ---------------------------------------------------------------------------
# transition_breaker — state machine
# ---------------------------------------------------------------------------

def test_transition_breaker_3_quality_errors_triggers_source_pause(tmp_breaker_metrics, tmp_experiments_log):
    """3 consecutive quality errors on a source → mode=write_paused, source in paused_sources."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    for _ in range(3):
        bump_breaker_error("github", "quality", tmp_breaker_metrics)
    transition_breaker("github", "quality_error", tmp_breaker_metrics, experiments_log=tmp_experiments_log)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["mode"] == "write_paused"
    assert "github" in metrics["paused_sources"]
    assert metrics["last_transition_at"] is not None


def test_transition_breaker_5_reverts_in_10_triggers_global_pause(tmp_breaker_metrics, tmp_experiments_log):
    """5 reverts in the last 10 runs → mode=global_paused."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    # Build a 10-run window for github with exactly 5 reverts
    for _ in range(5):
        bump_breaker_revert("github", tmp_breaker_metrics)
    for _ in range(5):
        bump_clean_run("github", tmp_breaker_metrics)
    transition_breaker("github", "revert_storm", tmp_breaker_metrics, experiments_log=tmp_experiments_log)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["mode"] == "global_paused"


def test_transition_breaker_reverts_outside_window_do_not_pause(tmp_breaker_metrics, tmp_experiments_log):
    """If only 4 of last 10 are reverts, must not global pause."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    # 5 reverts happened, but then enough clean runs push one revert out of window
    for _ in range(5):
        bump_breaker_revert("github", tmp_breaker_metrics)
    for _ in range(6):
        bump_clean_run("github", tmp_breaker_metrics)
    transition_breaker("github", "window_check", tmp_breaker_metrics, experiments_log=tmp_experiments_log)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["mode"] != "global_paused"


def test_bump_breaker_revert_keeps_only_last_revert_window(tmp_breaker_metrics):
    """Recent run outcomes are bounded to REVERT_WINDOW entries per source."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    for _ in range(REVERT_WINDOW + 3):
        bump_breaker_revert("github", tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    outcomes = metrics["recent_run_outcomes_by_source"]["github"]
    assert len(outcomes) == REVERT_WINDOW


def test_transition_breaker_3_clean_runs_resets_source_pause(tmp_breaker_metrics, tmp_experiments_log):
    """3 consecutive clean runs with outcomes in window → source removed from paused_sources."""
    save_breaker_metrics({
        **DEFAULT_BREAKER_METRICS,
        "mode": "write_paused",
        "paused_sources": ["github"],
        "error_streak_by_source": {"github": 0},
        "revert_streak_by_source": {"github": 0},
        "recent_run_outcomes_by_source": {"github": ["error", "error", "error"]},  # pre-window
    }, tmp_breaker_metrics)
    # Now 3 clean runs — the window will have exactly 3 clean runs
    for _ in range(3):
        bump_clean_run("github", tmp_breaker_metrics)
    transition_breaker("github", "clean_runs", tmp_breaker_metrics, experiments_log=tmp_experiments_log)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["mode"] == "monitoring"
    assert "github" not in metrics["paused_sources"]


def test_transition_breaker_sets_reason(tmp_breaker_metrics, tmp_experiments_log):
    """transition records the human-readable reason."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    # Bump errors to hit threshold so a transition fires
    for _ in range(QUALITY_ERROR_THRESHOLD):
        bump_breaker_error("github", "quality", tmp_breaker_metrics)
    transition_breaker("github", "quality_error", tmp_breaker_metrics, experiments_log=tmp_experiments_log)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["reason"] == "quality_error"


def test_transition_breaker_sets_last_transition_at(tmp_breaker_metrics, tmp_experiments_log):
    """last_transition_at is set to current ISO timestamp."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    # Bump errors to hit threshold so a transition fires
    for _ in range(QUALITY_ERROR_THRESHOLD):
        bump_breaker_error("github", "quality", tmp_breaker_metrics)
    transition_breaker("github", "quality_error", tmp_breaker_metrics, experiments_log=tmp_experiments_log)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["last_transition_at"] is not None
    # Valid ISO string
    from datetime import datetime
    datetime.fromisoformat(metrics["last_transition_at"])


# ---------------------------------------------------------------------------
# emit_breaker_transition — writes to experiments.jsonl
# ---------------------------------------------------------------------------

def test_emit_breaker_transition_writes_jsonl(tmp_breaker_metrics, tmp_experiments_log):
    """Every transition emits a JSONL line to vault/logs/experiments.jsonl."""
    emit_breaker_transition(
        source="github",
        breaker_mode="write_paused",
        decision="source_pause",
        reason="3 consecutive quality errors",
        experiments_log=tmp_experiments_log,
    )
    assert tmp_experiments_log.exists()
    lines = tmp_experiments_log.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["source"] == "github"
    assert record["breaker_mode"] == "write_paused"
    assert record["decision"] == "source_pause"
    assert "timestamp" in record
    assert record["event_type"] == "breaker_transition"


def test_emit_breaker_transition_append_only(tmp_breaker_metrics, tmp_experiments_log):
    """Multiple calls append, never overwrite."""
    emit_breaker_transition("github", "monitoring", "clean", "test", tmp_experiments_log)
    emit_breaker_transition("tldv", "write_paused", "source_pause", "test", tmp_experiments_log)
    lines = tmp_experiments_log.read_text().strip().splitlines()
    assert len(lines) == 2


# ---------------------------------------------------------------------------
# reset_breaker
# ---------------------------------------------------------------------------

def test_reset_breaker_returns_to_monitoring(tmp_breaker_metrics):
    """reset_breaker restores default state (monitoring, empty lists/dicts)."""
    save_breaker_metrics({
        **DEFAULT_BREAKER_METRICS,
        "mode": "global_paused",
        "paused_sources": ["github", "tldv"],
        "apply_count_by_source": {"github": 10},
        "error_streak_by_source": {"github": 3},
    }, tmp_breaker_metrics)
    reset_breaker(tmp_breaker_metrics)
    metrics = load_breaker_metrics(tmp_breaker_metrics)
    assert metrics["mode"] == "monitoring"
    assert metrics["paused_sources"] == []
    assert metrics["apply_count_by_source"] == {}


# ---------------------------------------------------------------------------
# Integration: breaker gates apply_decision
# ---------------------------------------------------------------------------

def test_apply_decision_blocked_when_source_paused(tmp_breaker_metrics):
    """apply_decision returns skipped when source is in paused_sources."""
    save_breaker_metrics({
        **DEFAULT_BREAKER_METRICS,
        "mode": "write_paused",
        "paused_sources": ["github"],
    }, tmp_breaker_metrics)
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.95,
        source="github",
        breaker_metrics_path=tmp_breaker_metrics,
    )
    assert result["decision"] == "skipped"
    assert "paused" in result["reason"]


def test_apply_decision_blocked_when_global_paused(tmp_breaker_metrics):
    """apply_decision returns skipped when mode is global_paused."""
    save_breaker_metrics({
        **DEFAULT_BREAKER_METRICS,
        "mode": "global_paused",
        "paused_sources": [],
    }, tmp_breaker_metrics)
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.95,
        source="tldv",
        breaker_metrics_path=tmp_breaker_metrics,
    )
    assert result["decision"] == "skipped"
    assert "global_paused" in result["reason"]


def test_apply_decision_allowed_when_monitoring(tmp_breaker_metrics):
    """apply_decision proceeds normally when mode is monitoring."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), tmp_breaker_metrics)
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.95,
        source="github",
        breaker_metrics_path=tmp_breaker_metrics,
    )
    assert result["decision"] == "applied"
