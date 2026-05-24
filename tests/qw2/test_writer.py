import json, pytest
from vault.qw2.writer import QWWriter, load_written_refs, add_to_written_refs

def test_write_append_and_log(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw2.writer.QW2_BASE", tmp_path)
    monkeypatch.setattr("vault.qw2.writer.DECISIONS_DIR", tmp_path / "decisions")
    decision = {
        "text": "Usar GPT-4 para decisões de alta confiança.",
        "source_ref": "tldv:meeting_abc",
        "confidence": 0.92,
        "date": "2026-05-24",
        "source": "tldv",
        "tags": ["llm", "gpt-4"],
    }
    writer = QWWriter()
    topic = tmp_path / "decisions" / "livy-memory-agent.md"
    writer.write(topic, decision)

    content = topic.read_text()
    assert "Usar GPT-4" in content
    assert "> Usar GPT-4" in content  # blockquote
    assert "**Confidence:** 0.92" in content

    # write log entry
    log = (tmp_path / "write_log.jsonl").read_text()
    assert "tldv:meeting_abc" in log
