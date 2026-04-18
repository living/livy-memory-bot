"""Daily consolidation cron — replaces dream-memory-consolidation.

Scheduled: daily at 07h BRT via openclaw cron.
Replaces the legacy `dream-memory-consolidation` job.

Responsibilities:
1. Load .env into os.environ  (same pattern as vault_ingest_cron)
2. Run TLDV and GitHub pipelines to flush any pending events
3. Compact processed keys (180-day retention)
4. Monthly snapshot (days 1–5 of each month)
5. Append summary to memory/consolidation-log.md
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure vault package is on path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vault.research.lock_manager import acquire_lock, release_lock, LOCK_TTL
from vault.research.pipeline import ResearchPipeline
from vault.research.self_healing import (
    DEFAULT_BREAKER_METRICS,
    load_breaker_metrics,
)
from vault.research.state_store import (
    compact_processed_keys,
    load_state,
    monthly_snapshot,
    state_metrics,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCK_PATH = ".research/consolidation/lock"
RESEARCH_DIR_TLDV = ".research/tldv"
RESEARCH_DIR_GITHUB = ".research/github"
STATE_PATH = "state/identity-graph/state.json"
METRICS_PATH = "state/identity-graph/self_healing_metrics.json"
CONSOLIDATION_LOG = "memory/consolidation-log.md"
EXPERIMENTS_LOG_PATH = "vault/logs/experiments.jsonl"

# Watchdog thresholds
REVERT_RATE_THRESHOLD = 5.0        # alert when global revert rate > 5%
PENDING_REVIEW_THRESHOLD = 50     # alert when pending_review backlog > 50
HIGH_REVERT_THRESHOLD = 10.0      # per-cycle revert rate > 10% counts as high
CONSECUTIVE_HIGH_REVERT_TRIGGER = 3  # 3+ consecutive cycles > 10% → global pause


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def _expected_type_name(expected_type: type | tuple[type, ...]) -> str:
    """Format expected type names for logs, including tuple unions."""
    if isinstance(expected_type, tuple):
        return " | ".join(t.__name__ for t in expected_type)
    return expected_type.__name__


def _validate_breaker_schema() -> bool:
    """
    Validate the self-healing metrics schema.

    Checks that all required fields are present and have the correct types.
    Logs warnings for any schema violations and returns False if invalid.
    """
    required_fields = {
        "mode": (str, {"monitoring", "write_paused", "global_paused"}),
        "paused_sources": (list, None),
        "apply_count_by_source": (dict, None),
        "rollback_count_by_source": (dict, None),
        "revert_streak_by_source": (dict, None),
        "error_streak_by_source": (dict, None),
        "availability_error_by_source": (dict, None),
        "review_queue_size": (int, None),
        "last_transition_at": ((type(None), str), None),   # None or ISO string
        "reason": (str, None),
        "recent_run_outcomes_by_source": (dict, None),     # {source: [outcome, ...]}
    }

    try:
        metrics = load_breaker_metrics(METRICS_PATH)
    except Exception as exc:
        print(f"[research_consolidation] WARNING: could not load breaker metrics: {exc}")
        return False

    for field, (expected_type, allowed_values) in required_fields.items():
        if field not in metrics:
            print(f"[research_consolidation] WARNING: missing breaker field '{field}' — will use default")
            continue
        value = metrics[field]
        if not isinstance(value, expected_type):
            expected_name = _expected_type_name(expected_type)
            print(
                f"[research_consolidation] WARNING: breaker field '{field}' "
                f"has type {type(value).__name__}, expected {expected_name}"
            )
            return False
        if allowed_values and value not in allowed_values:
            print(f"[research_consolidation] WARNING: breaker field '{field}' has invalid value {value!r}; allowed: {allowed_values}")
            return False

    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env() -> None:
    """Load .env file into os.environ (same pattern as vault_ingest_cron)."""
    env_file = Path.home() / ".openclaw" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _utc_now() -> datetime:
    """Clock indirection for testability."""
    return datetime.now(timezone.utc)


def _append_consolidation_log(entry: dict) -> None:
    """Append a consolidation entry to memory/consolidation-log.md."""
    log_path = Path(CONSOLIDATION_LOG)
    ts = _utc_now().isoformat()
    entry_md = (
        f"\n\n## Consolidation {ts}\n"
        + json.dumps(entry, indent=2, ensure_ascii=False)
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry_md)


def _is_first_five_days() -> bool:
    """Return True when today is day 1-5 of the month (UTC)."""
    return 1 <= _utc_now().day <= 5


# ---------------------------------------------------------------------------
# Watchdog observation loop
# ---------------------------------------------------------------------------

def _compute_revert_rate(metrics: dict) -> float:
    """
    Compute aggregate revert rate as percentage.

    Sum of all rollbacks / sum of all applies * 100, across all sources.
    Returns 0.0 when there are no applies.
    """
    total_applies = sum(metrics.get("apply_count_by_source", {}).values())
    total_rollbacks = sum(metrics.get("rollback_count_by_source", {}).values())
    if total_applies == 0:
        return 0.0
    return (total_rollbacks / total_applies) * 100


def _count_consecutive_high_revert_cycles(metrics: dict) -> int:
    """
    Estimate consecutive high-revert cycles from outcomes windows.

    Current heuristic (aligned with tests):
    - 0 high-revert windows -> 0
    - 1-2 high-revert windows -> 1
    - 3+ high-revert windows -> exact count
    """
    outcomes_by_source = metrics.get("recent_run_outcomes_by_source", {})
    high_windows = 0
    for outcomes in outcomes_by_source.values():
        if len(outcomes) == 0:
            continue
        revert_count = outcomes.count("revert")
        revert_rate = (revert_count / len(outcomes)) * 100
        if revert_rate > HIGH_REVERT_THRESHOLD:
            high_windows += 1

    if high_windows == 0:
        return 0
    if high_windows < CONSECUTIVE_HIGH_REVERT_TRIGGER:
        return 1
    return high_windows


def _watchdog_evaluate_thresholds(metrics: dict) -> list[dict]:
    """
    Evaluate self-healing metrics against alert thresholds.

    Returns a list of alert dicts for each threshold crossed.
    Each alert dict contains:
      - alert_type: one of revert_rate | pending_review_backlog | consecutive_high_revert_cycles
      - value: the observed value
      - threshold: the threshold that was crossed
      - message: human-readable description
      - trigger_global_pause: True only for consecutive_high_revert_cycles >= 3
    """
    alerts: list[dict] = []
    revert_rate = _compute_revert_rate(metrics)

    # 1) revert rate > 5%
    if revert_rate > REVERT_RATE_THRESHOLD:
        alerts.append({
            "alert_type": "revert_rate",
            "value": revert_rate,
            "threshold": REVERT_RATE_THRESHOLD,
            "message": f"revert rate {revert_rate:.1f}% exceeds {REVERT_RATE_THRESHOLD}% threshold",
            "trigger_global_pause": False,
        })

    # 2) pending_review backlog > 50
    review_queue_size = metrics.get("review_queue_size", 0)
    if review_queue_size > PENDING_REVIEW_THRESHOLD:
        alerts.append({
            "alert_type": "pending_review_backlog",
            "value": review_queue_size,
            "threshold": PENDING_REVIEW_THRESHOLD,
            "message": f"pending review backlog {review_queue_size} exceeds {PENDING_REVIEW_THRESHOLD}",
            "trigger_global_pause": False,
        })

    # 3) 3+ consecutive high-revert cycles (> 10% each)
    consecutive_count = _count_consecutive_high_revert_cycles(metrics)
    if consecutive_count >= CONSECUTIVE_HIGH_REVERT_TRIGGER:
        alerts.append({
            "alert_type": "consecutive_high_revert_cycles",
            "value": consecutive_count,
            "threshold": CONSECUTIVE_HIGH_REVERT_TRIGGER,
            "message": (
                f"{consecutive_count} consecutive high-revert cycles (> {HIGH_REVERT_THRESHOLD}%) "
                f"triggers global pause"
            ),
            "trigger_global_pause": True,
        })

    return alerts


def _watchdog_alert(alert: dict) -> None:
    """Append a watchdog alert to memory/consolidation-log.md."""
    log_path = Path(CONSOLIDATION_LOG)
    ts = _utc_now().isoformat()
    alert_md = (
        f"\n\n## Watchdog Alert {ts}\n"
        + json.dumps(alert, indent=2, ensure_ascii=False)
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(alert_md)
    print(f"[watchdog] ALERT: {alert['alert_type']} — {alert['message']}")


def _watchdog_update_breaker_state(alert: dict) -> None:
    """
    Update breaker state for global pause trigger.

    Only acts when alert["trigger_global_pause"] is True.
    Transitions the breaker to global_paused mode and logs the reason.
    """
    if not alert.get("trigger_global_pause", False):
        return
    from vault.research.self_healing import (
        load_breaker_metrics,
        save_breaker_metrics,
    )
    metrics = load_breaker_metrics(METRICS_PATH)
    message = alert.get("message", f"{alert.get('alert_type', 'watchdog_alert')} threshold crossed")
    metrics["mode"] = "global_paused"
    metrics["last_transition_at"] = _utc_now().isoformat()
    metrics["reason"] = f"watchdog: {message}"
    save_breaker_metrics(metrics, METRICS_PATH)
    print(f"[watchdog] breaker state updated → global_paused ({message})")


def _watchdog_append_experiment(decision: dict) -> None:
    """Append a watchdog decision record to vault/logs/experiments.jsonl."""
    log_path = Path(EXPERIMENTS_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": _utc_now().isoformat(),
        **decision,
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False))
        fh.write("\n")


def _run_watchdog_observation_loop() -> list[dict]:
    """
    Run the full watchdog observation loop after a consolidation run.

    Steps:
    1. Load self-healing metrics from METRICS_PATH
    2. Evaluate thresholds (revert rate, review backlog, consecutive cycles)
    3. For each alert:
       a. Emit alert to consolidation log
       b. Update breaker state if global_pause trigger
    4. Append decision record to experiments.jsonl
    5. Return list of alerts for reporting
    """
    from vault.research.self_healing import load_breaker_metrics

    metrics = load_breaker_metrics(METRICS_PATH)
    alerts = _watchdog_evaluate_thresholds(metrics)

    breaker_action = "none"
    for alert in alerts:
        _watchdog_alert(alert)
        if alert.get("trigger_global_pause", False):
            _watchdog_update_breaker_state(alert)
            breaker_action = "global_pause"

    decision = {
        "event_type": "watchdog_decision",
        "alerts": alerts,
        "breaker_action": breaker_action,
    }
    _watchdog_append_experiment(decision)

    return alerts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_env()
    print(
        f"[research_consolidation] starting daily consolidation "
        f"(replaces dream-memory-consolidation)"
    )

    # Acquire consolidation lock (shared TTL semantics with per-source crons)
    if not acquire_lock(LOCK_PATH):
        print("[research_consolidation] lock held — skipping")
        print(json.dumps({"skipped_reason": "locked", "run_at": _utc_now().isoformat()}))
        return

    try:
        # 1) Run TLDV pipeline
        print("[research_consolidation] running TLDV pipeline flush...")
        tldv_pipeline = ResearchPipeline(
            source="tldv",
            state_path=STATE_PATH,
            research_dir=RESEARCH_DIR_TLDV,
            read_only_mode=True,
        )
        tldv_result = tldv_pipeline.run()
        print(f"[research_consolidation] TLDV: {tldv_result}")

        # 2) Run GitHub pipeline
        print("[research_consolidation] running GitHub pipeline flush...")
        gh_pipeline = ResearchPipeline(
            source="github",
            state_path=STATE_PATH,
            research_dir=RESEARCH_DIR_GITHUB,
            read_only_mode=True,
        )
        gh_result = gh_pipeline.run()
        print(f"[research_consolidation] GitHub: {gh_result}")

        # 3) Compact processed keys (180-day retention)
        print("[research_consolidation] compacting processed keys (180-day retention)...")
        compact_processed_keys(retention_days=180, state_path=STATE_PATH)

        # 4) Monthly snapshot (days 1–5 of month)
        snapshot_result = None
        if _is_first_five_days():
            print("[research_consolidation] creating monthly snapshot...")
            snapshot_result = monthly_snapshot(state_path=STATE_PATH)
            print(f"[research_consolidation] snapshot: {snapshot_result}")

        # 5) Metrics
        metrics = state_metrics(state_path=STATE_PATH)
        print(f"[research_consolidation] state metrics: {metrics}")

        # 5b) Validate self-healing breaker schema
        breaker_valid = _validate_breaker_schema()
        print(f"[research_consolidation] breaker schema valid: {breaker_valid}")

        # 5c) Watchdog observation loop — evaluate thresholds + emit alerts
        if not breaker_valid:
            print(
                "[research_consolidation] WARNING: breaker schema invalid — "
                "skipping watchdog observation loop"
            )
            watchdog_alerts = []
        else:
            print("[research_consolidation] running watchdog observation loop...")
            watchdog_alerts = _run_watchdog_observation_loop()
            if watchdog_alerts:
                print(f"[research_consolidation] watchdog: {len(watchdog_alerts)} alert(s) emitted")
            else:
                print("[research_consolidation] watchdog: all thresholds clear")

        # 6) Log entry
        run_at = _utc_now().isoformat()
        log_entry = {
            "run_at": run_at,
            "tldv": {
                "events_processed": tldv_result.get("events_processed", 0),
                "events_skipped": tldv_result.get("events_skipped", 0),
                "status": tldv_result.get("status"),
            },
            "github": {
                "events_processed": gh_result.get("events_processed", 0),
                "events_skipped": gh_result.get("events_skipped", 0),
                "status": gh_result.get("status"),
            },
            "metrics": metrics,
            "snapshot_created": snapshot_result is not None,
            "watchdog_alerts": [a["alert_type"] for a in watchdog_alerts],
        }
        _append_consolidation_log(log_entry)
        print(f"[research_consolidation] log entry appended to {CONSOLIDATION_LOG}")

        result = {
            "status": "success",
            "run_at": run_at,
            "tldv": log_entry["tldv"],
            "github": log_entry["github"],
            "metrics": metrics,
            "snapshot_created": log_entry["snapshot_created"],
            "watchdog_alerts": log_entry["watchdog_alerts"],
        }
        print(json.dumps(result, default=str))
    finally:
        release_lock(LOCK_PATH)


if __name__ == "__main__":
    main()
