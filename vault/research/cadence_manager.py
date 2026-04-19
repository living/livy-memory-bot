"""Cadence state manager for research pipeline.

Persists per-source interval preference to state/identity-graph/cadence.json.
Hard floor: 4h. Escalation: 6h when budget exceeded.

Cadence state schema:
{
    "interval_hours": 4 | 6,
    "last_escalated_at": "<ISO timestamp or null>",
    "last_reduced_at": "<ISO timestamp or null>",
    "consecutive_budget_warnings": 0,
    "consecutive_healthy_runs": 0,
}
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path("state/identity-graph/cadence.json")
DEFAULT_INTERVAL_HOURS = 4
ESCALATED_INTERVAL_HOURS = 6
BUDGET_WARN_THRESHOLD = 3


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "interval_hours": DEFAULT_INTERVAL_HOURS,
        "last_escalated_at": None,
        "last_reduced_at": None,
        "consecutive_budget_warnings": 0,
        "consecutive_healthy_runs": 0,
    }


def load_cadence_state(state_path: Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    if not state_path.exists():
        return _default_state()
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_state()
        return data
    except (json.JSONDecodeError, OSError):
        return _default_state()


def save_cadence_state(state: dict[str, Any], state_path: Path = DEFAULT_STATE_PATH) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_interval_hours(state_path: Path = DEFAULT_STATE_PATH) -> int:
    state = load_cadence_state(state_path)
    return state.get("interval_hours", DEFAULT_INTERVAL_HOURS)


def record_budget_warning(state_path: Path = DEFAULT_STATE_PATH) -> None:
    """Call after a run that exceeded budget threshold. Escalates to 6h after 3 consecutive warnings."""
    state = load_cadence_state(state_path)
    state["consecutive_budget_warnings"] = state.get("consecutive_budget_warnings", 0) + 1
    state["consecutive_healthy_runs"] = 0

    if (
        state["consecutive_budget_warnings"] >= BUDGET_WARN_THRESHOLD
        and state.get("interval_hours", DEFAULT_INTERVAL_HOURS) == DEFAULT_INTERVAL_HOURS
    ):
        state["interval_hours"] = ESCALATED_INTERVAL_HOURS
        state["last_escalated_at"] = _iso_now()

    save_cadence_state(state, state_path)


def record_healthy_run(state_path: Path = DEFAULT_STATE_PATH) -> None:
    """Call after a run that stayed within budget. Reduces back to 4h after 3 consecutive healthy runs."""
    state = load_cadence_state(state_path)
    state["consecutive_healthy_runs"] = state.get("consecutive_healthy_runs", 0) + 1
    state["consecutive_budget_warnings"] = 0

    if (
        state.get("interval_hours", DEFAULT_INTERVAL_HOURS) == ESCALATED_INTERVAL_HOURS
        and state["consecutive_healthy_runs"] >= BUDGET_WARN_THRESHOLD
    ):
        state["interval_hours"] = DEFAULT_INTERVAL_HOURS
        state["last_reduced_at"] = _iso_now()
        state["consecutive_healthy_runs"] = 0

    save_cadence_state(state, state_path)
