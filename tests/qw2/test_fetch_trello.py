"""Tests for fetch_trello_snapshots — uses ParsedTrelloCard dataclass."""
from unittest.mock import patch, MagicMock
from vault.research.trello_parsers import ParsedTrelloCard
from vault.qw2.fetch_trello import trello_card_passes_filter, fetch_trello_snapshots

def test_trello_card_passes_filter_accepts_dataclass():
    card = ParsedTrelloCard(
        card_id="c1", card_name="Deploy UAT - Voice RLSE0109469",
        card_url="https://trello.com/c/ABC", board_id="b1", list_name="Concluído",
        labels=[], due_date=None,
        github_links=["https://github.com/living/livy-forge/pull/42"],
        hours_logged=4.5, last_activity="2026-05-24T12:00:00Z",
    )
    assert trello_card_passes_filter(card) is True

def test_trello_card_passes_filter_rejects_short_name():
    card = ParsedTrelloCard(
        card_id="c2", card_name="Done", card_url="",
        board_id="b1", list_name="Concluído",
        labels=[], due_date=None,
        github_links=[], hours_logged=0.0, last_activity=None,
    )
    assert trello_card_passes_filter(card) is False

@patch("vault.qw2.fetch_trello.TrelloClient")
def test_fetches_all_boards_no_allowlist(mock_client_cls):
    mock_client = MagicMock()
    mock_client.get_normalized_cards.return_value = [
        ParsedTrelloCard(
            card_id="c1", card_name="Deploy UAT", card_url="https://trello.com/c/C1",
            board_id="board_bat", list_name="Concluído",
            labels=["deploy"], due_date=None,
            github_links=["https://github.com/living/livy-forge/pull/42"],
            hours_logged=4.5, last_activity="2026-05-24T12:00:00Z",
        ),
        ParsedTrelloCard(
            card_id="c2", card_name="Bugfix login", card_url="https://trello.com/c/C2",
            board_id="board_delphos", list_name="Done",
            labels=["bug"], due_date=None,
            github_links=[], hours_logged=2.0, last_activity="2026-05-23T12:00:00Z",
        ),
    ]
    mock_client_cls.return_value = mock_client

    with patch("vault.qw2.fetch_trello._fetch_board_name", return_value="BAT"):
        snapshots, cursors = fetch_trello_snapshots(since_days=30)

    assert len(snapshots) == 2
    assert snapshots[0]["github_pr_url"] == "https://github.com/living/livy-forge/pull/42"
    assert snapshots[0]["hours_logged"] == 4.5
    assert snapshots[0]["board_name"] == "BAT"
