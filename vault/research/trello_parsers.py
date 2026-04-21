"""Parsers for Trello cards and claim extraction."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)

GITHUB_PATTERN = re.compile(r"https?://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:/[^\s)\]}>\"']+)?")
HOURS_PATTERN = re.compile(r"(?:hours?_logged|horas?)\s*[:=]\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
DECISION_KEYWORDS_PATTERN = re.compile(
    r"\b(?:decis[aã]o|decidido|decidimos|aprovad[oa]|definido|confirmado|vamos|deve(?:mos)?)\b",
    re.IGNORECASE,
)
WORD_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)


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
    comments: list[str] = None  # type: ignore[assignment]
    checklists: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.comments is None:
            self.comments = []
        if self.checklists is None:
            self.checklists = []


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


def _is_decision_text(text: str) -> bool:
    words = WORD_PATTERN.findall(text or "")
    return len(words) >= 5


def _extract_decision_comments(card: dict[str, Any]) -> list[str]:
    comments = card.get("_comments")
    if not isinstance(comments, list):
        return []

    decision_comments: list[str] = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        text = str(comment.get("text", "") or "").strip()
        if _is_decision_text(text):
            decision_comments.append(text)
    return decision_comments


def _extract_decision_checklists(card: dict[str, Any]) -> list[str]:
    checklists = card.get("_checklists")
    if not isinstance(checklists, list):
        return []

    decision_items: list[str] = []
    for checklist in checklists:
        if not isinstance(checklist, dict):
            continue
        items = checklist.get("checkItems", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            text = str(item.get("name", "") or "").strip()
            if _is_decision_text(text):
                decision_items.append(text)
    return decision_items


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
        comments=_extract_decision_comments(card),
        checklists=_extract_decision_checklists(card),
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

    decision_sources = list(card.comments) + list(card.checklists)
    if not decision_sources:
        logger.warning("trello_comments_unavailable", extra={"card_id": card.card_id})

    for decision_text in decision_sources:
        claims.append(
            {
                "source": "trello",
                "claim_type": "decision",
                "entity_type": "project",
                "entity_id": card.card_id,
                "text": decision_text,
                "event_timestamp": card.last_activity,
                "source_ref": {"source_id": card.card_id, "url": card.card_url},
                "metadata": {"board_id": card.board_id, "source": "trello_comment_or_checklist"},
                "needs_review": True,
                "review_reason": "comentario_trello",
                "confidence": 0.40,
            }
        )

    return claims
