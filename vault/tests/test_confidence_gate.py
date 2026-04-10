"""
Tests for vault/confidence_gate.py — hardened confidence write-gate.
Phase 1C: blocks high/medium promotion without official/corroborated sources.
"""
from pathlib import Path

import pytest


@pytest.fixture
def gate_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import vault.confidence_gate as cg
    return cg


# ------------------------------------------------------------------
# Source classification
# ------------------------------------------------------------------

class TestSourceClassification:

    def test_official_types(self, gate_module):
        assert gate_module.classify_source({"type": "tldv_api"}) == "official"
        assert gate_module.classify_source({"type": "github_api"}) == "official"
        assert gate_module.classify_source({"type": "openclaw_config"}) == "official"
        assert gate_module.classify_source({"type": "supabase_rest"}) == "official"
        assert gate_module.classify_source({"type": "exec"}) == "official"

    def test_corroborated_types(self, gate_module):
        assert gate_module.classify_source({"type": "curated_topic"}) == "corroborated"

    def test_indirect_types(self, gate_module):
        assert gate_module.classify_source({"type": "signal_event"}) == "indirect"
        assert gate_module.classify_source({"type": "observation"}) == "indirect"
        assert gate_module.classify_source({"type": "chat_history"}) == "indirect"


# ------------------------------------------------------------------
# Confidence scoring
# ------------------------------------------------------------------

class TestConfidenceScoring:

    def test_high_requires_official_or_official_plus_corroborated(self, gate_module):
        assert gate_module.score_confidence(2, 0, 0) == "high"
        assert gate_module.score_confidence(1, 1, 0) == "high"
        assert gate_module.score_confidence(0, 2, 0) != "high"

    def test_medium_requires_official_or_2_indirect(self, gate_module):
        assert gate_module.score_confidence(1, 0, 0) == "medium"
        assert gate_module.score_confidence(0, 0, 2) == "medium"

    def test_low_requires_single_indirect(self, gate_module):
        assert gate_module.score_confidence(0, 0, 1) == "low"

    def test_unverified_when_no_sources(self, gate_module):
        assert gate_module.score_confidence(0, 0, 0) == "unverified"


# ------------------------------------------------------------------
# Write-gate policy
# ------------------------------------------------------------------

class TestWriteGatePolicy:

    def test_blocks_high_without_official_or_corroborated(self, gate_module):
        sources = [{"type": "signal_event"}]
        conf = gate_module.score_from_sources(sources)
        assert conf in ("low", "unverified"), "signal_event only should not get high/medium"

    def test_allows_high_with_official_sources(self, gate_module):
        sources = [{"type": "tldv_api"}, {"type": "curated_topic"}]
        conf = gate_module.score_from_sources(sources)
        assert conf == "high"

    def test_gate_decision_returns_enforced_confidence(self, gate_module):
        sources = [{"type": "signal_event"}]
        result = gate_module.gate_decision(sources)
        assert result["allowed"]
        assert result["enforced_confidence"] in ("low", "unverified")

    def test_gate_decision_blocks_false_high(self, gate_module):
        sources = [{"type": "signal_event"}]
        result = gate_module.gate_decision(sources)
        assert result["enforced_confidence"] != "high"

    def test_gate_decision_allows_real_high(self, gate_module):
        sources = [{"type": "tldv_api"}, {"type": "curated_topic"}]
        result = gate_module.gate_decision(sources)
        assert result["allowed"]
        assert result["enforced_confidence"] == "high"
