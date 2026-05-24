# ParsedTrelloCard is a dataclass — fixtures must be dataclass instances
from vault.research.trello_parsers import ParsedTrelloCard

TRELLO_CARD_WITH_PLUGIN = ParsedTrelloCard(
    card_id="card_plugin_test",
    card_name="Deploy UAT - Voice RLSE0109469",
    card_url="https://trello.com/c/ABC123",
    board_id="board_bat",
    list_name="Concluído 🎉",
    labels=["deploy", "voice"],
    due_date=None,
    github_links=["https://github.com/living/livy-forge/pull/42"],
    hours_logged=4.5,
    last_activity="2026-05-24T12:00:00Z",
)

TRELLO_CARD_SHORT_NAME = ParsedTrelloCard(
    card_id="card_short_test",
    card_name="Done",
    card_url="https://trello.com/c/DEF456",
    board_id="board_bat",
    list_name="Concluído 🎉",
    labels=[],
    due_date=None,
    github_links=[],
    hours_logged=0.0,
    last_activity="2026-05-24T12:00:00Z",
)

TRELLO_CARD_NO_USEFUL_DATA = ParsedTrelloCard(
    card_id="card_empty_test",
    card_name="x" * 5,
    card_url="https://trello.com/c/GHI789",
    board_id="board_bat",
    list_name="",
    labels=[],
    due_date=None,
    github_links=[],
    hours_logged=0.0,
    last_activity=None,
)
