"""Fetch Trello cards as operational snapshots — not decisions."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from vault.research.trello_client import TrelloClient, TRELLO_API_BASE

logger = logging.getLogger(__name__)


def trello_card_passes_filter(card: "ParsedTrelloCard") -> bool:
    """Retorna True se o card tem dados operacionais uteis.

    Regras:
    - Card com card_name < 10 chars: skip
    - Card sem list_name e sem last_activity: skip
    - Cards em qualquer lista passam — DONE cards são dados operacionais
    """
    if len(card.card_name) < 10:
        return False
    if not card.list_name and not card.last_activity:
        return False
    return True


def _fetch_board_name(board_id: str, client: TrelloClient) -> str:
    """Fetch board name from Trello API (ParsedTrelloCard só tem board_id, não board_name)."""
    try:
        url = f"{TRELLO_API_BASE}/boards/{board_id}"
        params = {"key": client.api_key, "token": client.token, "fields": "name"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("name", board_id)
    except Exception as e:
        logger.warning("Failed to fetch board name for %s: %s", board_id, e)
    return board_id


def fetch_trello_snapshots(
    since_days: int = 30
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """
    Fetch all Trello cards (no board allowlist) as operational snapshots.
    Returns (snapshots, cursors) where cursors is {board_slug: last_seen_timestamp}.
    """
    try:
        client = TrelloClient()
    except EnvironmentError as e:
        logger.warning(f"Trello not configured: {e}")
        return [], {}

    raw_cards = client.get_normalized_cards()
    snapshots = []
    cursors: dict[str, str] = {}
    board_name_cache: dict[str, str] = {}

    for card in raw_cards:
        if not trello_card_passes_filter(card):
            continue

        last_activity = card.last_activity or ""
        try:
            dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
            if last_activity and dt < cutoff:
                continue
        except Exception:
            pass

        board_id = card.board_id
        if board_id not in board_name_cache:
            board_name_cache[board_id] = _fetch_board_name(board_id, client)
        board_name = board_name_cache[board_id]
        board_slug = _slugify(board_name)

        if last_activity:
            cursors[board_slug] = last_activity

        github_url = card.github_links[0] if card.github_links else None
        hours = card.hours_logged if card.hours_logged > 0 else None

        snapshots.append({
            "source_ref": f"trello:{card.card_id}",
            "board_id": board_id,
            "board_name": board_name,
            "board_slug": board_slug,
            "list_name": card.list_name,
            "card_name": card.card_name,
            "card_url": card.card_url,
            "hours_logged": hours,
            "github_pr_url": github_url,
            "last_activity": last_activity,
            "labels": card.labels,
            "source": "trello",
        })

    return snapshots, cursors


def _slugify(name: str) -> str:
    """Slugify board name for cursor key."""
    return re.sub(r"[^a-z0-9-]", "", name.lower())
