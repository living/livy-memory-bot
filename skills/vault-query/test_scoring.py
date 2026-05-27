"""
Tests for vault-query relevancy scoring.
"""

import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])

from scoring import RelevanceScorer, filter_and_rank


def test_exact_match_in_text():
    """Exact keyword match in text: +10"""
    entry = {
        "id": "1",
        "title": "Generic entry",
        "text": "The delphos-svd system handles video processing.",
    }
    scorer = RelevanceScorer()
    score = scorer.score(entry, "delphos-svd")
    assert score == 10, f"Expected 10, got {score}"
    print("✓ Exact match in text: +10")


def test_keyword_in_tags():
    """Keyword in tags: +5"""
    entry = {
        "id": "2",
        "title": "Integration doc",
        "tags": ["delphos", "delphos-svd", "video"],
        "text": "System integration guide.",
    }
    scorer = RelevanceScorer()
    score = scorer.score(entry, "delphos-svd")
    assert score == 5, f"Expected 5, got {score}"
    print("✓ Keyword in tags: +5")


def test_keyword_in_source_ref():
    """Keyword in source_ref: +3"""
    entry = {
        "id": "3",
        "title": "External reference",
        "source_ref": "https://github.com/living/delphos-svd",
        "text": "See the link above.",
    }
    scorer = RelevanceScorer()
    score = scorer.score(entry, "delphos-svd")
    assert score == 3, f"Expected 3, got {score}"
    print("✓ Keyword in source_ref: +3")


def test_keyword_in_title():
    """Keyword in title/header: +8"""
    entry = {
        "id": "4",
        "title": "delphos-svd architecture",
        "text": "Overview of the system.",
    }
    scorer = RelevanceScorer()
    score = scorer.score(entry, "delphos-svd")
    assert score == 8, f"Expected 8, got {score}"
    print("✓ Keyword in title: +8")


def test_recency_bonus():
    """Recency (last 30 days): +2"""
    from datetime import datetime, timedelta
    entry = {
        "id": "5",
        "title": "Recent update",
        "text": "A general update.",
        "created_at": datetime.now().isoformat(),
    }
    scorer = RelevanceScorer()
    score = scorer.score(entry, "delphos-svd")
    assert score == 2, f"Expected 2 (recency), got {score}"
    print("✓ Recency bonus: +2")


def test_multiple_occurrences():
    """Multiple occurrences: +1 per extra (max +5)"""
    entry = {
        "id": "6",
        "title": "delphos-svd deep dive",
        "text": "The delphos-svd system uses delphos-svd protocols. delphos-svd integration complete.",
    }
    scorer = RelevanceScorer()
    score = scorer.score(entry, "delphos-svd")
    # 10 (exact match in text) + 2 (2 extra in text) + 8 (title) = 20
    # Text has 3 occurrences: 10 + (3-1)*1 = 12
    # Title has 1: +8
    # Total: 20
    assert score == 20, f"Expected 20, got {score}"
    print("✓ Multiple occurrences counted")


def test_combined_score():
    """Combined scoring from multiple signals."""
    from datetime import datetime
    entry = {
        "id": "7",
        "title": "delphos-svd",
        "tags": ["delphos-svd"],
        "source_ref": "living/delphos-svd",
        "text": "delphos-svd is a subsystem for video processing.",
        "created_at": datetime.now().isoformat(),
    }
    scorer = RelevanceScorer()
    score = scorer.score(entry, "delphos-svd")
    # 10 (text) + 5 (tags) + 3 (source_ref) + 8 (title) + 2 (recency) = 28
    assert score == 28, f"Expected 28, got {score}"
    print("✓ Combined score: 28")


def test_ordering_by_score():
    """Entries should be sorted by score descending."""
    entries = [
        {"id": "a", "title": "Old entry", "text": "No match here."},
        {"id": "b", "title": "delphos-svd", "text": "Exact match.", "tags": ["other"]},
        {"id": "c", "title": "delphos-svd deep dive", "text": "The delphos-svd system. delphos-svd rocks.", "tags": ["delphos-svd"]},
        {"id": "d", "source_ref": "github.com/delphos-svd", "text": "Reference only."},
    ]
    results = filter_and_rank(entries, "delphos-svd", min_score=3)
    
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert results[0]["id"] == "c", f"Expected 'c' first, got {results[0]['id']}"
    assert results[0]["_score"] > results[1]["_score"], "First score should be > second"
    print("✓ Ordering by score descending")


def test_min_score_filter():
    """Entries below min_score should be excluded."""
    entries = [
        {"id": "a", "title": "delphos-svd", "text": "Match!", "source_ref": "xyz/delphos-svd"},  # 10+3=13
        {"id": "b", "source_ref": "github.com/delphos-svd"},  # 3
        {"id": "c", "title": "General doc", "text": "Nothing relevant."},  # 0
        {"id": "d", "tags": ["delphos-svd"]},  # 5
    ]
    results = filter_and_rank(entries, "delphos-svd", min_score=3)
    
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    ids = [r["id"] for r in results]
    assert "c" not in ids, "Entry 'c' should be filtered out (score=0)"
    print("✓ min_score filter works")


def test_score_added_to_results():
    """Each result should have _score field."""
    entries = [
        {"id": "a", "title": "delphos-svd", "text": "Match!"},
        {"id": "b", "tags": ["delphos-svd"]},
    ]
    results = filter_and_rank(entries, "delphos-svd")
    
    for r in results:
        assert "_score" in r, f"Missing _score in result: {r}"
    print("✓ _score field added to results")


if __name__ == "__main__":
    print("Running vault-query scoring tests...\n")
    
    test_exact_match_in_text()
    test_keyword_in_tags()
    test_keyword_in_source_ref()
    test_keyword_in_title()
    test_recency_bonus()
    test_multiple_occurrences()
    test_combined_score()
    test_ordering_by_score()
    test_min_score_filter()
    test_score_added_to_results()
    
    print("\n✅ All tests passed!")
