"""Cross-source entity matching for Person entities."""
from __future__ import annotations
from typing import Any


def _normalize(name: str | None) -> str:
    if not name:
        return ""
    return name.strip().lower()


def find_person_cross_refs(
    tldv_persons: list[dict[str, Any]],
    trello_members: list[dict[str, Any]],
) -> list[dict[str, str]]:
    matches = []
    by_email: dict[str, dict] = {}
    for p in trello_members:
        email = (p.get("email") or "").strip().lower()
        if email:
            by_email[email] = p

    for tp in tldv_persons:
        email = (tp.get("email") or "").strip().lower()
        trello_match = None
        if email and email in by_email:
            trello_match = by_email[email]
        else:
            norm = _normalize(tp.get("name"))
            for tm in trello_members:
                if _normalize(tm.get("fullName")) == norm:
                    trello_match = tm
                    break
        if trello_match:
            matches.append({
                "tldv_id": tp.get("id", ""),
                "trello_id": trello_match.get("id", ""),
                "match_method": "email" if email and email in by_email else "name",
            })
    return matches
