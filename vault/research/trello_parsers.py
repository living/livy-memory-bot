"""Parsers for Trello cards and claim extraction."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


GITHUB_PATTERN = re.compile(r"https?://github\.com/[^\s)\]}]+")
HOURS_PATTERN = re.compile(r"(?:hours?_logged|horas?)\s*[:=]\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)


@dataclass
class ParsedTrelloCard:
    card_id: str
    card_name: str
    card_url: str
    board_id: str
    list_name: str
    labels: list[str]
    due_date: str | None
    github_links: list[str]
    hours_logged: float
    last_activity: str | None


def _extract_hours(card: dict[str, Any]) -> float:
    if isinstance(card.get("hours_logged"), (int, float, str)):
        try:
            return float(str(card["hours_logged"]).replace(",", "."))
        except ValueError:
            pass

    desc = card.get("desc", "") or ""
    match = HOURS_PATTERN.search(desc)
    if match:
        return float(match.group(1).replace(",", "."))

    return 0.0


def parse_trello_card(card: dict[str, Any], list_name: str) -> ParsedTrelloCard:
    """Parse a raw Trello API card into ParsedTrelloCard."""
    description = card.get("desc", "") or ""
    github_links = [link.rstrip(".,;:") for link in GITHUB_PATTERN.findall(description)]

    label_names = [
        label.get("name", "")
        for label in card.get("labels", [])
        if isinstance(label, dict) and label.get("name")
    ]

    return ParsedTrelloCard(
        card_id=card.get("id", ""),
        card_name=card.get("name", ""),
        card_url=card.get("url", ""),
        board_id=card.get("idBoard", ""),
        list_name=list_name,
        labels=label_names,
        due_date=card.get("due"),
        github_links=github_links,
        hours_logged=_extract_hours(card),
        last_activity=card.get("dateLastActivity"),
    )


def card_to_claims(card: ParsedTrelloCard) -> list[dict[str, Any]]:
    """Generate normalized status/linkage claims from a parsed Trello card."""
    claims: list[dict[str, Any]] = [
        {
            "source": "trello",
            "claim_type": "status",
            "entity_type": "project",
            "entity_id": card.card_id,
            "text": f"Card '{card.card_name}' está em '{card.list_name}'",
            "event_timestamp": card.last_activity,
            "source_ref": {"source_id": card.card_id, "url": card.card_url},
            "metadata": {
                "board_id": card.board_id,
                "labels": card.labels,
                "due_date": card.due_date,
                "hours_logged": card.hours_logged,
            },
        }
    ]

    for github_link in card.github_links:
        claims.append(
            {
                "source": "trello",
                "claim_type": "linkage",
                "entity_type": "project",
                "entity_id": card.card_id,
                "text": f"Card vinculado ao GitHub: {github_link}",
                "event_timestamp": card.last_activity,
                "source_ref": {"source_id": card.card_id, "url": card.card_url},
                "metadata": {"link_url": github_link, "link_type": "github"},
            }
        )

    return claims
