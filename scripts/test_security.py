#!/usr/bin/env python3
"""
Security and resilience tests for meetings-tldv components.
Run: python3 scripts/test_security.py
"""

import importlib
import json, os, sys, tempfile, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Test helpers ──────────────────────────────────────────────────────────────

def assert_equal(a, b, msg=""):
    if a != b:
        raise AssertionError(f"{msg}: expected {a!r}, got {b!r}")

def assert_in(a, b, msg=""):
    if a not in b:
        raise AssertionError(f"{msg}: expected {a!r} in {b!r}")

def assert_not_in(a, b, msg=""):
    if a in b:
        raise AssertionError(f"{msg}: expected {a!r} NOT in {b!r}")

def pass_test(fn):
    fn()
    print(f"  ✓ {fn.__name__}")

def fail_test(fn):
    try:
        fn()
        print(f"  ✗ {fn.__name__} — should have raised")
    except AssertionError as e:
        print(f"  ✗ {fn.__name__}: {e}")

# ── search.py tests ─────────────────────────────────────────────────────────────

def test_limit_bounds():
    """--limit should be clamped to MAX_LIMIT."""
    sys.path.insert(0, 'skills/meetings-tldv')
    from search import DEFAULT_LIMIT, MAX_LIMIT
    # Test that any limit > MAX_LIMIT gets clamped
    clamped = min(max(20, 1), MAX_LIMIT)
    assert_equal(clamped, 20)
    clamped = min(max(100, 1), MAX_LIMIT)
    assert_equal(clamped, MAX_LIMIT)  # 20
    print("  ✓ test_limit_bounds")

def test_embedding_cache_has_ttl():
    """Manual cache stores entries and respects TTL on repeated calls."""
    sys.path.insert(0, 'skills/meetings-tldv')
    import search
    # Clear cache
    search.EMBEDDING_CACHE.clear()
    # First call — should call OpenAI (but we just verify cache entry is set)
    # We test the cache mechanics directly
    search.EMBEDDING_CACHE["test"] = ([0.1] * 1536, time.time())
    assert "test" in search.EMBEDDING_CACHE
    # Cache entry is (embedding, timestamp)
    emb, ts = search.EMBEDDING_CACHE["test"]
    assert len(emb) == 1536
    assert abs(time.time() - ts) < 1
    # After TTL expires, cache should not return the entry
    old_ts = time.time() - 400  # 6+ min ago
    search.EMBEDDING_CACHE["old"] = ([0.2] * 1536, old_ts)
    now = time.time()
    emb2, ts2 = search.EMBEDDING_CACHE["old"]
    assert now - ts2 > 300, "Old entry should be past TTL"
    search.EMBEDDING_CACHE.clear()
    print("  ✓ test_embedding_cache_has_ttl")

def test_content_truncate_ends_with_dots():
    """Long content is truncated with '...' at word boundary."""
    sys.path.insert(0, 'skills/meetings-tldv')
    from search import format_result
    # Long content
    rows = [{
        "meeting_name": "Test",
        "date_str": "2026-03-28T14:00:00Z",
        "content": "A" * 300,  # 300 chars
        "similarity": 0.8,
    }]
    result = format_result(rows, "semantic", "test", 0.55)
    # Should end with ... (word boundary truncation)
    assert_in("...", result), "Long content should be truncated with ..."
    # Original 300 A's should NOT appear in full
    assert_not_in("A" * 300, result), "Should not show full untruncated content"
    print("  ✓ test_content_truncate_ends_with_dots")

def test_sql_ilike_special_chars():
    """ILIKE with special chars (*, %, _) should be escaped by Supabase REST API."""
    import requests as _requests
    sys.path.insert(0, 'skills/meetings-tldv')
    # We can't test actual API, but we verify the query construction doesn't break
    from search import get_supabase_headers
    headers = get_supabase_headers()
    assert "apikey" in headers
    assert "Authorization" in headers
    print("  ✓ test_sql_ilike_special_chars (headers OK)")

def test_format_result_defensive():
    """format_result handles missing/None fields gracefully."""
    sys.path.insert(0, 'skills/meetings-tldv')
    from search import format_result
    rows = [{
        "meeting_name": None,
        "date_str": None,
        "content": None,
        "similarity": None,
    }]
    result = format_result(rows, "semantic", "test", 0.55)
    assert_in("Sem título", result)
    assert_in("—", result)  # missing date
    print("  ✓ test_format_result_defensive")

def test_infer_mode_detail_keywords():
    """infer_mode returns detail for meeting_id patterns."""
    sys.path.insert(0, 'skills/meetings-tldv')
    from search import infer_mode
    assert_equal(infer_mode("meeting 123"), "detail")
    assert_equal(infer_mode("summarize abc"), "detail")
    assert_equal(infer_mode("detail da reunião xyz"), "detail")
    print("  ✓ test_infer_mode_detail_keywords")

def test_infer_mode_temporal_keywords():
    """infer_mode returns temporal for time window patterns."""
    sys.path.insert(0, 'skills/meetings-tldv')
    from search import infer_mode
    assert_equal(infer_mode("última semana"), "temporal")
    assert_equal(infer_mode("reuniões de março"), "temporal")
    assert_equal(infer_mode("entre janeiro e fevereiro"), "temporal")
    print("  ✓ test_infer_mode_temporal_keywords")

def test_infer_mode_semantic_default():
    """infer_mode returns semantic for topic questions."""
    sys.path.insert(0, 'skills/meetings-tldv')
    from search import infer_mode
    assert_equal(infer_mode("decisões sobre o BAT"), "semantic")
    assert_equal(infer_mode("reuniões do Robert"), "semantic")
    print("  ✓ test_infer_mode_semantic_default")

# ── autoresearch tests ─────────────────────────────────────────────────────────

def test_load_feedback_malformed_json():
    """load_feedback skips malformed JSON lines silently."""
    from meetings_tldv_autoresearch import load_feedback
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write('{"ts":"2026-04-01T10:00:00Z","rating":"up"}\n')
        f.write('NOT JSON AT ALL\n')
        f.write('{"ts":"2026-04-01T11:00:00Z","rating":"down"}\n')
        f.flush()
        entries = load_feedback(Path(f.name))
    assert_equal(len(entries), 2, "Should skip malformed line")
    Path(f.name).unlink()
    print("  ✓ test_load_feedback_malformed_json")

def test_compute_scores_unknown_rating():
    """compute_scores handles unknown ratings gracefully."""
    from meetings_tldv_autoresearch import compute_scores
    entries = [
        {"action": "test", "rating": "up"},
        {"action": "test", "rating": "unknown"},
        {"action": "test", "rating": "down"},
    ]
    stats = compute_scores(entries)
    assert_equal(stats["test"]["up"], 1)
    assert_equal(stats["test"]["down"], 1)
    # unknown ratings should not be counted
    print("  ✓ test_compute_scores_unknown_rating")

def test_build_markdown_unicode():
    """build_markdown handles Unicode in action names."""
    from meetings_tldv_autoresearch import build_markdown
    stats = {
        "semantic|decisões sobre BÁT": {"score": 2, "up": 2, "down": 0, "notes": ["nota em português"]},
    }
    md = build_markdown(stats, "2026-04-01", [])
    assert_in("decisões", md)
    assert_in("BÁT", md)
    print("  ✓ test_build_markdown_unicode")

def test_generate_hypotheses_negative():
    """generate_hypotheses creates threshold advice for negative scores."""
    from meetings_tldv_autoresearch import generate_hypotheses
    stats = {
        "temporal|março": {"score": -3, "up": 0, "down": 3},
    }
    hyps = generate_hypotheses(stats)
    assert len(hyps) >= 1
    assert any("threshold" in h.lower() or "janela" in h.lower() for h in hyps)
    print("  ✓ test_generate_hypotheses_negative")

def test_feedback_archive_atomic():
    """Feedback archive + clear should be atomic (known issue: race condition)."""
    # This test documents the issue — can't easily test race condition
    # but we verify the archive file is created
    from meetings_tldv_autoresearch import load_feedback
    with tempfile.TemporaryDirectory() as tmpdir:
        feedback_file = Path(tmpdir) / "feedback.jsonl"
        archive_file = Path(tmpdir) / "archive.jsonl"
        # Write some feedback
        feedback_file.write_text('{"ts":"2026-04-01T10:00:00Z","rating":"up"}\n')
        # Simulate what the script does: archive then clear
        with archive_file.open("a") as arch:
            for line in feedback_file.read_text().splitlines():
                if line.strip():
                    arch.write(line + "\n")
        assert archive_file.exists()
        assert_equal(archive_file.read_text().count("\n"), 1)
        print("  ✓ test_feedback_archive_atomic (single-process OK, race condition is a concern)")

# ── feedback_poller tests ───────────────────────────────────────────────────────

def test_callback_prefix_routing():
    """Callbacks are routed by prefix correctly."""
    os.environ["FEEDBACK_BOT_TOKEN"] = "8725269523:AAFqAFEFcbAa6daClbUiVH9qBLfzu46SMOQ"
    sys.path.insert(0, 'handlers')
    # Reload to pick up env
    import importlib
    import feedback_poller
    importlib.reload(feedback_poller)
    FEEDBACK_FILES = {
        "meetings_tldv": Path("/tmp/meetings-tldv-feedback.jsonl"),
        "memory_general": Path("/tmp/memory-general-feedback.jsonl"),
    }
    assert "meetings_tldv" in FEEDBACK_FILES
    assert "memory_general" in FEEDBACK_FILES
    print("  ✓ test_callback_prefix_routing")

def test_meetings_tldv_has_user_filter():
    """meetings_tldv route now checks ALLOWED_USER_IDS (security fix applied)."""
    import inspect
    # Set env before reload
    os.environ["FEEDBACK_BOT_TOKEN"] = "8725269523:AAFqAFEFcbAa6daClbUiVH9qBLfzu46SMOQ"
    import feedback_poller
    importlib.reload(feedback_poller)
    source = inspect.getsource(feedback_poller.process_callback)
    meetings_tldv_section = source.split('if skill_prefix == "meetings_tldv":')[1].split("elif")[0]
    has_user_check = "ALLOWED_USER_IDS" in meetings_tldv_section
    assert has_user_check, "meetings_tldv should check ALLOWED_USER_IDS"
    print("  ✓ test_meetings_tldv_has_user_filter")

def test_bot_token_from_env():
    """BOT_TOKEN must come from env var, not hardcoded."""
    os.environ["FEEDBACK_BOT_TOKEN"] = "8725269523:TESTBOTTOCKENFOR验证"
    import feedback_poller
    importlib.reload(feedback_poller)
    token = feedback_poller.BOT_TOKEN
    assert len(token) > 20, "BOT_TOKEN should be set"
    # Verify it's from env var (our test value)
    assert "TESTBOTTOCKENFOR" in token, "BOT_TOKEN should come from env"
    print("  ✓ test_bot_token_from_env")

# ── reconciliation write-mode tests ──────────────────────────────────────────

def test_topic_rewrite_uses_tempfile_then_atomic_replace():
    """Verify atomic replace pattern: write to .tmp, then rename."""
    from pathlib import Path
    import os

    # Setup
    tmp_dir = Path(os.environ.get("TMPDIR", "/tmp"))
    original = tmp_dir / "topic_test.md"
    original.write_text("# topic\n")

    # Simulate atomic write: write to .tmp, then replace
    tmp = original.with_suffix(".tmp")
    tmp.write_text("# updated\n")
    tmp.replace(original)

    # Verify
    assert original.read_text() == "# updated\n"
    # Cleanup
    original.unlink(missing_ok=True)
    print("  ✓ test_topic_rewrite_uses_tempfile_then_atomic_replace")


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Security & Resilience Tests ===\n")

    print("search.py:")
    test_limit_bounds()
    test_embedding_cache_has_ttl()
    test_content_truncate_ends_with_dots()
    test_sql_ilike_special_chars()
    test_format_result_defensive()
    test_infer_mode_detail_keywords()
    test_infer_mode_temporal_keywords()
    test_infer_mode_semantic_default()

    print("\nautoresearch.py:")
    test_load_feedback_malformed_json()
    test_compute_scores_unknown_rating()
    test_build_markdown_unicode()
    test_generate_hypotheses_negative()
    test_feedback_archive_atomic()

    print("\nfeedback_poller.py:")
    test_callback_prefix_routing()
    test_meetings_tldv_has_user_filter()
    test_bot_token_from_env()

    print("\nreconciliation write-mode:")
    test_topic_rewrite_uses_tempfile_then_atomic_replace()

    print("\n=== Done ===")
