"""Self-healing apply core — confidence-based decision policy with metrics tracking."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_METRICS_PATH = Path("state/identity-graph/self_healing_metrics.json")

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

_logger = logging.getLogger(__name__)


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


def _breaker_enabled() -> bool:
    return os.environ.get("SELF_HEALING_BREAKER_ENABLED", "true").lower() != "false"


# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------

THRESHOLD_APPLY = 0.85          # confidence >= 0.85 → applied
THRESHOLD_AGGRESSIVE = 0.70     # confidence >= 0.70 (and < 0.85) → aggressive zone
THRESHOLD_QUEUE = 0.45          # confidence >= 0.45 (and < 0.70) → queued


def _confidence_bucket(confidence: float) -> str:
    if confidence >= THRESHOLD_APPLY:
        return "applied"
    if confidence >= THRESHOLD_AGGRESSIVE:
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

def apply_decision(
    hypothesis: dict[str, Any],
    confidence: float,
    source: str,
    metrics_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Apply a self-healing decision based on confidence thresholds.

    Decision outcomes:
      - applied  : confidence >= 0.85 (or >= 0.70 in aggressive mode)
      - queued   : confidence 0.45–0.69
      - dropped  : confidence < 0.45
      - skipped  : dry-run, breaker-disabled, or aggressive mode off for 0.70–0.84

    Environment flags:
      SELF_HEALING_WRITE_ENABLED=false    → dry-run (skipped)
      SELF_HEALING_BREAKER_ENABLED=false  → skipped with reason "breaker-disabled"
      SELF_HEALING_AGGRESSIVE_MODE=false  → 0.70–0.84 range is skipped

    Returns:
      dict with keys: decision, confidence, reason, source
    """
    m_path = Path(metrics_path) if metrics_path else DEFAULT_METRICS_PATH
    metrics = load_metrics(m_path)

    write_enabled = _write_enabled()
    aggressive = _aggressive_mode()
    breaker_enabled = _breaker_enabled()

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
        }

    if not breaker_enabled:
        _bump_metrics(metrics, "skipped", m_path)
        return {
            "decision": "skipped",
            "confidence": confidence,
            "reason": "breaker-disabled",
            "source": source,
        }

    bucket = _confidence_bucket(confidence)

    if bucket == "applied":
        _bump_metrics(metrics, "applied", m_path)
        return {
            "decision": "applied",
            "confidence": confidence,
            "reason": f"confidence {confidence:.2f} >= {THRESHOLD_APPLY}",
            "source": source,
        }

    if bucket == "aggressive":
        if aggressive:
            _log_aggressive(source, confidence, hypothesis)
            _bump_metrics(metrics, "applied", m_path)
            return {
                "decision": "applied",
                "confidence": confidence,
                "reason": f"aggressive: confidence {confidence:.2f} >= {THRESHOLD_AGGRESSIVE}",
                "source": source,
            }
        else:
            _bump_metrics(metrics, "skipped", m_path)
            return {
                "decision": "skipped",
                "confidence": confidence,
                "reason": "aggressive-mode disabled",
                "source": source,
            }

    if bucket == "queued":
        _bump_metrics(metrics, "queued", m_path)
        return {
            "decision": "queued",
            "confidence": confidence,
            "reason": f"confidence {confidence:.2f} in [{THRESHOLD_QUEUE}, {THRESHOLD_AGGRESSIVE})",
            "source": source,
        }

    # bucket == "dropped"
    _bump_metrics(metrics, "dropped", m_path)
    return {
        "decision": "dropped",
        "confidence": confidence,
        "reason": f"confidence {confidence:.2f} < {THRESHOLD_QUEUE}",
        "source": source,
    }


# ---------------------------------------------------------------------------
# Append-only rollback engine
# ---------------------------------------------------------------------------

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
        "event_key": event_key,
        "supersedes": supersedes,
        "reason": reason,
        "breaker_mode": breaker_mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    line = json.dumps(record, ensure_ascii=False)

    # Append-only: open with 'a' so we never touch existing lines
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.write("\n")
