from vault.enrich.relevance_filter import filter_enrichment_context


def test_filter_cards_by_board_relevance():
    """Only cards from boards matching the meeting project should be included."""
    context = {
        "trello": {
            "cards": [
                {"id": "1", "name": "Voice deploy", "board_id": "66e99655f8e85b6698d3d784"},
                {"id": "2", "name": "Delphos OCR setup", "board_id": "6697cdb0b388dea00a594901"},
                {"id": "3", "name": "Daily meeting card", "board_id": "66e99655f8e85b6698d3d784"},
            ]
        }
    }

    filtered = filter_enrichment_context(context, meeting_title="Status Kaba - BAT - BOT")
    bat_cards = filtered["trello"]["cards"]
    assert len(bat_cards) == 2
    assert all(c["board_id"] == "66e99655f8e85b6698d3d784" for c in bat_cards)


def test_filter_keeps_all_when_no_match():
    """If no project detected, keep all cards (conservative)."""
    context = {
        "trello": {
            "cards": [
                {"id": "1", "name": "Card A", "board_id": "aaa"},
                {"id": "2", "name": "Card B", "board_id": "bbb"},
            ]
        }
    }
    filtered = filter_enrichment_context(context, meeting_title="Random Meeting")
    assert len(filtered["trello"]["cards"]) == 2


def test_filter_delphos_project():
    """Delphos meetings only get Delphos board cards."""
    context = {
        "trello": {
            "cards": [
                {"id": "1", "name": "Voice deploy", "board_id": "66e99655f8e85b6698d3d784"},
                {"id": "2", "name": "Delphos OCR setup", "board_id": "6697cdb0b388dea00a594901"},
            ]
        }
    }
    filtered = filter_enrichment_context(context, meeting_title="Delphos Video Vistoria Review")
    assert len(filtered["trello"]["cards"]) == 1
    assert filtered["trello"]["cards"][0]["name"] == "Delphos OCR setup"
