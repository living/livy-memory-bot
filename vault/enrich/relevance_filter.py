"""Filter enrichment_context to only items relevant to the meeting's project.

Uses meeting title → project mapping and board_id → project mapping
to determine relevance.
"""
from __future__ import annotations

import re
from typing import Any

# Meeting title pattern → relevant board_ids
_PROJECT_BOARD_MAP = {
    "BAT": {
        "patterns": [r"Status\s+Kaba", r"BAT", r"Conecta.?Bot", r"voice", r"Voice"],
        "board_ids": {"66e99655f8e85b6698d3d784", "69a086a99bb2eb087f43ec75"},
    },
    "Delphos": {
        "patterns": [r"Delphos", r"Robô.*OCR", r"Elcano"],
        "board_ids": {"6697cdb0b388dea00a594901", "6964f88f5b00feaf4078988d"},
    },
    "B3": {
        "patterns": [r"Daily.*Operações.*B3", r"B3.*Billing", r"ECB"],
        "board_ids": {"5d85184c0c352d33748609f0", "60f058aa0bebde2f6e4e4b9c", "660ff54fc58cbcea05710f15"},
    },
    "Imobi": {
        "patterns": [r"Cadência\s+4D\s+imobi", r"4D\s+[Ii]mobi"],
        "board_ids": set(),
    },
}


def _detect_project(title: str) -> str | None:
    """Detect which project a meeting title refers to."""
    for project, config in _PROJECT_BOARD_MAP.items():
        for pattern in config["patterns"]:
            if re.search(pattern, title, re.IGNORECASE):
                return project
    return None


def filter_enrichment_context(
    context: dict[str, Any],
    meeting_title: str = "",
    max_cards: int = 20,
) -> dict[str, Any]:
    """Filter enrichment_context to only relevant items.

    If no project is detected from the title, returns all items (conservative).
    If a project is detected, only includes cards/PRs from matching boards/repos.
    """
    project = _detect_project(meeting_title)
    if not project:
        return context

    board_ids = _PROJECT_BOARD_MAP.get(project, {}).get("board_ids", set())
    filtered = dict(context)

    if "trello" in filtered and board_ids:
        cards = filtered["trello"].get("cards", [])
        filtered["trello"] = {
            **filtered["trello"],
            "cards": [c for c in cards if c.get("board_id") in board_ids][:max_cards],
        }

    return filtered
