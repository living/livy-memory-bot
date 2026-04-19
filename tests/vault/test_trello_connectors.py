from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vault.research.trello_client import TrelloClient, TrelloAPIError
from vault.research.trello_parsers import (
    ParsedTrelloCard,
    _extract_hours,
    card_to_claims,
    parse_trello_card,
)


# ---------------------------------------------------------------------------
# TrelloClient initialization
# ---------------------------------------------------------------------------

def test_trello_client_initialization():
    client = TrelloClient(api_key="key123", token="tok123", board_ids=["b1", "b2"])

    assert client.api_key == "key123"
    assert client.token == "tok123"
    assert client.board_ids == ["b1", "b2"]


def test_trello_client_board_ids_defaults_to_empty_list(mocker):
    """board_ids should default to [] when env var is absent and arg not provided."""
    mocker.patch.dict("os.environ", {}, clear=False)
    mocker.patch("os.environ.get", side_effect=lambda k, d=None: d if k == "TRELLO_BOARD_IDS" else ("key123" if k == "TRELLO_API_KEY" else ("tok123" if k == "TRELLO_TOKEN" else d)))

    client = TrelloClient(api_key="key123", token="tok123")
    assert client.board_ids == []


# ---------------------------------------------------------------------------
# parse_trello_card
# ---------------------------------------------------------------------------

def test_parse_trello_card_extracts_github_links():
    card = {
        "id": "card_1",
        "name": "Implement connector",
        "url": "https://trello.com/c/card_1",
        "idBoard": "board_1",
        "desc": "Relaciona com https://github.com/living/livy-memory-bot/pull/42",
        "labels": [{"name": "backend"}],
        "due": "2026-04-19T10:00:00.000Z",
        "dateLastActivity": "2026-04-19T12:00:00.000Z",
    }

    parsed = parse_trello_card(card, list_name="Doing")

    assert parsed.card_id == "card_1"
    assert parsed.list_name == "Doing"
    assert parsed.github_links == ["https://github.com/living/livy-memory-bot/pull/42"]


def test_parse_trello_card_does_not_capture_suffixes_like_quotes_or_brackets():
    """GitHub URLs followed by punctuation should not include trailing punctuation."""
    card = {
        "id": "card_2",
        "name": "Test",
        "url": "https://trello.com/c/card_2",
        "idBoard": "board_1",
        "desc": "See https://github.com/living/livy/pull/1\" and https://github.com/living/delphos/issues/2' and https://github.com/living/forge/tree/main> or https://github.com/living/bat/pull/99.",
        "labels": [],
        "dateLastActivity": "2026-04-19T12:00:00.000Z",
    }

    parsed = parse_trello_card(card, list_name="Doing")

    # Each URL should be clean — no trailing " ' . > characters
    for link in parsed.github_links:
        assert link[-1] not in ('"', "'", ".", ">"), f"URL should not end with punctuation: {link}"


def test_parse_trello_card_extracts_multiple_github_links():
    card = {
        "id": "card_3",
        "name": "Multi-link card",
        "url": "https://trello.com/c/card_3",
        "idBoard": "board_1",
        "desc": "PR https://github.com/living/livy-memory-bot/pull/42 e issue https://github.com/living/livy-memory-bot/issues/7",
        "labels": [],
        "dateLastActivity": "2026-04-19T12:00:00.000Z",
    }

    parsed = parse_trello_card(card, list_name="Doing")

    assert len(parsed.github_links) == 2
    assert "pull/42" in parsed.github_links[0]
    assert "issues/7" in parsed.github_links[1]


# ---------------------------------------------------------------------------
# _extract_hours
# ---------------------------------------------------------------------------

def test_extract_hours_from_desc_direct_number():
    """hours_logged field with a plain number is parsed correctly."""
    card = {"hours_logged": 3.5, "desc": ""}
    assert _extract_hours(card) == 3.5


def test_extract_hours_from_desc_comma_separator():
    """hours_logged with comma decimal separator is normalized."""
    card = {"hours_logged": "2,5", "desc": ""}
    assert _extract_hours(card) == 2.5


def test_extract_hours_from_desc_invalid_value():
    """hours_logged with non-numeric value falls back to 0."""
    card = {"hours_logged": "not-a-number", "desc": ""}
    assert _extract_hours(card) == 0.0


def test_extract_hours_from_desc_absent():
    """When hours_logged is absent, returns 0."""
    card = {"desc": ""}
    assert _extract_hours(card) == 0.0


def test_extract_hours_from_desc_regex_hours_equals():
    """hours_logged: pattern in desc is parsed correctly."""
    card = {"desc": "hours_logged: 4.5 today."}
    assert _extract_hours(card) == 4.5


def test_extract_hours_from_desc_regex_horas_colon():
    """horas: pattern in desc is parsed correctly."""
    card = {"desc": "horas: 6"}
    assert _extract_hours(card) == 6.0


def test_extract_hours_from_desc_regex_hours_logged_underscore():
    """hours_logged pattern with underscore is parsed."""
    card = {"desc": "hours_logged = 3"}
    assert _extract_hours(card) == 3.0


# ---------------------------------------------------------------------------
# card_to_claims
# ---------------------------------------------------------------------------

def test_card_to_claims_generates_status_and_linkage_claims():
    """card_to_claims returns a status claim plus one linkage claim per GitHub link."""
    parsed = ParsedTrelloCard(
        card_id="card_1",
        card_name="Implement feature X",
        card_url="https://trello.com/c/card_1",
        board_id="board_1",
        list_name="Doing",
        labels=["backend"],
        due_date="2026-04-20T10:00:00.000Z",
        github_links=["https://github.com/living/livy/pull/42"],
        hours_logged=2.5,
        last_activity="2026-04-19T12:00:00.000Z",
    )

    claims = card_to_claims(parsed)

    assert len(claims) == 2

    status = claims[0]
    assert status["source"] == "trello"
    assert status["claim_type"] == "status"
    assert "Doing" in status["text"]
    assert status["metadata"]["hours_logged"] == 2.5

    linkage = claims[1]
    assert linkage["claim_type"] == "linkage"
    assert "github" in linkage["metadata"]["link_url"]


def test_card_to_claims_with_no_github_links_returns_status_only():
    """A card with no GitHub links produces exactly one status claim."""
    parsed = ParsedTrelloCard(
        card_id="card_2",
        card_name="Solo card",
        card_url="https://trello.com/c/card_2",
        board_id="board_1",
        list_name="To Do",
        labels=[],
        due_date=None,
        github_links=[],
        hours_logged=0.0,
        last_activity=None,
    )

    claims = card_to_claims(parsed)

    assert len(claims) == 1
    assert claims[0]["claim_type"] == "status"


# ---------------------------------------------------------------------------
# TrelloClient._fetch_list_name
# ---------------------------------------------------------------------------

def test_fetch_list_name_success(mocker):
    """_fetch_list_name returns the list name on 200."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"name": "In Progress"}

    client = TrelloClient(api_key="k", token="t", board_ids=["b1"])
    name = client._fetch_list_name("list_id_123")

    assert name == "In Progress"


def test_fetch_list_name_empty_id_returns_unknown(mocker):
    """_fetch_list_name returns 'unknown' when list_id is empty."""
    client = TrelloClient(api_key="k", token="t", board_ids=["b1"])
    name = client._fetch_list_name("")
    assert name == "unknown"


def test_fetch_list_name_http_error_returns_unknown(mocker):
    """_fetch_list_name returns 'unknown' and logs on non-200 response."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 429
    mock_get.return_value.text = "Rate limited"

    client = TrelloClient(api_key="k", token="t", board_ids=["b1"])
    name = client._fetch_list_name("list_bad")

    assert name == "unknown"


# ---------------------------------------------------------------------------
# TrelloClient.get_normalized_cards
# ---------------------------------------------------------------------------

def test_get_normalized_cards_filters_by_last_seen_at(mocker):
    """Cards with dateLastActivity before last_seen_at are excluded."""

    def fake_get(url, params=None, timeout=30):
        resp = MagicMock()
        resp.status_code = 200
        if "/boards/" in url and url.endswith("/cards"):
            resp.json.return_value = [
                {
                    "id": "card_old",
                    "name": "Old card",
                    "url": "https://trello.com/c/card_old",
                    "idBoard": "board_1",
                    "desc": "",
                    "labels": [],
                    "idList": "list_1",
                    "dateLastActivity": "2026-04-18T10:00:00.000Z",
                },
                {
                    "id": "card_new",
                    "name": "New card",
                    "url": "https://trello.com/c/card_new",
                    "idBoard": "board_1",
                    "desc": "",
                    "labels": [],
                    "idList": "list_1",
                    "dateLastActivity": "2026-04-19T14:00:00.000Z",
                },
            ]
        else:
            resp.json.return_value = {"name": "Doing"}
        return resp

    mocker.patch("requests.get", side_effect=fake_get)

    client = TrelloClient(api_key="k", token="t", board_ids=["board_1"])
    cards = client.get_normalized_cards(last_seen_at="2026-04-19T12:00:00.000Z")

    assert len(cards) == 1
    assert cards[0].card_id == "card_new"


def test_get_normalized_cards_invalid_last_seen_at_disables_filter(mocker):
    """Invalid last_seen_at timestamp does not crash — filter is disabled."""

    def fake_get(url, params=None, timeout=30):
        resp = MagicMock()
        resp.status_code = 200
        if "/boards/" in url and url.endswith("/cards"):
            resp.json.return_value = [
                {
                    "id": "card_1",
                    "name": "Any card",
                    "url": "https://trello.com/c/card_1",
                    "idBoard": "board_1",
                    "desc": "",
                    "labels": [],
                    "idList": "list_1",
                    "dateLastActivity": "2026-04-19T12:00:00.000Z",
                }
            ]
        else:
            resp.json.return_value = {"name": "To Do"}
        return resp

    mocker.patch("requests.get", side_effect=fake_get)

    client = TrelloClient(api_key="k", token="t", board_ids=["board_1"])
    cards = client.get_normalized_cards(last_seen_at="not-a-valid-timestamp")
    assert len(cards) == 1


def test_get_normalized_cards_invalid_card_date_falls_back(mocker):
    """Card with malformed dateLastActivity is included safely (no crash)."""

    def fake_get(url, params=None, timeout=30):
        resp = MagicMock()
        resp.status_code = 200
        if "/boards/" in url and url.endswith("/cards"):
            resp.json.return_value = [
                {
                    "id": "card_bad_date",
                    "name": "Bad date card",
                    "url": "https://trello.com/c/card_bad_date",
                    "idBoard": "board_1",
                    "desc": "",
                    "labels": [],
                    "idList": "list_1",
                    "dateLastActivity": "not-a-date",
                }
            ]
        else:
            resp.json.return_value = {"name": "Doing"}
        return resp

    mocker.patch("requests.get", side_effect=fake_get)

    client = TrelloClient(api_key="k", token="t", board_ids=["board_1"])
    cards = client.get_normalized_cards(last_seen_at="2026-04-19T12:00:00.000Z")
    assert len(cards) == 1


def test_get_normalized_cards_caches_list_names(mocker):
    """Multiple cards with the same idList share one _fetch_list_name call."""
    board_resp = MagicMock(status_code=200)
    board_resp.json.return_value = [
        {
            "id": "card_1",
            "name": "Card 1",
            "url": "https://trello.com/c/card_1",
            "idBoard": "board_1",
            "desc": "",
            "labels": [],
            "idList": "list_shared",
            "dateLastActivity": "2026-04-19T12:00:00.000Z",
        },
        {
            "id": "card_2",
            "name": "Card 2",
            "url": "https://trello.com/c/card_2",
            "idBoard": "board_1",
            "desc": "",
            "labels": [],
            "idList": "list_shared",
            "dateLastActivity": "2026-04-19T13:00:00.000Z",
        },
        {
            "id": "card_3",
            "name": "Card 3",
            "url": "https://trello.com/c/card_3",
            "idBoard": "board_1",
            "desc": "",
            "labels": [],
            "idList": "list_other",
            "dateLastActivity": "2026-04-19T14:00:00.000Z",
        },
    ]

    list_resp = MagicMock(status_code=200)
    list_resp.json.return_value = {"name": "Any List"}

    mock_get = mocker.patch("requests.get", side_effect=[board_resp, list_resp, list_resp])

    client = TrelloClient(api_key="k", token="t", board_ids=["board_1"])
    cards = client.get_normalized_cards()

    # 1 call for board cards + 2 for distinct list ids (shared + other)
    assert mock_get.call_count == 3
    assert len(cards) == 3


def test_get_normalized_cards_raises_on_http_error(mocker):
    """Non-200 response from board cards endpoint raises TrelloAPIError."""
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 500
    mock_get.return_value.text = "Internal Server Error"

    client = TrelloClient(api_key="k", token="t", board_ids=["board_fail"])

    with pytest.raises(TrelloAPIError) as exc_info:
        client.get_normalized_cards()

    assert exc_info.value.board_id == "board_fail"
    assert exc_info.value.status_code == 500

