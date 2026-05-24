import pytest
from vault.qw2.router import route_decision

@pytest.mark.parametrize("source,decision,expected_topic", [
    ("tldv", {"text": "Status BAT reunião sobre erros"}, "bat-conectabot-observability.md"),
    ("tldv", {"text": "Discussão sobre TLDV e memory agent"}, "livy-memory-agent.md"),
    ("tldv", {"text": "Projeto Forge plataforma nova"}, "forge-platform.md"),
    ("trello", {"text": "Card title not relevant", "board_name": "Delphos"}, "delphos-video-vistoria.md"),
    ("trello", {"text": "Card on Forge board", "board_name": "Forge"}, "forge-platform.md"),
    ("github", {"text": "PR sobre Evo sistema"}, "livy-evo.md"),
    ("tldv", {"text": "Algo que não matches nada"}, "general.md"),  # fallback → DM
])
def test_route_decision(source, decision, expected_topic):
    decision["source"] = source
    result = route_decision(decision)
    assert result["topic"] == expected_topic
    assert "routing_failed" in result

# Also test routing_failed flag
@pytest.mark.parametrize("source,decision,expected_topic,expected_rf", [
    ("tldv", {"text": "Status BAT"}, "bat-conectabot-observability.md", False),
    ("tldv", {"text": "Algo random sem match"}, "general.md", True),
])
def test_routing_failed_flag(source, decision, expected_topic, expected_rf):
    decision["source"] = source
    result = route_decision(decision)
    assert result["topic"] == expected_topic
    assert result["routing_failed"] == expected_rf
