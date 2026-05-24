# tests/qw2/test_consolidate.py
import pytest
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))
from vault.qw2.consolidate import parse_topic_file, dedupe_entries, consolidate_topic


@pytest.fixture
def sample_topic_file(tmp_path):
    # Format: blank line between header and blockquote (QW-2 writer format)
    content = """---
name: test-topic
---

### 2026-05-07 — tldv

> SVD e Hidra seguem com integração via fila

- **Source:** tldv:abc123
- **Confidence:** 0.92

### 2026-05-07 — tldv

> SVD e Hidra seguem com integração via fila

- **Source:** tldv:abc123
- **Confidence:** 0.92

### 2026-05-06 — github

> Deploy de todos os serviços no Azure

- **Source:** github:xyz789
- **Confidence:** 0.85
"""
    p = tmp_path / "test-topic.md"
    p.write_text(content)
    return p


def test_parse_topic_file(sample_topic_file):
    entries = parse_topic_file(sample_topic_file)
    assert len(entries) == 3


def test_dedupe_keeps_latest(sample_topic_file):
    entries = parse_topic_file(sample_topic_file)
    deduped = dedupe_entries(entries)
    assert len(deduped) == 2  # 2 unique source_refs
    # tldv:abc123 appears twice (same date) → one wins
    # github:xyz789 → 1


def test_dedupe_different_source_refs_kept(sample_topic_file):
    entries = parse_topic_file(sample_topic_file)
    deduped = dedupe_entries(entries)
    refs = {e["source_ref"] for e in deduped}
    assert "tldv:abc123" in refs
    assert "github:xyz789" in refs


def test_consolidate_dry_run_no_modify(sample_topic_file):
    original = sample_topic_file.read_text()
    stats = consolidate_topic(sample_topic_file, dry_run=True)
    assert stats["deduped"] == 1
    assert stats["written"] == 0
    assert sample_topic_file.read_text() == original


def test_consolidate_writes_deduplicated(sample_topic_file):
    stats = consolidate_topic(sample_topic_file, dry_run=False)
    assert stats["deduped"] == 1
    assert stats["written"] == 1
    entries = parse_topic_file(sample_topic_file)
    assert len(entries) == 2
