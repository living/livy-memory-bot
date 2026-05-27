#!/usr/bin/env python3
"""Test query routing classifier for vault-query skill."""

import re
from typing import Literal

QueryType = Literal["simple", "entity", "complex"]


def classify_query(query: str) -> QueryType:
    """
    Classify query complexity to route to the right strategy.
    
    Rules:
    - Simple: contains specific repo/tag/keyword, date range, or "what was decided about X"
    - Entity: asks about a person or meeting ("who is X?", "what meetings had Y?")
    - Complex: asks about project status, needs synthesis, or compares across sources
    """
    query_lower = query.lower()
    
    # Entity patterns: "who is", "what meetings had", person/meeting focus
    entity_patterns = [
        r'\bwho is\b',
        r'\bwho was\b',
        r'\bwhat meetings?\b',
        r'\bwhich meetings?\b',
        r'\babout\s+\w+\s+\?',  # "about X?"
    ]
    for pattern in entity_patterns:
        if re.search(pattern, query_lower):
            return "entity"
    
    # Complex patterns: project status, synthesis, comparison
    complex_patterns = [
        r'\bwhat is happening\b',
        r'\bwhat\'s happening\b',
        r'\bstatus of\b',
        r'\bcompare\b.*\bacross\b',
        r'\bsynthesis\b',
        r'\boverview of\b',
        r'\bsummary of\b',
    ]
    for pattern in complex_patterns:
        if re.search(pattern, query_lower):
            return "complex"
    
    # Simple patterns: specific keywords, date ranges, "what was decided"
    simple_patterns = [
        r'\b\d{4}-\d{2}(-\d{2})?\b',  # Date range YYYY-MM-DD
        r'\bwhat was decided\b',
        r'\bdecisions?\s+about\b',
        r'\bpr[ #]?\d+\b',  # PR references
        r'\b[a-z]+-[a-z]+-[a-z]+\b',  # hyphenated keywords like delphos-svd
    ]
    for pattern in simple_patterns:
        if re.search(pattern, query_lower):
            return "simple"
    
    # Default: simple (has specific keyword/topic)
    return "simple"


def main():
    test_queries = [
        "delphos-svd",
        "who is Lincoln?",
        "what is happening with BAT?",
        "kaba PRs this month",
        "decisions about whisper",
    ]
    
    print("=" * 60)
    print("Vault-Query Routing Test")
    print("=" * 60)
    
    for i, query in enumerate(test_queries, 1):
        classification = classify_query(query)
        print(f"\n{i}. Query: \"{query}\"")
        print(f"   → Classification: {classification}")


if __name__ == "__main__":
    main()
