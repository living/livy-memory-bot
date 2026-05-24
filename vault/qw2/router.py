"""Inference pass: map a decision to a topic file."""
from __future__ import annotations

from typing import Any

# Keyword → topic file
ROUTING_RULES: list[tuple[list[str], str]] = [
    (["bat", "kaba", "bot", "b3", "balc", "balcao"], "bat-conectabot-observability.md"),
    (["tldv", "memory", "livy", "openclaw", "gateway"], "livy-memory-agent.md"),
    (["delphos", "vistoria", "cerc", "interop"], "delphos-video-vistoria.md"),
    (["forge"], "forge-platform.md"),
    (["evo", "evolution"], "livy-evo.md"),
    (["4d", "imobi"], "4d-imobi.md"),
    (["hydra"], "hydra-evolution.md"),
]

# Trello: explicit board_name → topic routing
TRELLO_BOARD_ROUTING: dict[str, str] = {
    "bat": "bat-conectabot-observability.md",
    "kaba": "bat-conectabot-observability.md",
    "bot": "bat-conectabot-observability.md",
    "b3": "bat-conectabot-observability.md",
    "delphos": "delphos-video-vistoria.md",
    "vistoria": "delphos-video-vistoria.md",
    "forge": "forge-platform.md",
    "evo": "livy-evo.md",
    "4d": "4d-imobi.md",
    "imobi": "4d-imobi.md",
    "hydra": "hydra-evolution.md",
}

def route_decision(decision: dict[str, Any]) -> dict[str, Any]:
    """Route a decision to a topic file. Returns dict with topic, routing_failed."""
    source = decision.get("source", "")
    text_lower = decision.get("text", "").lower()
    source_ref = decision.get("source_ref", "").lower()

    # Trello: check board_name first
    if source == "trello":
        board_name = decision.get("board_name", "").lower()
        for board_key, topic in TRELLO_BOARD_ROUTING.items():
            if board_key in board_name:
                return {"topic": topic, "routing_failed": False, "match": f"board:{board_key}"}

    # Combined text + source_ref for keyword matching
    combined = f"{text_lower} {source_ref}"

    for keywords, topic in ROUTING_RULES:
        for kw in keywords:
            if kw in combined:
                return {"topic": topic, "routing_failed": False, "match": kw}

    # Fallback: general.md + routing failed → DM
    return {"topic": "general.md", "routing_failed": True, "match": None}
