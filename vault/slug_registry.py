"""
vault/slug_registry.py — canonical slug aliases for vault links.
"""
from __future__ import annotations

import json
from pathlib import Path

_ALIAS: dict[str, str] = {
    "bat-conectabot-observability": "bat-conectabot",
    "tldv-pipeline-state": "tldv-pipeline",
    "projeto-super-memoria-robert": "super-memoria-corporativa",
}


def register(alias: str, canonical: str) -> None:
    if not alias:
        return
    _ALIAS[alias.lower()] = canonical.lower()


def resolve(slug: str | None) -> str | None:
    if slug is None:
        return None
    key = slug.lower()
    return _ALIAS.get(key, key)


def filter_aliased_gaps(gaps: list[dict]) -> list[dict]:
    """Drop gaps that resolve to known canonical slugs."""
    out: list[dict] = []
    for gap in gaps:
        concept = gap.get("concept")
        if not concept:
            continue
        canonical = resolve(concept)
        # If alias differs from original, consider it resolved by mapping
        if canonical != concept.lower():
            continue
        out.append(gap)
    return out


def save_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_ALIAS, ensure_ascii=False, indent=2), encoding="utf-8")


def load_registry(path: Path) -> dict[str, str]:
    if not path.exists():
        return dict(_ALIAS)
    data = json.loads(path.read_text(encoding="utf-8"))
    for k, v in data.items():
        register(k, v)
    return dict(_ALIAS)
