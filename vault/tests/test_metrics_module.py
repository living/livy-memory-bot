"""
Tests for vault/metrics.py — quality metrics for Memory Vault.
"""
from pathlib import Path

import pytest


@pytest.fixture
def metrics_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import vault.metrics as mx
    return mx


@pytest.fixture
def vault_with_decisions(tmp_path):
    root = tmp_path / "memory" / "vault"
    for d in ("decisions", "entities", "concepts"):
        (root / d).mkdir(parents=True, exist_ok=True)

    (root / "entities" / "entity-a.md").write_text("# A", encoding="utf-8")

    # Decision with high + official source (should count)
    (root / "decisions" / "d1.md").write_text(
        """---
entity: D1
type: decision
confidence: high
sources:
  - type: tldv_api
    ref: https://tldv.io/meeting/123
---
# D1
""",
        encoding="utf-8",
    )

    # Decision with high but indirect source (should NOT count as official)
    (root / "decisions" / "d2.md").write_text(
        """---
entity: D2
type: decision
confidence: high
sources:
  - type: signal_event
    ref: https://tldv.io/meeting/456
---
# D2
""",
        encoding="utf-8",
    )

    # Decision with low confidence
    (root / "decisions" / "d3.md").write_text(
        """---
entity: D3
type: decision
confidence: low
sources: []
---
# D3
""",
        encoding="utf-8",
    )

    return root


class TestQualityMetrics:

    def test_high_claims_counted(self, metrics_module, vault_with_decisions):
        m = metrics_module.collect_quality_metrics(vault_with_decisions)
        assert m["high_claims_total"] == 2

    def test_high_with_official_counted(self, metrics_module, vault_with_decisions):
        m = metrics_module.collect_quality_metrics(vault_with_decisions)
        assert m["high_claims_with_official"] == 1

    def test_pct_high_with_official(self, metrics_module, vault_with_decisions):
        m = metrics_module.collect_quality_metrics(vault_with_decisions)
        assert m["pct_high_with_official"] == 50.0

    def test_gaps_and_orphans_counted(self, metrics_module, vault_with_decisions):
        m = metrics_module.collect_quality_metrics(vault_with_decisions)
        assert "gaps" in m
        assert "orphans" in m
        assert "stale_claims" in m
