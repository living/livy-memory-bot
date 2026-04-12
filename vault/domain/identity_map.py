"""Identity map — resolves person names from different sources to canonical identity."""
from __future__ import annotations

import logging
import unicodedata
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parent / "identity_map.yaml"


def _strip_accents(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")


def _norm(s: str) -> str:
    return _strip_accents(s).strip().lower()


class IdentityMap:
    """Resolve person identifiers to canonical names."""

    def __init__(self, entries: list[dict]):
        self._entries = entries
        self._by_github: dict[str, str] = {}
        self._by_trello: dict[str, str] = {}
        self._by_alias: dict[str, str] = {}
        self._by_email: dict[str, str] = {}

        for entry in entries:
            canonical = entry["canonical"]
            gh = entry.get("github_login")
            if gh:
                self._by_github[gh.lower()] = canonical
                self._by_alias[_norm(gh)] = canonical
            for tn in entry.get("trello_names", []):
                self._by_trello[_norm(tn)] = canonical
                self._by_alias[_norm(tn)] = canonical
            email = entry.get("email")
            if email:
                self._by_email[email.lower().strip()] = canonical
            for alias in entry.get("aliases", []):
                self._by_alias[_norm(alias)] = canonical
            self._by_alias[_norm(canonical)] = canonical

    @classmethod
    def load(cls, path: Path | None = None) -> "IdentityMap":
        yaml_path = path or _DEFAULT_PATH
        if not yaml_path.exists():
            logger.warning("Identity map not found: %s", yaml_path)
            return cls(entries=[])
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("persons", [])
        return cls(entries=entries)

    def resolve_by_github(self, login: str) -> Optional[str]:
        if not login:
            return None
        return self._by_github.get(login.lower())

    def resolve_by_trello_name(self, name: str) -> Optional[str]:
        if not name:
            return None
        return self._by_trello.get(_norm(name))

    def resolve_by_email(self, email: str) -> Optional[str]:
        if not email:
            return None
        return self._by_email.get(email.lower().strip())

    def resolve(self, name_or_login: str) -> Optional[str]:
        if not name_or_login:
            return None
        norm = _norm(name_or_login)
        for lookup in (self._by_github, self._by_trello, self._by_alias, self._by_email):
            result = lookup.get(norm) or lookup.get(name_or_login.lower())
            if result:
                return result
        return None

    def all_canonical_names(self) -> list[str]:
        return [e["canonical"] for e in self._entries]
