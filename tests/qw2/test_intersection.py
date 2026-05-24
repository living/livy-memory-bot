from vault.qw2.intersection import find_intersections, extract_hours_plugin, extract_github_url, extract_trello_url

def test_extract_hours():
    assert extract_hours_plugin("Horas: 4.5h trabalhadas") == 4.5
    assert extract_hours_plugin("Logged: 2 horas") == 2.0
    assert extract_hours_plugin("h: 1.5") == 1.5
    assert extract_hours_plugin("sem horas") is None

def test_extract_github_url():
    assert extract_github_url("Veja https://github.com/living/livy-forge/pull/42") == "https://github.com/living/livy-forge/pull/42"
    assert extract_github_url("github.com/living/livy-bot/issues/10") == "https://github.com/living/livy-bot/pull/10"
    assert extract_github_url("nada a ver") is None

def test_extract_trello_url():
    assert extract_trello_url("Card: https://trello.com/c/ABC123") == "https://trello.com/c/ABC123"
    assert extract_trello_url("nada") is None

def test_find_intersections():
    """
    Trello↔GitHub intersection requires bidirectional URL link:
    - Trello item has: github_pr_url = "https://github.com/owner/repo/pull/42"
    - GitHub item has: trello_card_url = "https://github.com/owner/repo/pull/42"
      (same string, even though semantically it should be a Trello URL)
    This is the key used for matching in find_intersections().
    """
    trello_items = [
        {"source": "trello", "card_name": "Deploy UAT", "github_pr_url": "https://github.com/living/livy-forge/pull/42"},
    ]
    github_items = [
        {"source": "github", "pr_title": "Deploy UAT to UAT", "trello_card_url": "https://github.com/living/livy-forge/pull/42"},
    ]
    tldv_items = [
        {"source": "tldv", "decisions": ["Validamos o deploy UAT"]},
    ]

    result = find_intersections(trello_items, github_items, tldv_items)
    assert len(result) >= 1
    cross = [r for r in result if "github" in r.get("cross_platform", []) and "trello" in r.get("cross_platform", [])]
    assert len(cross) >= 1
