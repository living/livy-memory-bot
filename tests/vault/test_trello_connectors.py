from vault.research.trello_client import TrelloClient
from vault.research.trello_parsers import parse_trello_card


def test_trello_client_initialization():
    client = TrelloClient(api_key="key123", token="tok123", board_ids=["b1", "b2"])

    assert client.api_key == "key123"
    assert client.token == "tok123"
    assert client.board_ids == ["b1", "b2"]


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
