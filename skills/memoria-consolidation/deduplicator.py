"""Semantic deduplicator with 7-day temporal window."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

_WINDOW_DAYS = 7


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None

    ts = value.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def make_fingerprint(topic: str, entity_key: str, rule_id: str) -> str:
    """Create collision-safe semantic fingerprint for dedup decisions."""
    raw = f"topic:{_normalize(topic)}|entity_key:{_normalize(entity_key)}|rule_id:{_normalize(rule_id)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_duplicate(
    fingerprint: str,
    ledger: list[dict[str, Any]],
    now: datetime | None = None,
) -> bool:
    """Return True when matching fingerprint exists in ledger newer than 7 days."""
    if not ledger or not fingerprint:
        return False

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    window = timedelta(days=_WINDOW_DAYS)

    for entry in ledger:
        if entry.get("fingerprint") != fingerprint:
            continue

        decided_at = _parse_timestamp(entry.get("decided_at"))
        if decided_at is None:
            continue

        age = current - decided_at
        if timedelta(0) <= age < window:
            return True

    return False


def filter_duplicate_signals(
    signals: list[dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Filter duplicate signals using semantic fingerprint + 7-day temporal window."""
    if not signals:
        return []

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    kept: list[dict[str, Any]] = []
    kept_ledger: list[dict[str, Any]] = []

    for signal in signals:
        fingerprint = make_fingerprint(
            signal.get("topic", ""),
            signal.get("entity_key", ""),
            signal.get("rule_id", ""),
        )

        if is_duplicate(fingerprint, kept_ledger, now=current):
            continue

        kept.append(signal)
        kept_ledger.append(
            {
                "fingerprint": fingerprint,
                "decided_at": signal.get("decided_at") or current.isoformat().replace("+00:00", "Z"),
            }
        )

    return kept
