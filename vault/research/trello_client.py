"""Trello polling client for board events (Stream T).

Fetches actions and cards from configured Trello boards via the REST API.
Normalizes Trello events into the internal event format.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import requests

from vault.research.trello_parsers import ParsedTrelloCard, parse_trello_card

logger = logging.getLogger(__name__)


# Trello API base URL
TRELLO_API_BASE = "https://api.trello.com/1"

# Mapping from Trello action types to internal event types
ACTION_TYPE_MAP = {
    "createCard": "trello:card_created",
    "updateCard": "trello:card_updated",
    "moveListFromBoard": "trello:list_moved",
    "addMemberToCard": "trello:member_added",
    "removeMemberFromCard": "trello:member_removed",
}


class TrelloAPIError(Exception):
    """Raised when the Trello API returns a non-200 response."""

    def __init__(self, board_id: str, status_code: int, response_text: str = "") -> None:
        self.board_id = board_id
        self.status_code = status_code
        super().__init__(
            f"Trello API error for board {board_id}: HTTP {status_code}{f' - {response_text[:100]}' if response_text else ''}"
        )


class TrelloClient:
    """Client for polling Trello boards for activity.

    Args:
        api_key: Trello API key (or set TRELLO_API_KEY env var)
        token: Trello token (or set TRELLO_TOKEN env var)
        board_ids: List of Trello board IDs to poll

    Raises:
        EnvironmentError: if TRELLO_API_KEY or TRELLO_TOKEN is not set
        TrelloAPIError: if a board API call returns a non-200 response
    """

    def __init__(
        self,
        api_key: str | None = None,
        token: str | None = None,
        board_ids: list[str] | None = None,
    ) -> None:
        # Allow constructor overrides, but env vars are the primary source
        self.api_key = api_key or os.environ.get("TRELLO_API_KEY", "")
        self.token = token or os.environ.get("TRELLO_TOKEN", "")

        env_board_ids = os.environ.get("TRELLO_BOARD_IDS", "")
        raw_board_ids = board_ids if board_ids is not None else env_board_ids.split(",")
        self.board_ids = [b.strip() for b in raw_board_ids if b and b.strip()]

        # Validate required credentials
        if not self.api_key or not self.token:
            raise EnvironmentError("TRELLO_API_KEY and TRELLO_TOKEN must be set")

    def fetch_events_since(self, last_seen_at: str | None) -> list[dict[str, Any]]:
        """Fetch events from all configured boards since last_seen_at.

        Args:
            last_seen_at: ISO timestamp string; if None, fetches all recent actions

        Returns:
            List of normalized event dicts with source='trello' and event_type in
            trello:card_created | card_updated | list_moved | member_added | member_removed
        """
        all_events: list[dict[str, Any]] = []

        for board_id in self.board_ids:
            events = self._fetch_board_actions(board_id, last_seen_at)
            all_events.extend(events)

        return all_events

    def _fetch_board_actions(
        self, board_id: str, last_seen_at: str | None
    ) -> list[dict[str, Any]]:
        """Fetch actions for a single board, optionally filtered by since date."""
        params: dict[str, Any] = {
            "key": self.api_key,
            "token": self.token,
            "filter": "createCard,updateCard,moveListFromBoard,addMemberToCard,removeMemberFromCard",
        }

        if last_seen_at:
            params["since"] = last_seen_at

        url = f"{TRELLO_API_BASE}/boards/{board_id}/actions"
        response = requests.get(url, params=params, timeout=30)

        if response.status_code != 200:
            raise TrelloAPIError(board_id, response.status_code, response.text)

        actions = response.json()
        return [self.normalize_action(action) for action in actions]

    def get_normalized_cards(self, last_seen_at: str | None = None) -> list[ParsedTrelloCard]:
        """Fetch and normalize cards from configured boards.

        Args:
            last_seen_at: ISO timestamp string; when provided, returns only cards
                with dateLastActivity >= last_seen_at.

        Returns:
            Parsed Trello cards enriched with GitHub links and hours metadata.
        """
        normalized_cards: list[ParsedTrelloCard] = []

        threshold_dt: datetime | None = None
        if last_seen_at:
            try:
                threshold_dt = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
            except ValueError:
                logger.warning("Invalid last_seen_at timestamp %r; disabling date filter", last_seen_at)

        for board_id in self.board_ids:
            url = f"{TRELLO_API_BASE}/boards/{board_id}/cards"
            params: dict[str, Any] = {
                "key": self.api_key,
                "token": self.token,
                "fields": "id,name,url,idBoard,desc,labels,due,dateLastActivity,idList",
            }

            response = requests.get(url, params=params, timeout=30)
            if response.status_code != 200:
                raise TrelloAPIError(board_id, response.status_code, response.text)

            cards = response.json()
            list_name_cache: dict[str, str] = {}

            for card in cards:
                if threshold_dt is not None:
                    last_activity = card.get("dateLastActivity")
                    if not last_activity:
                        continue

                    card_dt: datetime | None = None
                    try:
                        card_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                    except ValueError:
                        logger.warning(
                            "Invalid card dateLastActivity for card %s: %r; including card anyway",
                            card.get("id"),
                            last_activity,
                        )

                    if card_dt is not None and card_dt < threshold_dt:
                        continue

                list_id = card.get("idList", "")
                if list_id not in list_name_cache:
                    list_name_cache[list_id] = self._fetch_list_name(list_id)
                list_name = list_name_cache[list_id]

                normalized_cards.append(parse_trello_card(card, list_name))

        return normalized_cards

    def get_card_comments(self, card_id: str) -> list[dict[str, Any]]:
        """Fetch commentCard actions for a card.

        Returns a list of dicts with at least {id, date, data: {text, creator: {fullName}}}.
        """
        params: dict[str, Any] = {
            "key": self.api_key,
            "token": self.token,
            "filter": "commentCard",
        }
        url = f"{TRELLO_API_BASE}/cards/{card_id}/actions"
        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code != 200:
                logger.warning("Failed to fetch comments for card %s: HTTP %s", card_id, response.status_code)
                return []
            return response.json() or []
        except Exception as exc:
            logger.warning("Exception fetching comments for card %s: %s", card_id, exc)
            return []

    def get_card_checklists(self, card_id: str) -> list[dict[str, Any]]:
        """Fetch checklists for a card.

        Returns a list of dicts with {id, name, checkItems: [{id, name, state}]}.
        """
        params: dict[str, Any] = {
            "key": self.api_key,
            "token": self.token,
        }
        url = f"{TRELLO_API_BASE}/cards/{card_id}/checklists"
        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code != 200:
                logger.warning("Failed to fetch checklists for card %s: HTTP %s", card_id, response.status_code)
                return []
            return response.json() or []
        except Exception as exc:
            logger.warning("Exception fetching checklists for card %s: %s", card_id, exc)
            return []

    def _fetch_list_name(self, list_id: str) -> str:
        """Fetch Trello list name from list id."""
        if not list_id:
            return "unknown"

        url = f"{TRELLO_API_BASE}/lists/{list_id}"
        params = {
            "key": self.api_key,
            "token": self.token,
            "fields": "name",
        }
        response = requests.get(url, params=params, timeout=30)

        if response.status_code != 200:
            logger.warning("Failed to fetch Trello list name for %s", list_id)
            return "unknown"

        return response.json().get("name", "unknown")

    def normalize_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """Convert a Trello action dict into the internal event format.

        Args:
            action: Raw Trello action object from the API

        Returns:
            Normalized event dict with fields:
                - source: always "trello"
                - event_type: mapped from action type
                - action_id: original Trello action ID
                - card_id: card ID if present
                - list_id: list ID if present
                - board_id: board ID if present
                - member_id: member ID if present
                - timestamp: ISO timestamp of the action
                - raw: original action data
        """
        action_type = action.get("type", "")
        # Known types are in ACTION_TYPE_MAP; unknown types fall back to
        # "trello:<raw_type>" so the pipeline can still track them.
        event_type = ACTION_TYPE_MAP.get(action_type, f"trello:{action_type}")
        data = action.get("data", {})

        event: dict[str, Any] = {
            "source": "trello",
            "event_type": event_type,
            "action_id": action.get("id"),
            "timestamp": action.get("date"),
            "raw": action,
        }

        # Extract card info if present
        card = data.get("card")
        if card:
            event["card_id"] = card.get("id")
            event["card_name"] = card.get("name")

        # Extract list info if present
        lst = data.get("list")
        if lst:
            event["list_id"] = lst.get("id")
            event["list_name"] = lst.get("name")

        # Extract board info if present
        board = data.get("board")
        if board:
            event["board_id"] = board.get("id")
            event["board_name"] = board.get("name")

        # Extract member info if present
        member = data.get("member") or data.get("memberAdded") or data.get("memberRemoved")
        if member:
            event["member_id"] = member.get("id")
            event["member_name"] = member.get("fullName")

        # Member creator (actor)
        member_creator = action.get("memberCreator")
        if member_creator:
            event["actor_id"] = member_creator.get("id")
            event["actor_name"] = member_creator.get("fullName")

        return event
