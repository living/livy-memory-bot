"""Canonical SSOT state store for research pipeline (minimal API)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

DEFAULT_STATE = {
    "processed_event_keys": {"github": [], "tldv": [], "trello": []},
    "processed_content_keys": {"github": [], "tldv": [], "trello": []},
    "last_seen_at": {"github": None, "tldv": None, "trello": None},
    "pending_conflicts": [],
    "version": 1,
}

# Alert threshold for pending_conflicts entries (>200 → alert)
PENDING_CONFLICTS_ALERT_THRESHOLD = 200

DEFAULT_STATE_PATH = Path("state/identity-graph/state.json")


# ---------------------------------------------------------------------------
# Source priority for conflict resolution (highest → lowest)
# ---------------------------------------------------------------------------

_SOURCE_PRIORITY: dict[str, int] = {
    "github": 3,
    "tldv": 2,
    "trello": 1,
}
_DEFAULT_PRIORITY = 0


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Core load / save
# ---------------------------------------------------------------------------

def load_state(state_path: str | Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    path = Path(state_path)
    if not path.exists():
        save_state(copy.deepcopy(DEFAULT_STATE), path)
    raw = json.loads(path.read_text())

    # Normalize: ensure all required top-level keys exist.
    if "processed_event_keys" not in raw:
        raw["processed_event_keys"] = {"github": [], "tldv": [], "trello": []}
    if "processed_content_keys" not in raw:
        raw["processed_content_keys"] = {"github": [], "tldv": [], "trello": []}
    if "last_seen_at" not in raw:
        raw["last_seen_at"] = {"github": None, "tldv": None, "trello": None}
    if "version" not in raw:
        raw["version"] = 1

    # Retroactively add trello source to legacy state files.
    for section in ("processed_event_keys", "processed_content_keys", "last_seen_at"):
        if section in raw and "trello" not in raw[section]:
            raw[section]["trello"] = [] if section in {"processed_event_keys", "processed_content_keys"} else None

    # Retroactively add pending_conflicts to legacy state files.
    if "pending_conflicts" not in raw:
        raw["pending_conflicts"] = []

    return raw


def save_state(state_dict: dict[str, Any], state_path: str | Path = DEFAULT_STATE_PATH) -> None:
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state_dict, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Processed event keys
# ---------------------------------------------------------------------------

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


def upsert_processed_content_key(
    source: str,
    content_key: str,
    event_at: datetime | str,
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    """Store a content_key in the SSOT state.

    Content keys dedupe *semantically identical* content even when it arrives
    via different event keys (e.g. replay / retry scenarios).

    Idempotent: calling twice with the same key does not duplicate entries.
    """
    state = load_state(state_path)
    processed = state.setdefault("processed_content_keys", {})
    entries = processed.setdefault(source, [])

    existing = any(item.get("key") == content_key for item in entries if isinstance(item, dict))
    if not existing:
        entries.append({"key": content_key, "event_at": _to_iso(event_at)})

    save_state(state, state_path)
    return state


def compact_processed_keys(
    retention_days: int = 180,
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state = load_state(state_path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    def _compact_section(section_name: str) -> None:
        section = state.setdefault(section_name, {})
        for source, entries in section.items():
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
            section[source] = cleaned

    _compact_section("processed_event_keys")
    _compact_section("processed_content_keys")

    save_state(state, state_path)
    return state


def monthly_snapshot(state_path: str | Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    state = load_state(state_path)
    snapshot = {
        "snapshot_at": _iso_now(),
        "version": state.get("version", 1),
        "last_seen_at": copy.deepcopy(state.get("last_seen_at", {})),
        "processed_event_keys": copy.deepcopy(state.get("processed_event_keys", {})),
        "processed_content_keys": copy.deepcopy(state.get("processed_content_keys", {})),
    }
    return snapshot


def state_metrics(state_path: str | Path = DEFAULT_STATE_PATH) -> dict[str, dict[str, int]]:
    state = load_state(state_path)
    result: dict[str, dict[str, int]] = {}

    event_sections = state.get("processed_event_keys", {})
    content_sections = state.get("processed_content_keys", {})

    all_sources = set(event_sections.keys()) | set(content_sections.keys())
    for source in all_sources:
        event_entries = event_sections.get(source, [])
        content_entries = content_sections.get(source, [])
        event_payload = json.dumps(event_entries, ensure_ascii=False)
        content_payload = json.dumps(content_entries, ensure_ascii=False)

        result[source] = {
            "key_count": len(event_entries),
            "size_bytes": len(event_payload.encode("utf-8")),
            "content_key_count": len(content_entries),
            "content_size_bytes": len(content_payload.encode("utf-8")),
        }

    return result


# ---------------------------------------------------------------------------
# Pending conflicts
# ---------------------------------------------------------------------------

def get_pending_conflicts(state_path: str | Path = DEFAULT_STATE_PATH) -> list[dict[str, Any]]:
    """Return the current list of pending conflicts."""
    state = load_state(state_path)
    return list(state.get("pending_conflicts", []))


def count_pending_conflicts(state_path: str | Path = DEFAULT_STATE_PATH) -> int:
    """Return the number of pending conflicts (status=pending only)."""
    state = load_state(state_path)
    return sum(1 for e in state.get("pending_conflicts", []) if e.get("status") == "pending")


def add_pending_conflict(
    entry: dict[str, Any],
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    """Append a pending conflict entry if it doesn't already exist (entity_id + event_key)."""
    state = load_state(state_path)
    conflicts = state.setdefault("pending_conflicts", [])

    entity_id = entry.get("entity_id", "")
    event_key = entry.get("event_key", "")
    is_duplicate = any(
        e.get("entity_id") == entity_id and e.get("event_key") == event_key
        for e in conflicts
    )
    if not is_duplicate:
        conflicts.append(dict(entry))

    save_state(state, state_path)
    return state


def resolve_pending_conflicts(
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    """Re-resolve pending conflicts using source priority + recency.

    Policy:
      1. Higher source priority wins  (github=3 > tldv=2 > trello=1 > unknown=0)
      2. On tie → most recent event_at wins
      3. On total tie → keep pending
      4. Resolved entries get status=resolved + resolved_by_event_key
    """
    state = load_state(state_path)
    conflicts = state.get("pending_conflicts", [])

    resolved: list[dict[str, Any]] = []
    still_pending: list[dict[str, Any]] = []

    for entry in conflicts:
        if entry.get("status") == "resolved":
            continue

        candidates = entry.get("candidates", [])
        winner = _resolve_single_conflict(candidates)

        if winner is not None:
            resolved_entry = dict(entry)
            resolved_entry["status"] = "resolved"
            resolved_entry["winner_identifier"] = winner["identifier"]
            resolved_entry["resolved_by_event_key"] = winner["resolved_by_event_key"]
            resolved.append(resolved_entry)
        else:
            still_pending.append(dict(entry))

    # Update state in-place: resolved entries updated, still_pending left unchanged
    updated = still_pending + resolved
    # Preserve order: still_pending first, then resolved (chronological within each group)
    state["pending_conflicts"] = updated
    save_state(state, state_path)

    return {
        "resolved": resolved,
        "still_pending": still_pending,
        "resolved_count": len(resolved),
        "still_pending_count": len(still_pending),
        "total_count": len(conflicts),
    }


def _resolve_single_conflict(
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Resolve a single conflict entry. Returns winner dict or None on tie."""
    if not candidates:
        return None

    scored = []
    for cand in candidates:
        priority = _SOURCE_PRIORITY.get(cand.get("source", ""), _DEFAULT_PRIORITY)
        event_at = _parse_event_at(cand.get("event_at"))
        scored.append({
            "candidate": cand,
            "priority": priority,
            "event_at": event_at,
        })

    scored.sort(key=lambda x: (x["priority"], x["event_at"]), reverse=True)

    top = scored[0]
    top_priority = top["priority"]
    top_event_at = top["event_at"]

    # Check for tie on priority + event_at
    ties = [
        s for s in scored
        if s["priority"] == top_priority and s["event_at"] == top_event_at
    ]
    if len(ties) > 1:
        return None  # full tie → keep pending

    winner = top["candidate"]
    source = winner.get("source", "unknown")
    priority_val = _SOURCE_PRIORITY.get(source, _DEFAULT_PRIORITY)
    resolved_by_event_key = f"resolved:{source}:priority:{priority_val}"

    return {
        "identifier": winner.get("identifier"),
        "source": source,
        "priority": priority_val,
        "resolved_by_event_key": resolved_by_event_key,
    }


def _parse_event_at(event_at_str: str | None) -> datetime:
    """Parse event_at string to datetime, returning epoch on failure."""
    if not event_at_str:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(event_at_str.replace("Z", "+00:00"))
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
