#!/usr/bin/env python3
"""Tests for meetings_tldv_autoresearch.py"""
import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, 'scripts')

# Test compute_scores
def test_compute_scores():
    from meetings_tldv_autoresearch import compute_scores
    entries = [
        {"action": "semantic|decisões BAT", "rating": "up", "note": None},
        {"action": "semantic|decisões BAT", "rating": "up", "note": None},
        {"action": "semantic|decisões BAT", "rating": "down", "note": "faltou contexto"},
        {"action": "temporal|março", "rating": "up", "note": None},
    ]
    stats = compute_scores(entries)
    assert stats["semantic|decisões BAT"]["up"] == 2
    assert stats["semantic|decisões BAT"]["down"] == 1
    assert stats["semantic|decisões BAT"]["score"] == 1  # 2-1
    assert stats["temporal|março"]["score"] == 1
    print("test_compute_scores PASSED")

def test_generate_hypotheses():
    from meetings_tldv_autoresearch import generate_hypotheses
    stats = {
        "semantic|decisões BAT": {"score": 3, "up": 3, "down": 0},
        "temporal|março": {"score": -3, "up": 0, "down": 3},
        "semantic|reuniões": {"score": 0, "up": 1, "down": 1},
    }
    hypotheses = generate_hypotheses(stats)
    assert len(hypotheses) >= 1
    # Negative score should generate a hypothesis
    neg_hyp = [h for h in hypotheses if "score" in h and "-3" in h]
    assert len(neg_hyp) >= 1
    print("test_generate_hypotheses PASSED")

def test_build_markdown():
    from meetings_tldv_autoresearch import build_markdown
    stats = {
        "semantic|decisões BAT": {"score": 2, "up": 2, "down": 0, "notes": []},
    }
    md = build_markdown(stats, "2026-04-01", [])
    assert "score positivo" in md
    assert "decisões BAT" in md
    assert "+2" in md
    print("test_build_markdown PASSED")

if __name__ == "__main__":
    test_compute_scores()
    test_generate_hypotheses()
    test_build_markdown()
    print("\nAll tests PASSED")