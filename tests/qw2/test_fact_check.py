# tests/qw2/test_fact_check.py
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))
from vault.qw2.fact_check import enrich_decision, enrich_decisions


def test_tldv_decision_medium():
    d = {"source": "tldv", "source_ref": "tldv:abc", "confidence_level": None, "corroborated_sources": None}
    result = enrich_decision(d)
    assert result["confidence_level"] == "medium"


def test_github_decision_medium():
    d = {"source": "github", "source_ref": "github:xyz", "confidence_level": None, "corroborated_sources": None}
    result = enrich_decision(d)
    assert result["confidence_level"] == "medium"


def test_trello_decision_low():
    d = {"source": "trello", "source_ref": "trello:xyz", "confidence_level": None, "corroborated_sources": None}
    result = enrich_decision(d)
    assert result["confidence_level"] == "low"


def test_tldv_with_corroborated_high():
    d = {"source": "tldv", "source_ref": "tldv:abc", "confidence_level": None, "corroborated_sources": ["github:xyz"]}
    result = enrich_decision(d)
    assert result["confidence_level"] == "high"


def test_skips_if_already_has_confidence_level():
    d = {"source": "tldv", "source_ref": "tldv:abc", "confidence_level": "high", "corroborated_sources": None}
    result = enrich_decision(d)
    assert result["confidence_level"] == "high"  # não recalcula


def test_enrich_decisions_batch():
    decisions = [
        {"source": "tldv", "source_ref": "tldv:a", "confidence_level": None, "corroborated_sources": None},
        {"source": "trello", "source_ref": "trello:b", "confidence_level": None, "corroborated_sources": None},
    ]
    results = enrich_decisions(decisions)
    assert results[0]["confidence_level"] == "medium"
    assert results[1]["confidence_level"] == "low"
