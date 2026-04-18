"""Tests for vault/research/trello_mapper.py — Board→Project resolver."""
from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from vault.research.trello_mapper import BoardProjectMapper, resolve_board


class TestResolveKnownBoard:
    """Board IDs present in the map return their project_source_key."""

    def test_resolve_known_board_returns_project(self, tmp_path):
        """A board_id that exists in the map returns the correct project key."""
        schema_file = tmp_path / "map.yaml"
        schema_file.write_text(
            "boards:\n"
            "  board_abc123:\n"
            "    project_source_key: github/living-bat\n"
            "  board_xyz789:\n"
            "    project_source_key: github/living-delphos\n"
        )
        mapper = BoardProjectMapper(schema_path=str(schema_file))
        result = mapper.resolve_board("board_abc123")
        assert result == "github/living-bat"

    def test_resolve_second_board_returns_its_project(self, tmp_path):
        """Each board resolves to its own mapped project."""
        schema_file = tmp_path / "map.yaml"
        schema_file.write_text(
            "boards:\n"
            "  board_abc123:\n"
            "    project_source_key: github/living-bat\n"
            "  board_xyz789:\n"
            "    project_source_key: github/living-delphos\n"
        )
        mapper = BoardProjectMapper(schema_path=str(schema_file))
        result = mapper.resolve_board("board_xyz789")
        assert result == "github/living-delphos"


class TestResolveUnknownBoard:
    """Board IDs not in the map return 'mapping_missing', not an exception."""

    def test_resolve_unknown_board_returns_mapping_missing(self, tmp_path):
        """An unknown board_id returns 'mapping_missing' sentinel."""
        schema_file = tmp_path / "map.yaml"
        schema_file.write_text(
            "boards:\n"
            "  board_abc123:\n"
            "    project_source_key: github/living-bat\n"
        )
        mapper = BoardProjectMapper(schema_path=str(schema_file))
        result = mapper.resolve_board("board_unknown")
        assert result == "mapping_missing"


class TestMalformedYAML:
    """Malformed YAML raises an exception, not silently ignored."""

    def test_malformed_yaml_raises(self, tmp_path):
        """Invalid YAML raises YAMLError (or wrapped ValueError)."""
        schema_file = tmp_path / "bad.yaml"
        schema_file.write_text("boards: !!notvalid\na  - b")

        with pytest.raises((yaml.YAMLError, ValueError)):
            BoardProjectMapper(schema_path=str(schema_file))


class TestBoardIDsEnvVar:
    """TRELLO_BOARD_IDS environment variable handling."""

    def test_board_ids_split_comma_separated(self, tmp_path, monkeypatch):
        """TRELLO_BOARD_IDS with comma-separated values splits into list."""
        schema_file = tmp_path / "map.yaml"
        schema_file.write_text(
            "boards:\n"
            "  board_a:\n"
            "    project_source_key: github/living-bat\n"
            "  board_b:\n"
            "    project_source_key: github/living-delphos\n"
            "  board_c:\n"
            "    project_source_key: github/livy-tldv\n"
        )
        monkeypatch.setenv("TRELLO_BOARD_IDS", "board_a,board_b,board_c")
        mapper = BoardProjectMapper(schema_path=str(schema_file))
        assert mapper.board_ids == ["board_a", "board_b", "board_c"]

    def test_board_ids_single_value(self, tmp_path, monkeypatch):
        """TRELLO_BOARD_IDS with single value still returns list."""
        schema_file = tmp_path / "map.yaml"
        schema_file.write_text("boards: {}")
        monkeypatch.setenv("TRELLO_BOARD_IDS", "board_single")
        mapper = BoardProjectMapper(schema_path=str(schema_file))
        assert mapper.board_ids == ["board_single"]

    def test_board_ids_whitespace_stripped(self, tmp_path, monkeypatch):
        """Board IDs have whitespace stripped around each value."""
        schema_file = tmp_path / "map.yaml"
        schema_file.write_text("boards: {}")
        monkeypatch.setenv("TRELLO_BOARD_IDS", "  board_a , board_b , board_c  ")
        mapper = BoardProjectMapper(schema_path=str(schema_file))
        assert mapper.board_ids == ["board_a", "board_b", "board_c"]


class TestModuleLevelResolve:
    """Module-level resolve_board convenience function."""

    def test_resolve_board_known(self, tmp_path, monkeypatch):
        """resolve_board(board_id) returns project key for known board."""
        schema_file = tmp_path / "map.yaml"
        schema_file.write_text(
            "boards:\n"
            "  board_known:\n"
            "    project_source_key: github/living-forge\n"
        )
        monkeypatch.setattr(
            "vault.research.trello_mapper.DEFAULT_SCHEMA_PATH",
            str(schema_file),
        )
        # Re-import to pick up patched path (test isolation concern — use instance instead)
        result = resolve_board("board_known")
        assert result == "github/living-forge"
