"""Tests for vault/research/cadence_manager.py."""

from pathlib import Path

from vault.research.cadence_manager import (
    DEFAULT_INTERVAL_HOURS,
    ESCALATED_INTERVAL_HOURS,
    get_interval_hours,
    load_cadence_state,
    record_budget_warning,
    record_healthy_run,
)


def test_default_state_when_file_missing(tmp_path):
    state_path = tmp_path / "cadence.json"
    state = load_cadence_state(state_path)

    assert state["interval_hours"] == DEFAULT_INTERVAL_HOURS
    assert state["consecutive_budget_warnings"] == 0
    assert state["consecutive_healthy_runs"] == 0


def test_escalates_to_6h_after_3_budget_warnings(tmp_path):
    state_path = tmp_path / "cadence.json"

    record_budget_warning(state_path)
    record_budget_warning(state_path)
    assert get_interval_hours(state_path) == DEFAULT_INTERVAL_HOURS

    record_budget_warning(state_path)
    assert get_interval_hours(state_path) == ESCALATED_INTERVAL_HOURS

    state = load_cadence_state(state_path)
    assert state["last_escalated_at"] is not None


def test_reduces_back_to_4h_after_3_healthy_runs(tmp_path):
    state_path = tmp_path / "cadence.json"

    # Escalate first
    record_budget_warning(state_path)
    record_budget_warning(state_path)
    record_budget_warning(state_path)
    assert get_interval_hours(state_path) == ESCALATED_INTERVAL_HOURS

    # Three healthy runs reduce cadence
    record_healthy_run(state_path)
    record_healthy_run(state_path)
    assert get_interval_hours(state_path) == ESCALATED_INTERVAL_HOURS

    record_healthy_run(state_path)
    assert get_interval_hours(state_path) == DEFAULT_INTERVAL_HOURS

    state = load_cadence_state(state_path)
    assert state["last_reduced_at"] is not None
