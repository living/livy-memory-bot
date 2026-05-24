import json, pytest
from vault.qw2.cursor import QWCursor

def test_read_write_cursor(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw2.cursor.QW2_CURSOR_DIR", tmp_path)
    c = QWCursor("tldv")
    assert c.read() is None
    c.write("2026-05-24T10:00:00Z")
    assert c.read() == "2026-05-24T10:00:00Z"

def test_cursor_per_source(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw2.cursor.QW2_CURSOR_DIR", tmp_path)
    t = QWCursor("tldv")
    g = QWCursor("github")
    t.write("2026-05-24T10:00:00Z")
    g.write("2026-05-24T11:00:00Z")
    assert t.read() == "2026-05-24T10:00:00Z"
    assert g.read() == "2026-05-24T11:00:00Z"
