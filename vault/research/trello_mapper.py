"""
Board → Project source key resolver.

Loads ``vault/schemas/trello-board-project-map.yaml`` and resolves Trello
board IDs to their corresponding project source keys (e.g. ``github/living-bat``).

Behavior
--------
- ``resolve_board(board_id)`` returns the mapped project_source_key.
- Unknown board IDs return the sentinel string ``"mapping_missing"``.
- Malformed YAML raises ``yaml.YAMLError`` (or a wrapped ``ValueError``).
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# Default path relative to this module
DEFAULT_SCHEMA_PATH = str(Path(__file__).parent.parent / "schemas" / "trello-board-project-map.yaml")

# Sentinel for unknown board IDs
MAPPING_MISSING = "mapping_missing"


class BoardProjectMapper:
    """Loads and queries the Trello board → project source key map."""

    def __init__(self, schema_path: str | None = None) -> None:
        self.schema_path = schema_path or DEFAULT_SCHEMA_PATH
        self._map: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Load the YAML schema file and build the board→project lookup."""
        with open(self.schema_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if not isinstance(raw, dict) or "boards" not in raw:
            raise ValueError(
                f"Schema file {self.schema_path!r} must contain a top-level "
                "'boards' mapping."
            )

        boards = raw["boards"]
        if not isinstance(boards, dict):
            raise ValueError(
                f"Schema file {self.schema_path!r}: 'boards' must be a mapping "
                f"of board_id -> project_source_key, got {type(boards).__name__}."
            )

        for board_id, entry in boards.items():
            if isinstance(entry, dict):
                self._map[str(board_id)] = str(entry.get("project_source_key", ""))
            else:
                # Support flat format: board_id: project_source_key (string)
                self._map[str(board_id)] = str(entry)

    def resolve_board(self, board_id: str) -> str:
        """
        Resolve a Trello board ID to its project_source_key.

        Returns ``"mapping_missing"`` if the board ID is not in the map.
        """
        return self._map.get(str(board_id), MAPPING_MISSING)

    @property
    def board_ids(self) -> list[str]:
        """
        Return the list of board IDs from the TRELLO_BOARD_IDS environment
        variable, split by comma. Whitespace is stripped around each value.

        Returns an empty list if the env var is not set or empty.
        """
        raw = os.environ.get("TRELLO_BOARD_IDS", "")
        if not raw:
            return []
        return [bid.strip() for bid in raw.split(",") if bid.strip()]


# Module-level convenience function that uses the default schema path.
_default_mapper: BoardProjectMapper | None = None


def resolve_board(board_id: str) -> str:
    """
    Resolve a Trello board ID to its project_source_key using the default
    schema file.

    Unknown board IDs return ``"mapping_missing"``.
    """
    global _default_mapper
    if _default_mapper is None:
        _default_mapper = BoardProjectMapper()
    return _default_mapper.resolve_board(board_id)
