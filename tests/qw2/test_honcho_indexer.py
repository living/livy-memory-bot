# tests/qw2/test_honcho_indexer.py
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))
from vault.qw2.honcho_indexer import get_source_type, build_content


def test_get_source_type_tldv():
    assert get_source_type("tldv:abc123") == "tldv"


def test_get_source_type_github():
    assert get_source_type("github:xyz789") == "github"


def test_get_source_type_trello():
    assert get_source_type("trello:card123") == "trello"


def test_get_source_type_unknown():
    assert get_source_type("unknown:ref") == "unknown"


def test_build_content_basic():
    entry = {
        "date": "2026-05-07",
        "text": "Deploy to Azure",
        "source_ref": "github:xyz789",
        "confidence_level": "high",
        "tags": "azure,deploy",
    }
    content = build_content(entry)
    assert "2026-05-07" in content
    assert "Deploy to Azure" in content
    assert "github:xyz789" in content
    assert "confidence:high" in content
    assert "tags:azure,deploy" in content


def test_build_content_with_supersedes():
    entry = {
        "date": "2026-05-07",
        "text": "Updated decision",
        "source_ref": "tldv:abc123",
        "confidence_level": "medium",
        "tags": "",
    }
    content = build_content(entry, supersedes="old_id_123")
    assert "supersedes:old_id_123" in content


def test_build_content_text_truncated():
    entry = {
        "date": "2026-05-07",
        "text": "A" * 300,
        "source_ref": "github:xyz",
        "confidence_level": "low",
        "tags": "",
    }
    content = build_content(entry)
    # text should be truncated to 200 chars
    assert len(content) < 350
    assert "AAAA" not in content or len(content) <= 350
