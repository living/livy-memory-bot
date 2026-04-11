"""Trello card ingestion → canonical card entities.

Phase C1 contract:
- Read from Trello REST API (boards/{board_id}/cards)
- Lookback: 7 days by dateLastActivity
- Output: canonical card entities with full lineage
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

from vault.domain.normalize import build_entity_with_traceability
from vault.domain.canonical_types import is_iso_date

MAPPER_VERSION = "wave-c-card-ingest-v1"
DEFAULT_LOOKBACK_DAYS = 7


def _fetch_from_trello(days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict[str, Any]]:
    """Fetch recently-active cards from Trello.

    Reads TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_BOARD_ID from environment.
    Returns list of raw card dicts.
    """
    import requests

    api_key = os.environ.get("TRELLO_API_KEY")
    token = os.environ.get("TRELLO_TOKEN")
    board_id = os.environ.get("TRELLO_BOARD_ID")
    if not api_key or not token or not board_id:
        print("[WARN] TRELLO_API_KEY or token or board not set; skipping fetch", file=sys.stderr)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    url = f"https://api.trello.com/1/boards/{board_id}/cards"
    params = {
        "key": api_key,
        "token": token,
        "fields": "id,name,desc,idBoard,idList,dateLastActivity,idMembers",
        "members": "true",
        "member_fields": "fullName,username",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    cards = resp.json()
    return [c for c in cards if _is_recent(c, cutoff)]


def _is_recent(card: dict[str, Any], cutoff: datetime) -> bool:
    dla = card.get("dateLastActivity")
    if not dla:
        return False
    try:
        dt = datetime.fromisoformat(str(dla).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except ValueError:
        return False


def normalize_card_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Trello card record to a Card entity.

    Produces a partial entity dict (without lineage stamps).
    Use build_entity_with_traceability() after to add lineage.

    Allowed fields per validate_card():
      id_canonical, card_id_source, title, board, list, project_ref, status
    """
    card_id = raw.get("id", "")
    if not isinstance(card_id, str) or not card_id.strip():
        raise ValueError("card_id is required")

    # board_id extraction: raw can have board={id, name}, idBoard, or board_id
    board_id = raw.get("board_id")
    if not isinstance(board_id, str) or not board_id.strip():
        board_data = raw.get("board")
        if isinstance(board_data, dict):
            board_id = board_data.get("id", "")
        if not isinstance(board_id, str) or not board_id.strip():
            id_board = raw.get("idBoard")
            if isinstance(id_board, str):
                board_id = id_board
    if not isinstance(board_id, str) or not board_id.strip():
        raise ValueError("board_id is required")

    title = raw.get("name") or raw.get("title", "")
    project_ref = raw.get("project_ref")
    status = raw.get("state") or raw.get("status")

    # list: raw can have list={name} or idList
    list_name = None
    list_data = raw.get("list")
    if isinstance(list_data, dict):
        list_name = list_data.get("name")

    date_last_activity = raw.get("dateLastActivity")
    if date_last_activity is not None and not is_iso_date(date_last_activity):
        raise ValueError("dateLastActivity must be ISO date/datetime")

    source_keys = [f"trello:{board_id}:{card_id}"]

    entity: dict[str, Any] = {
        "id_canonical": f"card:{board_id}:{card_id}",
        "card_id_source": card_id,
        "title": title,
        "board": board_id,
        "list": list_name,
        "source_keys": source_keys,
    }

    if project_ref is not None:
        entity["project_ref"] = project_ref
    if status is not None:
        entity["status"] = status

    return entity


def build_card_entity(
    raw: dict[str, Any],
    mapper_version: str = MAPPER_VERSION,
) -> dict[str, Any]:
    """Build a fully-stamped canonical card entity from a raw Trello record."""
    entity = normalize_card_record(raw)
    return build_entity_with_traceability(entity, mapper_version)


def extract_assignees(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract assignee/member records from a card dict.

    Skips members without a valid non-empty id.
    """
    members = raw.get("idMembers") or []
    members_data = raw.get("membersData") or raw.get("members") or []

    # board_id: same fallback as normalize_card_record
    board_id = raw.get("board_id")
    if not isinstance(board_id, str) or not board_id.strip():
        board_data = raw.get("board")
        if isinstance(board_data, dict):
            board_id = board_data.get("id", "unknown")
        else:
            board_id = raw.get("idBoard", "unknown")

    card_id = raw.get("id", "")

    # Index members data by id for lookup
    data_map: dict[str, dict] = {
        m.get("id"): m for m in members_data
        if isinstance(m, dict) and m.get("id")
    }

    out: list[dict[str, Any]] = []
    for mid in members:
        if not isinstance(mid, str) or not mid.strip():
            continue
        info = data_map.get(mid, {})
        out.append({
            "id": mid,
            "name": info.get("fullName", "unknown"),
            "username": info.get("username"),
            "source_key": f"trello:assignee:{board_id}:{card_id}:{mid}",
        })

    return out


def idem_key_for_card(entity: dict[str, Any]) -> str:
    """Return the idempotency source_key for a card entity.

    Returns the trello:{board_id}:{card_id} source_key from the entity's
    source_keys list, or empty string if not present.
    """
    for key in entity.get("source_keys", []):
        if key.startswith("trello:"):
            return key
    return ""


def fetch_and_build(
    days: int = DEFAULT_LOOKBACK_DAYS,
    mapper_version: str = MAPPER_VERSION,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch cards from Trello and build canonical entities + assignees.

    Returns:
        (card_entities, assignee_records)
    """
    raw_cards = _fetch_from_trello(days)
    entities: list[dict[str, Any]] = []
    all_assignees: list[dict[str, Any]] = []
    for raw in raw_cards:
        try:
            entity = build_card_entity(raw, mapper_version)
        except ValueError:
            continue
        entities.append(entity)
        assignees = extract_assignees(raw)
        all_assignees.extend(assignees)
    return entities, all_assignees
