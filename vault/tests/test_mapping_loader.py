"""Tests for mapping_loader — YAML config loading and resolution."""
from __future__ import annotations

import pytest
from pathlib import Path

from vault.ingest.mapping_loader import (
    load_trello_member_map,
    load_repo_project_map,
    load_board_project_map,
    resolve_trello_member_to_person,
    resolve_repo_to_project,
    resolve_board_to_project,
)


# --- load_trello_member_map ---

def test_load_trello_member_map_valid(tmp_path: Path):
    (tmp_path / "trello-member-map.yaml").write_text(
        "members:\n  abc123: Lincoln\n  def456: Robert\n"
    )
    result = load_trello_member_map(tmp_path)
    assert result == {"abc123": "Lincoln", "def456": "Robert"}


def test_load_trello_member_map_missing_file(tmp_path: Path):
    result = load_trello_member_map(tmp_path / "nonexistent")
    assert result == {}


def test_load_trello_member_map_empty(tmp_path: Path):
    (tmp_path / "trello-member-map.yaml").write_text("members: {}\n")
    result = load_trello_member_map(tmp_path)
    assert result == {}


# --- resolve_trello_member_to_person ---

def test_resolve_trello_member_found(tmp_path: Path):
    result = resolve_trello_member_to_person("abc123", {"abc123": "Lincoln"}, tmp_path)
    assert result == "Lincoln"


def test_resolve_trello_member_unmapped(tmp_path: Path):
    result = resolve_trello_member_to_person("zzz", {"abc123": "Lincoln"}, tmp_path)
    assert result is None


# --- resolve_repo_to_project ---

def test_resolve_repo_to_project_found():
    result = resolve_repo_to_project("living/livy-memory-bot", {"living/livy-memory-bot": "Livy Memory"})
    assert result == "Livy Memory"


def test_resolve_repo_to_project_unmapped():
    result = resolve_repo_to_project("unknown/repo", {"living/livy-memory-bot": "Livy Memory"})
    assert result is None


# --- resolve_board_to_project ---

def test_resolve_board_to_project_found():
    result = resolve_board_to_project("board123", {"board123": "BAT"})
    assert result == "BAT"


def test_resolve_board_to_project_unmapped():
    result = resolve_board_to_project("zzz", {"board123": "BAT"})
    assert result is None
