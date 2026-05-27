"""
Relevancy scoring for vault query results.

Scoring signals:
- Exact keyword match in text: +10 (case-insensitive)
- Keyword in tags: +5
- Keyword in source_ref: +3
- Recency (last 30 days): +2
- Keyword in title/header: +8
- Multiple keyword occurrences: +1 per extra (max +5)

Results with score < 3 are excluded.
"""

from datetime import datetime, timedelta
from typing import Any


class RelevanceScorer:
    """Calculate relevance scores for vault query entries."""

    def __init__(self):
        self.now = datetime.now()
        self.thirty_days_ago = self.now - timedelta(days=30)

    def _get_text_content(self, entry: dict[str, Any]) -> str:
        """Extract all text content from entry for searching."""
        parts = []
        for key in ("text", "content", "body", "description", "summary"):
            if key in entry and isinstance(entry[key], str):
                parts.append(entry[key])
        return " ".join(parts)

    def _count_occurrences(self, text: str, keyword: str) -> int:
        """Count case-insensitive keyword occurrences in text."""
        lower_text = text.lower()
        lower_kw = keyword.lower()
        return lower_text.count(lower_kw)

    def _check_recency(self, entry: dict[str, Any]) -> bool:
        """Check if entry was created/modified in last 30 days."""
        date_keys = ("created_at", "updated_at", "modified_at", "date")
        for key in date_keys:
            if key in entry:
                val = entry[key]
                if isinstance(val, str):
                    try:
                        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                        # naive datetime for comparison
                        dt = dt.replace(tzinfo=None)
                        return dt >= self.thirty_days_ago
                    except (ValueError, TypeError):
                        pass
                elif isinstance(val, datetime):
                    return val >= self.thirty_days_ago
        return False

    def score(self, entry: dict[str, Any], query: str) -> int:
        """
        Calculate relevance score for a single entry.
        
        Args:
            entry: Dictionary with keys like text, tags, source_ref, title, etc.
            query: The search keyword/phrase
            
        Returns:
            Integer score (0 if below minimum threshold)
        """
        score = 0
        query_lower = query.lower()
        text = self._get_text_content(entry).lower()

        # Exact keyword match in text: +10
        if query_lower in text:
            score += 10

        # Multiple keyword occurrences: +1 per extra (max +5)
        extra_occurrences = self._count_occurrences(text, query) - 1
        if extra_occurrences > 0:
            score += min(extra_occurrences, 5)

        # Keyword in tags: +5
        tags = entry.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if query_lower in str(tag).lower():
                    score += 5
                    break

        # Keyword in source_ref: +3
        source_ref = entry.get("source_ref", "")
        if source_ref and query_lower in str(source_ref).lower():
            score += 3

        # Keyword in title/header: +8
        title = entry.get("title", "") or entry.get("header", "")
        if title and query_lower in str(title).lower():
            score += 8

        # Recency (last 30 days): +2
        if self._check_recency(entry):
            score += 2

        return score


def filter_and_rank(entries: list[dict[str, Any]], query: str, min_score: int = 3) -> list[dict[str, Any]]:
    """
    Filter entries by minimum relevance score and sort by score descending.
    
    Args:
        entries: List of vault entry dictionaries
        query: The search keyword/phrase
        min_score: Minimum score threshold (default: 3)
        
    Returns:
        Filtered and sorted list of entries, each with added '_score' key
    """
    scorer = RelevanceScorer()
    scored = []
    
    for entry in entries:
        score = scorer.score(entry, query)
        if score >= min_score:
            result = dict(entry)
            result["_score"] = score
            scored.append(result)
    
    # Sort by score descending
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored
