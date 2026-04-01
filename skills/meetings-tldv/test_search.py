#!/usr/bin/env python3
import sys
sys.path.insert(0, 'skills/meetings-tldv')

def test_infer_mode():
    from search import infer_mode
    # detail cases
    assert infer_mode("meeting 123") == "detail"
    assert infer_mode("summarize meeting abc") == "detail"
    assert infer_mode("detail da reunião xyz") == "detail"
    # temporal cases
    assert infer_mode("última semana") == "temporal"
    assert infer_mode("reuniões de março") == "temporal"
    assert infer_mode("entre janeiro e fevereiro") == "temporal"
    # semantic (default)
    assert infer_mode("decisões sobre o BAT") == "semantic"
    assert infer_mode("reuniões do Robert") == "semantic"
    print("test_infer_mode PASSED")

def test_query_recency_ts():
    from search import query_recency_ts_from_text
    import datetime
    result = query_recency_ts_from_text("última semana")
    assert result is not None
    # Should be ~7 days ago
    age_days = (datetime.datetime.now().timestamp() - result) / 86400
    assert 6.5 < age_days < 7.5, f"Expected ~7 days, got {age_days}"
    # No temporal info
    assert query_recency_ts_from_text("decisões sobre o BAT") is None
    print("test_query_recency_ts PASSED")

def test_hybrid_score():
    from search import hybrid_score
    import datetime
    now = datetime.datetime.now()
    # High similarity, recent
    score = hybrid_score(now, 0.9, now.timestamp())
    assert 0.7 < score < 1.0, f"Expected high score, got {score}"
    # No similarity data
    score = hybrid_score(now, None, None)
    assert score == 0.5, f"Expected neutral 0.5, got {score}"
    print("test_hybrid_score PASSED")

def test_format_result_empty():
    from search import format_result
    result = format_result([], "semantic", "test query", 0.55)
    assert "Nenhuma reunião encontrada" in result
    print("test_format_result_empty PASSED")

def test_format_result_with_rows():
    from search import format_result
    rows = [{
        "meeting_name": "Reunião BAT",
        "date_str": "2026-03-28T14:00:00Z",
        "content": "Robert pediu mudança no schedule.",
        "participants": ["Lincoln", "Robert"],
        "importance": "high",
        "similarity": 0.87,
    }]
    result = format_result(rows, "semantic", "decisões BAT", 0.55)
    assert "Reuniões — TLDV" in result
    assert "Reunião BAT" in result
    assert "0.87" in result
    assert "Lincoln, Robert" in result
    print("test_format_result_with_rows PASSED")

def test_dry_run_inference(capsys=None):
    import subprocess
    result = subprocess.run(
        ["python3", "skills/meetings-tldv/search.py", "--dry-run", "--query", "últimas reuniões de março"],
        capture_output=True, text=True, cwd="/home/lincoln/.openclaw/workspace-livy-memory",
    )
    assert result.returncode == 0
    assert "DRY RUN" in result.stdout or "mode=" in result.stdout
    print("test_dry_run_inference PASSED")

if __name__ == "__main__":
    test_infer_mode()
    test_query_recency_ts()
    test_hybrid_score()
    test_format_result_empty()
    test_format_result_with_rows()
    test_dry_run_inference()
    print("\nAll tests PASSED")
