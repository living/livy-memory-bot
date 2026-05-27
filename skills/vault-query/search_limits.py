"""
Result limits and complexity budget for vault-query.

Prevents timeout and manages token usage by enforcing query-type limits
and cross-reference budgets.
"""

from typing import List, Dict, Any, Optional


# Max results by query type
MAX_RESULTS: Dict[str, int] = {
    "simple_keyword": 20,
    "entity_lookup": 10,
    "concept_trace": 15,
    "decision_history": 30,
    "complex_synthesis": 20,
}

# Max items per source for concept traces
MAX_PER_SOURCE = 5

# Complexity budget limits
MAX_CROSS_REFS = 5
MAX_HOPS = 3


def search_with_limit(query_type: str, results: List[Any]) -> List[Any]:
    """
    Apply result limits based on query type.
    
    Args:
        query_type: One of the defined query types
        results: Raw results list
        
    Returns:
        Limited results list with early exit hint for simple queries
    """
    max_results = MAX_RESULTS.get(query_type, 20)
    
    if len(results) <= max_results:
        return results
    
    # Early exit for simple keyword queries
    if query_type == "simple_keyword":
        return results[:max_results]
    
    # For concept traces, limit per source
    if query_type == "concept_trace":
        return _limit_per_source(results, MAX_PER_SOURCE)
    
    # Default: slice to max
    return results[:max_results]


def _limit_per_source(results: List[Any], max_per_source: int) -> List[Any]:
    """Limit results to max_per_source per source."""
    by_source: Dict[str, List[Any]] = {}
    
    for item in results:
        source = getattr(item, 'source', 'unknown') if hasattr(item, 'source') else item.get('source', 'unknown') if isinstance(item, dict) else 'unknown'
        if source not in by_source:
            by_source[source] = []
        if len(by_source[source]) < max_per_source:
            by_source[source].append(item)
    
    # Flatten back to list
    limited = []
    for source_items in by_source.values():
        limited.extend(source_items)
    return limited


class ComplexityBudget:
    """
    Tracks cross-reference usage to prevent timeout.
    
    Attributes:
        max_cross_refs: Maximum files to cross-reference (default 5)
        max_hops: Maximum relationship hops (default 3)
        cross_refs_used: Current cross-reference count
        hops_used: Current hop count
    """
    
    def __init__(
        self,
        max_cross_refs: int = MAX_CROSS_REFS,
        max_hops: int = MAX_HOPS
    ):
        self.max_cross_refs = max_cross_refs
        self.max_hops = max_hops
        self.cross_refs_used = 0
        self.hops_used = 0
    
    def can_cross_ref(self) -> bool:
        """Check if cross-reference budget is available."""
        return self.cross_refs_used < self.max_cross_refs
    
    def use_budget(self, hops: int = 1) -> bool:
        """
        Consume cross-reference budget.
        
        Args:
            hops: Number of relationship hops for this cross-ref
            
        Returns:
            True if budget was consumed, False if exhausted
        """
        if not self.can_cross_ref():
            return False
        
        if self.hops_used + hops > self.max_hops:
            return False
        
        self.cross_refs_used += 1
        self.hops_used += hops
        return True
    
    def reset(self) -> None:
        """Reset budget counters."""
        self.cross_refs_used = 0
        self.hops_used = 0
    
    @property
    def is_exhausted(self) -> bool:
        """Check if budget is fully exhausted."""
        return self.cross_refs_used >= self.max_cross_refs or self.hops_used >= self.max_hops
    
    def remaining_cross_refs(self) -> int:
        """Get remaining cross-reference budget."""
        return self.max_cross_refs - self.cross_refs_used
    
    def remaining_hops(self) -> int:
        """Get remaining hop budget."""
        return self.max_hops - self.hops_used
    
    def to_dict(self) -> Dict[str, Any]:
        """Export budget state for signaling pagination."""
        return {
            "cross_refs_used": self.cross_refs_used,
            "cross_refs_remaining": self.remaining_cross_refs(),
            "hops_used": self.hops_used,
            "hops_remaining": self.remaining_hops(),
            "exhausted": self.is_exhausted,
            "pagination_needed": self.is_exhausted,
        }
