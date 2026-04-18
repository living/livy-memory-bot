"""Tests for vault/research/trello_client.py — Trello polling client."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from vault.research.trello_client import TrelloClient, TrelloAPIError


def test_fetch_cards_since_uses_board_ids_and_returns_normalized_items(mocker):
    """fetch_events_since must poll all board_ids and return a list."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [
        {
            "id": "a1",
            "type": "createCard",
            "date": "2026-04-18T10:00:00.000Z",
            "data": {
                "card": {"id": "c1", "name": "Test Card"},
                "list": {"id": "l1", "name": "To Do"},
                "board": {"id": "b1", "name": "Test Board"},
            },
            "memberCreator": {"id": "m1", "fullName": "John Doe"},
        }
    ]

    client = TrelloClient(api_key="k", token="t", board_ids=["b1"])
    events = client.fetch_events_since(None)

    assert isinstance(events, list)
    assert len(events) == 1
    assert events[0]["source"] == "trello"
    assert events[0]["event_type"] == "trello:card_created"


def test_fetch_board_actions_raises_trello_api_error_on_non_200(mocker):
    """Non-200 responses raise TrelloAPIError (not silent [])."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 429
    mock_get.return_value.text = "Rate limit exceeded"

    client = TrelloClient(api_key="k", token="t", board_ids=["b1"])

    with pytest.raises(TrelloAPIError) as exc_info:
        client.fetch_events_since(None)

    assert exc_info.value.board_id == "b1"
    assert exc_info.value.status_code == 429


def test_fetch_events_since_filters_by_since_date(mocker):
    """When last_seen_at is provided, only return actions after that date."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [
        {"id": "a1", "type": "createCard", "date": "2026-04-18T10:00:00.000Z", "data": {"card": {"id": "c1", "name": "Test Card"}}}
    ]

    client = TrelloClient(api_key="k", token="t", board_ids=["b1"])
    events = client.fetch_events_since("2026-04-18T09:00:00.000Z")

    # Should have called with since param
    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert "since" in call_args.kwargs["params"]


def test_normalize_action_maps_create_card_to_trello_card_created():
    """A createCard action normalizes to event_type trello:card_created."""
    client = TrelloClient(api_key="k", token="t", board_ids=[])
    action = {
        "id": "a1",
        "type": "createCard",
        "date": "2026-04-18T10:00:00.000Z",
        "data": {
            "card": {"id": "c1", "name": "Test Card"},
            "list": {"id": "l1", "name": "To Do"},
            "board": {"id": "b1", "name": "Test Board"}
        },
        "memberCreator": {"id": "m1", "fullName": "John Doe"}
    }
    event = client.normalize_action(action)
    assert event["event_type"] == "trello:card_created"
    assert event["source"] == "trello"
    assert event["card_id"] == "c1"


def test_normalize_action_maps_update_card_to_trello_card_updated():
    """An updateCard action normalizes to event_type trello:card_updated."""
    client = TrelloClient(api_key="k", token="t", board_ids=[])
    action = {
        "id": "a2",
        "type": "updateCard",
        "date": "2026-04-18T11:00:00.000Z",
        "data": {
            "card": {"id": "c1", "name": "Updated Card"},
            "list": {"id": "l1", "name": "Doing"},
            "board": {"id": "b1", "name": "Test Board"}
        }
    }
    event = client.normalize_action(action)
    assert event["event_type"] == "trello:card_updated"


def test_normalize_action_maps_move_list_to_trello_list_moved():
    """A moveListFromBoard action normalizes to event_type trello:list_moved."""
    client = TrelloClient(api_key="k", token="t", board_ids=[])
    action = {
        "id": "a3",
        "type": "moveListFromBoard",
        "date": "2026-04-18T12:00:00.000Z",
        "data": {
            "list": {"id": "l1", "name": "Done"},
            "board": {"id": "b1", "name": "Test Board"}
        }
    }
    event = client.normalize_action(action)
    assert event["event_type"] == "trello:list_moved"


def test_normalize_action_maps_add_member_to_trello_member_added():
    """A addMemberToCard action normalizes to event_type trello:member_added."""
    client = TrelloClient(api_key="k", token="t", board_ids=[])
    action = {
        "id": "a4",
        "type": "addMemberToCard",
        "date": "2026-04-18T13:00:00.000Z",
        "data": {
            "card": {"id": "c1", "name": "Test Card"},
            "member": {"id": "m1", "fullName": "Jane Doe"}
        }
    }
    event = client.normalize_action(action)
    assert event["event_type"] == "trello:member_added"


def test_normalize_action_maps_remove_member_to_trello_member_removed():
    """A removeMemberFromCard action normalizes to event_type trello:member_removed."""
    client = TrelloClient(api_key="k", token="t", board_ids=[])
    action = {
        "id": "a5",
        "type": "removeMemberFromCard",
        "date": "2026-04-18T14:00:00.000Z",
        "data": {
            "card": {"id": "c1", "name": "Test Card"},
            "member": {"id": "m1", "fullName": "Jane Doe"}
        }
    }
    event = client.normalize_action(action)
    assert event["event_type"] == "trello:member_removed"


def test_normalize_action_falls_back_to_trello_raw_type_for_unknown_action():
    """Unknown action types fall back to 'trello:<raw_type>' per documented behavior."""
    client = TrelloClient(api_key="k", token="t", board_ids=[])
    action = {
        "id": "a99",
        "type": "commentCard",
        "date": "2026-04-18T15:00:00.000Z",
        "data": {"card": {"id": "c1", "name": "Test Card"}},
    }
    event = client.normalize_action(action)
    assert event["event_type"] == "trello:commentCard"
    assert event["source"] == "trello"


def test_client_raises_environment_error_when_api_key_missing(mocker):
    """Missing TRELLO_API_KEY raises EnvironmentError."""
    env = {"TRELLO_TOKEN": "t"}
    mocker.patch.dict(os.environ, env, clear=True)
    with pytest.raises(EnvironmentError, match="TRELLO_API_KEY"):
        TrelloClient()


def test_client_raises_environment_error_when_token_missing(mocker):
    """Missing TRELLO_TOKEN raises EnvironmentError."""
    env = {"TRELLO_API_KEY": "k"}
    mocker.patch.dict(os.environ, env, clear=True)
    with pytest.raises(EnvironmentError, match="TRELLO_TOKEN"):
        TrelloClient()


def test_client_raises_environment_error_when_both_missing(mocker):
    """Missing both credentials raises EnvironmentError."""
    mocker.patch.dict(os.environ, {}, clear=True)
    with pytest.raises(EnvironmentError):
        TrelloClient(api_key="", token="")


def test_fetch_events_since_returns_normalized_events(mocker):
    """fetch_events_since should return events in internal format."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [
        {
            "id": "a1",
            "type": "createCard",
            "date": "2026-04-18T10:00:00.000Z",
            "data": {
                "card": {"id": "c1", "name": "Test Card"},
                "list": {"id": "l1", "name": "To Do"},
                "board": {"id": "b1", "name": "Test Board"}
            },
            "memberCreator": {"id": "m1", "fullName": "John Doe"}
        }
    ]

    client = TrelloClient(api_key="k", token="t", board_ids=["b1"])
    events = client.fetch_events_since(None)

    assert len(events) == 1
    assert events[0]["source"] == "trello"
    assert events[0]["event_type"] == "trello:card_created"


def test_fetch_events_since_uses_env_vars(mocker):
    """TrelloClient should accept board_ids from constructor."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = []

    # Pass board_ids directly to constructor
    client = TrelloClient(api_key="k", token="t", board_ids=["b1", "b2"])
    client.fetch_events_since(None)

    # Should have made 2 calls (one per board)
    assert mock_get.call_count == 2
