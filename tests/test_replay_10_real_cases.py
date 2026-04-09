"""
Test replay of 10 historical R005 deferred cases under strict shadow evolution gate.

TDD Phase 1: These tests should FAIL because production modules don't exist yet.
When production modules are implemented, all 10 cases must remain deferred under
the strict gate to ensure zero false positives.
"""
import importlib.util
import json
from pathlib import Path

import pytest

# Load the 10 historical R005 cases as fixture
FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPLAY_FIXTURE = FIXTURES_DIR / "replay_r005_cases.json"
GATE_FILE = Path(__file__).resolve().parents[1] / "skills" / "memoria-consolidation" / "gate.py"


@pytest.fixture
def replay_cases():
    """Load the 10 historical R005 deferred cases."""
    with open(REPLAY_FIXTURE) as f:
        cases = json.load(f)
    assert len(cases) == 10, "Fixture must contain exactly 10 R005 cases"
    return cases


@pytest.fixture
def strict_gate():
    """Import the production gate module (will fail until implemented)."""
    if not GATE_FILE.exists():
        raise ModuleNotFoundError(f"Missing production gate module: {GATE_FILE}")

    spec = importlib.util.spec_from_file_location("memoria_consolidation_gate", GATE_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load gate module spec from {GATE_FILE}")

    gate_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate_module)
    return gate_module.strict_promotion_gate


class TestReplay10RealCases:
    """Verify all 10 historical R005 cases remain deferred under strict gate."""

    def test_fixture_contains_10_r005_deferred_cases(self, replay_cases):
        """Sanity check: fixture has exactly 10 deferred R005 cases."""
        r005_cases = [c for c in replay_cases if c["rule_id"] == "R005_new_issue_flagged_for_triage"]
        assert len(r005_cases) == 10
        assert all(c["result"] == "deferred" for c in r005_cases)

    def test_all_10_cases_remain_deferred_under_strict_gate(self, replay_cases, strict_gate):
        """FAIL (expected): All 10 R005 cases should remain deferred under strict gate."""
        promoted = []
        for case in replay_cases:
            result = strict_gate(case)
            if result.get("promoted"):
                promoted.append(case["entity_key"])

        # ZERO false positives allowed - all 10 must stay deferred
        assert len(promoted) == 0, (
            f"FAIL: {len(promoted)} cases wrongly promoted: {promoted}. "
            f"Zero FP gate must keep all 10 R005 cases deferred."
        )

    def test_case_missing_tier_classification_not_promoted(self, replay_cases, strict_gate):
        """FAIL (expected): Cases without tier classification must not be promoted."""
        for case in replay_cases:
            # Simulate missing tier - gate must reject
            case_without_tier = {k: v for k, v in case.items() if k != "tier"}
            result = strict_gate(case_without_tier)
            assert not result.get("promoted"), (
                f"Case {case['entity_key']} promoted without tier classification!"
            )

    def test_case_low_confidence_not_promoted(self, replay_cases, strict_gate):
        """FAIL (expected): Cases with confidence < 0.85 must not be promoted."""
        for case in replay_cases:
            # All fixture cases have confidence 0.6 - must stay deferred
            result = strict_gate(case)
            assert not result.get("promoted"), (
                f"Case {case['entity_key']} promoted with low confidence {case['confidence']}"
            )
