"""Tests for incremental index.md management."""
from vault.ingest.index_manager import (
    init_index,
    add_entry,
    update_entry,
    read_index,
)


class TestIndexManager:
    def test_init_index_creates_file(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        assert (vault / "index.md").exists()

    def test_add_entry(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        add_entry(vault, "entities/meeting-abc.md", "Meeting: Status BAT", "meeting")
        idx = read_index(vault)
        assert "entities/meeting-abc.md" in idx
        assert idx["entities/meeting-abc.md"]["title"] == "Meeting: Status BAT"
        assert idx["entities/meeting-abc.md"]["type"] == "meeting"

    def test_add_entry_idempotent(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        add_entry(vault, "entities/meeting-abc.md", "Title", "meeting")
        add_entry(vault, "entities/meeting-abc.md", "Title", "meeting")
        idx = read_index(vault)
        assert len([k for k in idx if "meeting-abc" in k]) == 1

    def test_update_entry_changes_title(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        add_entry(vault, "entities/meeting-abc.md", "Old Title", "meeting")
        update_entry(vault, "entities/meeting-abc.md", "New Title")
        idx = read_index(vault)
        assert idx["entities/meeting-abc.md"]["title"] == "New Title"

    def test_multiple_entries_by_type(self, tmp_path):
        vault = tmp_path / "vault"
        init_index(vault)
        add_entry(vault, "entities/meeting-a.md", "M A", "meeting")
        add_entry(vault, "entities/person-b.md", "P B", "person")
        add_entry(vault, "concepts/bat.md", "BAT", "concept")
        idx = read_index(vault)
        assert len(idx) == 3
        types = {v["type"] for v in idx.values()}
        assert types == {"meeting", "person", "concept"}
