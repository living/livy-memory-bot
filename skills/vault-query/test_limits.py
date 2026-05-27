"""
Tests for search_limits module.

Run with: python3 test_limits.py
"""

import sys
from dataclasses import dataclass
from typing import Dict, Any

# Add module to path
sys.path.insert(0, __file__.rsplit('/', 1)[0])

from search_limits import (
    MAX_RESULTS,
    search_with_limit,
    ComplexityBudget,
    MAX_CROSS_REFS,
    MAX_HOPS,
)


@dataclass
class MockResult:
    """Mock result object for testing."""
    id: str
    source: str
    score: float


def test_budget_decreases_on_cross_ref():
    """Test that budget decreases on cross-ref calls."""
    budget = ComplexityBudget()
    
    assert budget.cross_refs_used == 0
    assert budget.can_cross_ref() is True
    
    # Use first cross-ref
    result = budget.use_budget(hops=0)
    assert result is True
    assert budget.cross_refs_used == 1
    assert budget.remaining_cross_refs() == MAX_CROSS_REFS - 1
    
    # Use second cross-ref
    result = budget.use_budget(hops=0)
    assert result is True
    assert budget.cross_refs_used == 2
    assert budget.hops_used == 0  # hops=0
    
    print("✓ test_budget_decreases_on_cross_ref passed")


def test_budget_blocks_after_5_cross_refs():
    """Test that budget blocks after 5 cross-refs."""
    budget = ComplexityBudget()
    
    # Use all 5 cross-refs (use hops=0 to avoid hop limit)
    for i in range(5):
        assert budget.can_cross_ref() is True
        assert budget.use_budget(hops=0) is True
        assert budget.cross_refs_used == i + 1
    
    # Should be exhausted now
    assert budget.can_cross_ref() is False
    assert budget.use_budget(hops=0) is False
    assert budget.is_exhausted is True
    assert budget.cross_refs_used == 5
    
    print("✓ test_budget_blocks_after_5_cross_refs passed")


def test_early_exit_for_simple_queries():
    """Test early exit for simple keyword queries."""
    # Create 30 mock results
    results = [MockResult(id=str(i), source="test", score=1.0 - i*0.01) for i in range(30)]
    
    # Simple keyword query should return only 20
    limited = search_with_limit("simple_keyword", results)
    assert len(limited) == 20
    assert limited[0].id == "0"  # First item preserved
    
    print("✓ test_early_exit_for_simple_queries passed")


def test_entity_lookup_limit():
    """Test entity lookup returns max 10 results."""
    results = [MockResult(id=str(i), source="entity", score=1.0) for i in range(15)]
    
    limited = search_with_limit("entity_lookup", results)
    assert len(limited) == 10
    
    print("✓ test_entity_lookup_limit passed")


def test_concept_trace_per_source_limit():
    """Test concept trace limits to 5 per source."""
    # Create 10 results from source A, 10 from source B
    results = [
        MockResult(id=f"a-{i}", source="source-A", score=1.0 - i*0.01)
        for i in range(10)
    ] + [
        MockResult(id=f"b-{i}", source="source-B", score=1.0 - i*0.01)
        for i in range(10)
    ]
    
    limited = search_with_limit("concept_trace", results)
    
    # Should have max 5 per source = 10 total
    assert len(limited) == 10
    
    # Verify both sources are represented
    sources = set(r.source for r in limited)
    assert len(sources) == 2
    
    print("✓ test_concept_trace_per_source_limit passed")


def test_complex_synthesis_pagination():
    """Test complex synthesis triggers pagination."""
    budget = ComplexityBudget()
    
    # Simulate complex query with many cross-refs
    while not budget.is_exhausted:
        budget.use_budget()
    
    state = budget.to_dict()
    assert state["exhausted"] is True
    assert state["pagination_needed"] is True
    
    print("✓ test_complex_synthesis_pagination passed")


def test_budget_reset():
    """Test budget reset functionality."""
    budget = ComplexityBudget()
    
    # Use some budget
    budget.use_budget()
    budget.use_budget()
    assert budget.cross_refs_used == 2
    
    # Reset
    budget.reset()
    assert budget.cross_refs_used == 0
    assert budget.hops_used == 0
    assert budget.can_cross_ref() is True
    
    print("✓ test_budget_reset passed")


def test_max_results_constants():
    """Test MAX_RESULTS dict has all required query types."""
    required_types = [
        "simple_keyword",
        "entity_lookup",
        "concept_trace",
        "decision_history",
        "complex_synthesis",
    ]
    
    for query_type in required_types:
        assert query_type in MAX_RESULTS
        assert MAX_RESULTS[query_type] > 0
    
    print("✓ test_max_results_constants passed")


def test_unknown_query_type_defaults():
    """Test unknown query type defaults to 20 results."""
    results = list(range(50))
    limited = search_with_limit("unknown_type", results)
    assert len(limited) == 20
    
    print("✓ test_unknown_query_type_defaults passed")


def run_all_tests():
    """Run all tests."""
    print("\nRunning search_limits tests...\n")
    
    tests = [
        test_budget_decreases_on_cross_ref,
        test_budget_blocks_after_5_cross_refs,
        test_early_exit_for_simple_queries,
        test_entity_lookup_limit,
        test_concept_trace_per_source_limit,
        test_complex_synthesis_pagination,
        test_budget_reset,
        test_max_results_constants,
        test_unknown_query_type_defaults,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        sys.exit(1)
    else:
        print("All tests passed! ✓")


if __name__ == "__main__":
    run_all_tests()
