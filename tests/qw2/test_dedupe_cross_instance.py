import json, pytest
from vault.qw2.writer import QWWriter, load_written_refs

def test_dedupe_across_two_writer_instances(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw2.writer.QW2_BASE", tmp_path)
    monkeypatch.setattr("vault.qw2.writer.DECISIONS_DIR", tmp_path / "decisions")

    decision = {
        "text": "Test decision for dedupe.",
        "source_ref": "tldv:meeting_cross_instance_test",
        "confidence": 0.90,
        "date": "2026-05-24",
        "source": "tldv",
        "tags": [],
    }
    topic = tmp_path / "decisions" / "test.md"

    # Run 1
    writer1 = QWWriter()
    result1 = writer1.write(topic, decision)
    assert result1 is True

    # Run 2: separate instance
    writer2 = QWWriter()
    result2 = writer2.write(topic, decision)
    assert result2 is False  # dedupe

    content = topic.read_text()
    assert content.count("Test decision for dedupe.") == 1
