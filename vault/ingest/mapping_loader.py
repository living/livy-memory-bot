"""Mapping config loader — load and resolve YAML mapping schemas."""
from __future__ import annotations

from pathlib import Path

import yaml


def load_trello_member_map(schema_dir: Path) -> dict[str, str]:
    """Load trello-member-map.yaml → {member_id: person_name}."""
    return _load_map(schema_dir / "trello-member-map.yaml", "members")


def load_repo_project_map(schema_dir: Path) -> dict[str, str]:
    """Load repo-project-map.yaml → {repo_full_name: project_name}."""
    return _load_map(schema_dir / "repo-project-map.yaml", "repos")


def load_board_project_map(schema_dir: Path) -> dict[str, str]:
    """Load board-project-map.yaml → {board_id: project_name}."""
    return _load_map(schema_dir / "board-project-map.yaml", "boards")


def resolve_trello_member_to_person(
    member_id: str, member_map: dict[str, str], vault_root: Path
) -> str | None:
    return member_map.get(member_id)


def resolve_repo_to_project(
    repo_full_name: str, repo_map: dict[str, str]
) -> str | None:
    return repo_map.get(repo_full_name)


def resolve_board_to_project(
    board_id: str, board_map: dict[str, str]
) -> str | None:
    return board_map.get(board_id)


def _load_map(path: Path, key: str) -> dict[str, str]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text())
    if not data or not isinstance(data, dict):
        return {}
    return data.get(key) or {}
