"""vault/research/retry_policy.py

Retry policy for HTTP errors encountered during research scraping.

Policy summary:
  - 429 (Rate Limit): exponential backoff 60 → 120 → 240 → 480s, max 3 retries
  - 5xx (Server Error): exponential backoff 30 → 60 → 120s, max 3 retries
  - 401/403 (Auth Error): no retry, raises NonRetriableError immediately
  - timeout (status_code=None): 1 immediate retry (0s), then falls back to 5xx policy
    (total retries: 1 + 3 = 4, exhausted at retry_count >= 4)
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Any, Optional

# Default path relative to project root
_DEFAULT_LOG_PATH = str(
    Path(__file__).resolve().parents[2] / "memory" / "consolidation-log.md"
)

_MAX_RETRIES = 3

# Backoff schedules (indexed by retry_count)
_429_DELAYS = [60, 120, 240, 480]   # seconds
_5XX_DELAYS = [30, 60, 120]          # seconds


class NonRetriableError(Exception):
    """Raised for HTTP status codes that should never be retried (401, 403)."""


def _utc_now_z() -> str:
    """Current UTC time in ISO-8601 Zulu format."""
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def should_retry(status_code: Optional[int], retry_count: int) -> bool:
    """Return True if the request should be retried given the current retry_count.

    Args:
        status_code: HTTP status code, or None to represent a timeout.
        retry_count: Number of retries already attempted (0-based).

    Returns:
        True if a retry should be attempted.
    """
    if status_code in (401, 403):
        return False

    if status_code == 429:
        return retry_count < _MAX_RETRIES

    if status_code is not None and 500 <= status_code <= 599:
        return retry_count < _MAX_RETRIES

    if status_code is None:
        # Timeout: 1 immediate retry + up to 3 5xx-style retries = 4 total
        return retry_count < (_MAX_RETRIES + 1)

    # Unknown status codes: no retry
    return False


def next_retry_delay(status_code: Optional[int], retry_count: int) -> int:
    """Return the delay in seconds before the next retry attempt.

    Args:
        status_code: HTTP status code, or None for timeout.
        retry_count: Number of retries already attempted (0-based).

    Returns:
        Delay in seconds (0 means retry immediately).

    Raises:
        NonRetriableError: If status_code is 401 or 403.
    """
    if status_code in (401, 403):
        raise NonRetriableError(
            f"HTTP {status_code} is not retriable — check credentials/permissions."
        )

    if status_code == 429:
        idx = min(retry_count, len(_429_DELAYS) - 1)
        return _429_DELAYS[idx]

    if status_code is not None and 500 <= status_code <= 599:
        idx = min(retry_count, len(_5XX_DELAYS) - 1)
        return _5XX_DELAYS[idx]

    if status_code is None:
        # First timeout retry is immediate; subsequent ones follow 5xx policy
        if retry_count == 0:
            return 0
        idx = min(retry_count - 1, len(_5XX_DELAYS) - 1)
        return _5XX_DELAYS[idx]

    # Fallback for unknown codes
    return 0


def build_retry_record(
    event_key: str,
    error: str,
    retry_count: int,
    next_retry_at: Optional[str],
) -> dict[str, Any]:
    """Build a retry record dict for state tracking.

    Args:
        event_key: Canonical event identifier (e.g. "github:pr:42").
        error: Human-readable description of the last error.
        retry_count: Number of retries already attempted.
        next_retry_at: ISO-8601 timestamp for next attempt, or None if exhausted.

    Returns:
        Dict with keys: event_key, status, retry_count, last_error,
        next_retry_at, last_attempt_at.
    """
    status = "exhausted" if next_retry_at is None else "pending_retry"
    now = _utc_now_z()

    return {
        "event_key": event_key,
        "status": status,
        "retry_count": retry_count,
        "last_error": error,
        "next_retry_at": next_retry_at,
        "last_attempt_at": now,
    }


def log_exhausted_event(
    record: dict[str, Any],
    log_path: str = _DEFAULT_LOG_PATH,
) -> None:
    """Append an exhausted retry record to the consolidation log.

    The log file is created if it does not exist.

    Args:
        record: A dict returned by build_retry_record() with status="exhausted".
        log_path: Path to the consolidation log markdown file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)

    ts = _utc_now_z()
    entry = (
        f"\n## Retry Exhausted — {ts}\n"
        f"- **event_key**: {record['event_key']}\n"
        f"- **status**: {record['status']}\n"
        f"- **retry_count**: {record['retry_count']}\n"
        f"- **last_error**: {record['last_error']}\n"
        f"- **last_attempt_at**: {record.get('last_attempt_at', ts)}\n"
    )

    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(entry)


def log_exhausted_to_consolidation_log(
    event_key: str,
    error: str,
    log_path: str = _DEFAULT_LOG_PATH,
) -> None:
    """Compatibility helper required by spec: log exhausted event by key+error."""
    record = build_retry_record(
        event_key=event_key,
        error=error,
        retry_count=3,
        next_retry_at=None,
    )
    log_exhausted_event(record, log_path=log_path)
