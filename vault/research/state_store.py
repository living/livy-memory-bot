"""Canonical SSOT state store for research pipeline (minimal API)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

DEFAULT_STATE = {
    "processed_event_keys": {"github": [], "tldv": []},
    "last_seen_at": {"github": None, "tldv": None},
    "version": 1,
}

DEFAULT_STATE_PATH = Path("state/identity-graph/state.json")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_iso(dt: datetime | str) -> str:
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_iso(iso: str) -> datetime:
    if iso.endswith("Z"):
        iso = iso.replace("Z", "+00:00")
    return datetime.fromisoformat(iso)


def load_state(state_path: str | Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    path = Path(state_path)
    if not path.exists():
        save_state(copy.deepcopy(DEFAULT_STATE), path)
    raw = json.loads(path.read_text())

    # Minimal normalization to guarantee required top-level keys.
    if "processed_event_keys" not in raw:
        raw["processed_event_keys"] = {"github": [], "tldv": []}
    if "last_seen_at" not in raw:
        raw["last_seen_at"] = {"github": None, "tldv": None}
    if "version" not in raw:
        raw["version"] = 1

    return raw


def save_state(state_dict: dict[str, Any], state_path: str | Path = DEFAULT_STATE_PATH) -> None:
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state_dict, indent=2, ensure_ascii=False))


def upsert_processed_event_key(
    source: str,
    event_key: str,
    event_at: datetime | str,
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state = load_state(state_path)
    processed = state.setdefault("processed_event_keys", {})
    entries = processed.setdefault(source, [])

    existing = any(item.get("key") == event_key for item in entries if isinstance(item, dict))
    if not existing:
        entries.append({"key": event_key, "event_at": _to_iso(event_at)})

    save_state(state, state_path)
    return state


def compact_processed_keys(
    retention_days: int = 180,
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state = load_state(state_path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    processed = state.setdefault("processed_event_keys", {})
    for source, entries in processed.items():
        cleaned: list[dict[str, Any]] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            event_at = item.get("event_at")
            if not event_at:
                continue
            try:
                dt = _parse_iso(event_at)
            except ValueError:
                continue
            if dt >= cutoff:
                cleaned.append(item)
        processed[source] = cleaned

    save_state(state, state_path)
    return state


def monthly_snapshot(state_path: str | Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    state = load_state(state_path)
    snapshot = {
        "snapshot_at": _iso_now(),
        "version": state.get("version", 1),
        "last_seen_at": copy.deepcopy(state.get("last_seen_at", {})),
        "processed_event_keys": copy.deepcopy(state.get("processed_event_keys", {})),
    }
    return snapshot


def state_metrics(state_path: str | Path = DEFAULT_STATE_PATH) -> dict[str, dict[str, int]]:
    state = load_state(state_path)
    result: dict[str, dict[str, int]] = {}

    for source, entries in state.get("processed_event_keys", {}).items():
        payload = json.dumps(entries, ensure_ascii=False)
        result[source] = {
            "key_count": len(entries),
            "size_bytes": len(payload.encode("utf-8")),
        }

    return result
