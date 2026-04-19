"""Self-healing apply core — confidence-based decision policy with metrics tracking."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vault.research.lock_manager import acquire_lock, release_lock
from vault.research.state_store import load_state, save_state

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_METRICS_PATH = Path("state/identity-graph/self_healing_metrics.json")
DEFAULT_EXPERIMENTS_LOG = Path("vault/logs/experiments.jsonl")

DEFAULT_METRICS = {
    "applied": 0,
    "queued": 0,
    "dropped": 0,
    "skipped": 0,
    "dry_run": 0,
    "last_applied_at": None,
    "last_queued_at": None,
    "last_dropped_at": None,
}

DEFAULT_METRICS_V2 = {
    "schema_version": 2,
    "hourly_24h": {},
    "contradictions_detected": 0,
    "supersessions_applied": 0,
    "avg_confidence_by_source": {},
    "auto_rejected_below_threshold": 0,
    "apply_errors": 0,
}

# Circuit breaker thresholds
QUALITY_ERROR_THRESHOLD = 3      # consecutive quality errors → source paused
REVERT_THRESHOLD = 5              # reverts in window → global paused
REVERT_WINDOW = 10                # runs to consider for revert count
CLEAN_RUN_THRESHOLD = 3           # consecutive clean runs → reset source pause

# Circuit breaker metrics schema
DEFAULT_BREAKER_METRICS = {
    "mode": "monitoring",
    "paused_sources": [],
    "apply_count_by_source": {},
    "rollback_count_by_source": {},
    "revert_streak_by_source": {},
    "error_streak_by_source": {},
    "availability_error_by_source": {},
    "recent_run_outcomes_by_source": {},   # {source: ["revert"|"clean"|"error", ...]}
    "review_queue_size": 0,
    "last_transition_at": None,
    "reason": "",
}

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit breaker — metrics helpers
# ---------------------------------------------------------------------------

def load_breaker_metrics(
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
) -> dict[str, Any]:
    """Load breaker metrics, merging with defaults for forward-compatibility."""
    path = Path(metrics_path)
    if not path.exists():
        return dict(DEFAULT_BREAKER_METRICS)
    try:
        data = json.loads(path.read_text())
        result = dict(DEFAULT_BREAKER_METRICS)
        result.update(data)
        return result
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_BREAKER_METRICS)


def save_breaker_metrics(
    metrics: dict[str, Any],
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
) -> None:
    """Save breaker metrics to disk."""
    path = Path(metrics_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))


def get_breaker_mode(metrics_path: Path | str = DEFAULT_METRICS_PATH) -> str:
    """Return current breaker mode string."""
    return load_breaker_metrics(metrics_path)["mode"]


def is_source_paused(
    source: str,
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
) -> bool:
    """Return True when the source is paused or mode is global_paused."""
    metrics = load_breaker_metrics(metrics_path)
    if metrics["mode"] == "global_paused":
        return True
    return source in metrics["paused_sources"]


# ---------------------------------------------------------------------------
# Circuit breaker — streak tracking
# ---------------------------------------------------------------------------

def bump_breaker_error(
    source: str,
    error_type: str,  # "quality" | "availability"
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
) -> None:
    """
    Record a quality or availability error for the source.

    Quality errors increment error_streak. Availability errors reset
    error_streak and increment availability_error_by_source.
    Both append an outcome to the recent-run window.
    """
    metrics = load_breaker_metrics(metrics_path)
    if error_type == "quality":
        metrics["error_streak_by_source"][source] = \
            metrics["error_streak_by_source"].get(source, 0) + 1
        _record_run_outcome(source, "error", metrics)
    elif error_type == "availability":
        metrics["error_streak_by_source"][source] = 0
        metrics["availability_error_by_source"][source] = \
            metrics["availability_error_by_source"].get(source, 0) + 1
        _record_run_outcome(source, "error", metrics)
    save_breaker_metrics(metrics, metrics_path)


def _record_run_outcome(
    source: str,
    outcome: str,  # "revert" | "clean" | "error"
    metrics: dict[str, Any],
) -> None:
    """Append outcome to recent_run_outcomes_by_source, cap at REVERT_WINDOW."""
    outcomes = metrics.setdefault("recent_run_outcomes_by_source", {}).setdefault(source, [])
    outcomes.append(outcome)
    # Keep only the last REVERT_WINDOW outcomes
    del outcomes[:-REVERT_WINDOW]


def bump_breaker_revert(
    source: str,
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
) -> None:
    """Record a revert for the source — increments revert_streak and appends outcome."""
    metrics = load_breaker_metrics(metrics_path)
    metrics["revert_streak_by_source"][source] = \
        metrics["revert_streak_by_source"].get(source, 0) + 1
    _record_run_outcome(source, "revert", metrics)
    save_breaker_metrics(metrics, metrics_path)


def bump_clean_run(
    source: str,
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
) -> None:
    """Record a clean run — resets both streaks and appends clean outcome."""
    metrics = load_breaker_metrics(metrics_path)
    metrics["error_streak_by_source"][source] = 0
    metrics["revert_streak_by_source"][source] = 0
    _record_run_outcome(source, "clean", metrics)
    save_breaker_metrics(metrics, metrics_path)


# ---------------------------------------------------------------------------
# Circuit breaker — apply/rollback accounting
# ---------------------------------------------------------------------------

def record_apply(
    source: str,
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
) -> None:
    """Increment apply_count_by_source."""
    metrics = load_breaker_metrics(metrics_path)
    metrics["apply_count_by_source"][source] = \
        metrics["apply_count_by_source"].get(source, 0) + 1
    save_breaker_metrics(metrics, metrics_path)


def record_rollback(
    source: str,
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
) -> None:
    """Increment rollback_count_by_source."""
    metrics = load_breaker_metrics(metrics_path)
    metrics["rollback_count_by_source"][source] = \
        metrics["rollback_count_by_source"].get(source, 0) + 1
    save_breaker_metrics(metrics, metrics_path)


# ---------------------------------------------------------------------------
# Circuit breaker — state machine transitions
# ---------------------------------------------------------------------------

def transition_breaker(
    source: str,
    reason: str,
    metrics_path: Path | str = DEFAULT_METRICS_PATH,
    experiments_log: Path | str | None = None,
) -> None:
    """
    Evaluate breaker thresholds and perform state transitions.

    Transitions:
      - 3+ consecutive quality errors on a source  → write_paused, source paused
      - 5+ reverts in window                       → global_paused
      - 3 clean runs after source pause            → monitoring, source un-paused
    """
    metrics = load_breaker_metrics(metrics_path)
    error_streak = metrics["error_streak_by_source"].get(source, 0)
    revert_streak = metrics["revert_streak_by_source"].get(source, 0)
    prev_mode = metrics["mode"]
    now = datetime.now(timezone.utc).isoformat()

    # 3 quality errors in a row → source pause
    if error_streak >= QUALITY_ERROR_THRESHOLD:
        metrics["mode"] = "write_paused"
        if source not in metrics["paused_sources"]:
            metrics["paused_sources"].append(source)
        metrics["last_transition_at"] = now
        metrics["reason"] = reason
        save_breaker_metrics(metrics, metrics_path)
        emit_breaker_transition(
            source=source,
            breaker_mode=metrics["mode"],
            decision="source_pause",
            reason=reason,
            experiments_log=experiments_log,
        )
        return

    # 5+ reverts in last 10 runs → global pause
    recent = metrics.get("recent_run_outcomes_by_source", {}).get(source, [])
    revert_count_in_window = recent.count("revert")
    if revert_count_in_window >= REVERT_THRESHOLD and len(recent) >= REVERT_WINDOW:
        metrics["mode"] = "global_paused"
        metrics["last_transition_at"] = now
        metrics["reason"] = reason
        save_breaker_metrics(metrics, metrics_path)
        emit_breaker_transition(
            source=source,
            breaker_mode=metrics["mode"],
            decision="global_pause",
            reason=reason,
            experiments_log=experiments_log,
        )
        return

    # 3 clean runs after a source was paused → reset that source
    if source in metrics["paused_sources"] and prev_mode == "write_paused":
        last_outcomes = metrics.get("recent_run_outcomes_by_source", {}).get(source, [])
        last_clean = last_outcomes[-CLEAN_RUN_THRESHOLD:]
        if (
            len(last_clean) == CLEAN_RUN_THRESHOLD
            and all(item == "clean" for item in last_clean)
            and error_streak == 0
            and revert_streak == 0
        ):
            metrics["paused_sources"] = [s for s in metrics["paused_sources"] if s != source]
            if not metrics["paused_sources"]:
                metrics["mode"] = "monitoring"
            metrics["last_transition_at"] = now
            metrics["reason"] = reason
            save_breaker_metrics(metrics, metrics_path)
            emit_breaker_transition(
                source=source,
                breaker_mode=metrics["mode"],
                decision="source_reset",
                reason=reason,
                experiments_log=experiments_log,
            )
            return

    # No transition — just update reason/timestamp if meaningful
    if reason and reason != metrics.get("reason"):
        metrics["reason"] = reason
        save_breaker_metrics(metrics, metrics_path)


def reset_breaker(metrics_path: Path | str = DEFAULT_METRICS_PATH) -> None:
    """Restore breaker to monitoring state — clears all streaks and paused sources."""
    save_breaker_metrics(dict(DEFAULT_BREAKER_METRICS), metrics_path)


# ---------------------------------------------------------------------------
# Circuit breaker — experiments.jsonl emission
# ---------------------------------------------------------------------------

def emit_breaker_transition(
    source: str,
    breaker_mode: str,
    decision: str,
    reason: str,
    experiments_log: Path | str | None = None,
) -> None:
    """
    Append a breaker transition record to vault/logs/experiments.jsonl.

    Record fields: ts, source, breaker_mode, decision, reason
    """
    log_path = Path(experiments_log) if experiments_log else DEFAULT_EXPERIMENTS_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "breaker_transition",
        "source": source,
        "breaker_mode": breaker_mode,
        "decision": decision,
        "reason": reason,
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False))
        fh.write("\n")


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def load_metrics(metrics_path: Path | str = DEFAULT_METRICS_PATH) -> dict[str, Any]:
    path = Path(metrics_path)
    if not path.exists():
        return dict(DEFAULT_METRICS)
    try:
        data = json.loads(path.read_text())
        # Merge with defaults to guarantee all known fields are present
        result = dict(DEFAULT_METRICS)
        result.update(data)
        return result
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_METRICS)


def save_metrics(metrics: dict[str, Any], metrics_path: Path | str = DEFAULT_METRICS_PATH) -> None:
    path = Path(metrics_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))


def _bump_metrics(
    metrics: dict[str, Any],
    key: str,
    metrics_path: Path | str,
) -> None:
    """Increment the named counter and update the timestamp field."""
    now = datetime.now(timezone.utc).isoformat()
    ts_field = f"last_{key}_at"
    metrics[key] = metrics.get(key, 0) + 1
    if ts_field in DEFAULT_METRICS:
        metrics[ts_field] = now
    save_metrics(metrics, metrics_path)


# ---------------------------------------------------------------------------
# Environment-driven feature flags
# ---------------------------------------------------------------------------

def _write_enabled() -> bool:
    return os.environ.get("SELF_HEALING_WRITE_ENABLED", "true").lower() != "false"


def _aggressive_mode() -> bool:
    return os.environ.get("SELF_HEALING_AGGRESSIVE_MODE", "true").lower() != "false"


def _policy_version() -> str:
    raw = os.environ.get("SELF_HEALING_POLICY_VERSION", "v1").strip().lower()
    return raw if raw in {"v1", "v2"} else "v1"


def _breaker_enabled() -> bool:
    return os.environ.get("SELF_HEALING_BREAKER_ENABLED", "true").lower() != "false"


# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------

THRESHOLD_APPLY = 0.85          # confidence >= 0.85 → applied
THRESHOLD_AGGRESSIVE = 0.70     # confidence >= 0.70 (and < 0.85) → aggressive zone
THRESHOLD_QUEUE = 0.45          # confidence >= 0.45 (and < 0.70) → queued


def _confidence_bucket(confidence: float, policy_version: str) -> str:
    if confidence >= THRESHOLD_APPLY:
        return "applied"
    # v2 policy is strict: no aggressive auto-apply in 0.70-0.84
    if policy_version == "v1" and confidence >= THRESHOLD_AGGRESSIVE:
        return "aggressive"
    if confidence >= THRESHOLD_QUEUE:
        return "queued"
    return "dropped"


# ---------------------------------------------------------------------------
# Verbose logging for aggressive zone
# ---------------------------------------------------------------------------

def _log_aggressive(source: str, confidence: float, hypothesis: dict[str, Any]) -> None:
    _logger.info(
        "[SELF-HEALING:AGGRESSIVE] source=%s confidence=%.2f hypothesis=%s",
        source,
        confidence,
        hypothesis,
    )


# ---------------------------------------------------------------------------
# apply_decision — main entry point
# ---------------------------------------------------------------------------

def _ensure_metrics_schema(metrics: dict[str, Any], policy_version: str) -> dict[str, Any]:
    """Upgrade/normalize metrics schema in-memory for the selected policy."""
    result = dict(metrics)
    if policy_version != "v2":
        return result

    # v2 canonical schema extension (backwards-compatible)
    if result.get("schema_version") != 2:
        result["schema_version"] = 2
    for key, value in DEFAULT_METRICS_V2.items():
        result.setdefault(key, value if not isinstance(value, dict) else dict(value))
    return result


def _merge_id(hypothesis: dict[str, Any], confidence: float, source: str) -> str:
    payload = {
        "hypothesis": hypothesis,
        "confidence": round(confidence, 6),
        "source": source,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def apply_decision(
    hypothesis: dict[str, Any],
    confidence: float,
    source: str,
    metrics_path: Path | str | None = None,
    breaker_metrics_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Apply a self-healing decision based on confidence thresholds.

    Policy versions:
      - v1 (default): legacy behavior with aggressive 0.70–0.84 when enabled
      - v2: strict behavior (only >=0.85 applies automatically)

    Decision outcomes:
      - applied  : confidence >= 0.85 (or >=0.70 in v1 aggressive mode)
      - queued   : confidence 0.45–0.84 in v2, or 0.45–0.69 in v1
      - dropped  : confidence < 0.45
      - skipped  : dry-run, breaker-disabled, aggressive mode off for v1 0.70–0.84,
                   or source/global pause active

    Returns:
      dict with keys: decision, confidence, reason, source, policy_version, merge_id
    """
    m_path = Path(metrics_path) if metrics_path else DEFAULT_METRICS_PATH
    b_path = Path(breaker_metrics_path) if breaker_metrics_path else DEFAULT_METRICS_PATH
    policy_version = _policy_version()
    metrics = _ensure_metrics_schema(load_metrics(m_path), policy_version)

    write_enabled = _write_enabled()
    aggressive = _aggressive_mode()
    breaker_enabled = _breaker_enabled()
    merge_id = _merge_id(hypothesis, confidence, source)

    # Dry-run gate: accumulate evidence but don't apply
    if not write_enabled:
        metrics["skipped"] = metrics.get("skipped", 0) + 1
        metrics["dry_run"] = metrics.get("dry_run", 0) + 1
        save_metrics(metrics, m_path)
        return {
            "decision": "skipped",
            "confidence": confidence,
            "reason": "dry-run",
            "source": source,
            "policy_version": policy_version,
            "merge_id": None,
        }

    if not breaker_enabled:
        _bump_metrics(metrics, "skipped", m_path)
        return {
            "decision": "skipped",
            "confidence": confidence,
            "reason": "breaker-disabled",
            "source": source,
            "policy_version": policy_version,
            "merge_id": None,
        }

    # Circuit breaker gate — check before applying
    if is_source_paused(source, b_path):
        breaker_mode = get_breaker_mode(b_path)
        _bump_metrics(metrics, "skipped", m_path)
        return {
            "decision": "skipped",
            "confidence": confidence,
            "reason": f"breaker-{breaker_mode}",
            "source": source,
            "policy_version": policy_version,
            "merge_id": None,
        }

    bucket = _confidence_bucket(confidence, policy_version)

    if bucket == "applied":
        _bump_metrics(metrics, "applied", m_path)
        record_apply(source, b_path)
        return {
            "decision": "applied",
            "confidence": confidence,
            "reason": f"confidence {confidence:.2f} >= {THRESHOLD_APPLY}",
            "source": source,
            "policy_version": policy_version,
            "merge_id": merge_id,
        }

    if bucket == "aggressive":
        if aggressive:
            _log_aggressive(source, confidence, hypothesis)
            _bump_metrics(metrics, "applied", m_path)
            record_apply(source, b_path)
            return {
                "decision": "applied",
                "confidence": confidence,
                "reason": f"aggressive: confidence {confidence:.2f} >= {THRESHOLD_AGGRESSIVE}",
                "source": source,
                "policy_version": policy_version,
                "merge_id": merge_id,
            }
        else:
            _bump_metrics(metrics, "skipped", m_path)
            return {
                "decision": "skipped",
                "confidence": confidence,
                "reason": "aggressive-mode disabled",
                "source": source,
                "policy_version": policy_version,
                "merge_id": None,
            }

    if bucket == "queued":
        _bump_metrics(metrics, "queued", m_path)
        if policy_version == "v2":
            metrics = load_metrics(m_path)
            metrics["auto_rejected_below_threshold"] = metrics.get("auto_rejected_below_threshold", 0) + 1
            save_metrics(metrics, m_path)
        upper = THRESHOLD_APPLY if policy_version == "v2" else THRESHOLD_AGGRESSIVE
        return {
            "decision": "queued",
            "confidence": confidence,
            "reason": f"confidence {confidence:.2f} in [{THRESHOLD_QUEUE}, {upper})",
            "source": source,
            "policy_version": policy_version,
            "merge_id": None,
        }

    # bucket == "dropped"
    _bump_metrics(metrics, "dropped", m_path)
    return {
        "decision": "dropped",
        "confidence": confidence,
        "reason": f"confidence {confidence:.2f} < {THRESHOLD_QUEUE}",
        "source": source,
        "policy_version": policy_version,
        "merge_id": None,
    }


# ---------------------------------------------------------------------------
# Append-only rollback engine
# ---------------------------------------------------------------------------

def _prune_applied_merges(entries: list[dict[str, Any]], days: int = 180) -> list[dict[str, Any]]:
    """Keep only applied_merges entries newer than retention window."""
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    kept: list[dict[str, Any]] = []
    for item in entries:
        ts = item.get("applied_at")
        if not isinstance(ts, str):
            continue
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if parsed.timestamp() >= cutoff:
                kept.append(item)
        except ValueError:
            continue
    return kept


def apply_merge_to_ssot(
    *,
    decision: dict[str, Any],
    winner_claim: dict[str, Any],
    loser_claim: dict[str, Any] | None,
    entity_id: str,
    event_key: str,
    state_path: str | Path,
    lock_path: str | Path,
    lock_ttl: int = 600,
) -> dict[str, Any]:
    """Persist an applied merge into SSOT with lock + idempotency.

    Returns dict with: merge_id, state_changed, reason.
    """
    if decision.get("decision") != "applied":
        return {
            "merge_id": decision.get("merge_id"),
            "state_changed": False,
            "reason": "no-apply-needed",
        }

    if not acquire_lock(str(lock_path), ttl=lock_ttl):
        return {
            "merge_id": decision.get("merge_id"),
            "state_changed": False,
            "reason": "lock-timeout",
        }

    try:
        state = load_state(state_path)
        applied = list(state.get("applied_merges", []))
        applied = _prune_applied_merges(applied, days=180)

        merge_id = decision.get("merge_id")
        if merge_id and any(item.get("merge_id") == merge_id for item in applied):
            state["applied_merges"] = applied
            save_state(state, state_path)
            return {
                "merge_id": merge_id,
                "state_changed": False,
                "reason": "duplicate-merge-id",
            }

        entry = {
            "merge_id": merge_id,
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "source": decision.get("source"),
            "event_key": event_key,
            "entity_id": entity_id,
            "winner_claim_id": winner_claim.get("id"),
            "loser_claim_id": loser_claim.get("id") if loser_claim else None,
            "confidence": decision.get("confidence"),
            "contradiction": bool(decision.get("contradiction", False)),
            "policy_version": decision.get("policy_version"),
            "reason": decision.get("reason"),
        }
        applied.append(entry)

        state["applied_merges"] = applied
        save_state(state, state_path)
        return {
            "merge_id": merge_id,
            "state_changed": True,
            "reason": "applied",
        }
    finally:
        release_lock(str(lock_path))


def rollback_append(
    log_path: Path | str,
    event_key: str,
    supersedes: str | None,
    reason: str,
    breaker_mode: bool,
) -> None:
    """
    Append a rollback record to vault/logs/experiments.jsonl.

    This function is append-only: it never reads, parses, or rewrites the
    existing file content.  New records are always appended as a new JSONL
    line so that the file forms an immutable audit trail.

    Fields written:
      - event_key   : identifier of the rollback event
      - supersedes  : event_key being superseded, or None
      - reason      : human-readable justification
      - breaker_mode: whether the breaker was in effect at rollback time
      - timestamp   : ISO-8601 UTC timestamp of the append

    Parameters
    ----------
    log_path  : Path to the JSONL log file (created with parents if absent).
    event_key : Unique identifier for this rollback event.
    supersedes: event_key of the record being superseded, or None.
    reason    : Why this rollback is being recorded.
    breaker_mode: Whether the self-healing breaker was enabled.
    """
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "rollback_append",
        "event_key": event_key,
        "supersedes": supersedes,
        "reason": reason,
        "breaker_mode": breaker_mode,
    }
    line = json.dumps(record, ensure_ascii=False)

    # Append-only: open with 'a' so we never touch existing lines
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.write("\n")
