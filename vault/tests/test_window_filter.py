"""
Test vault/ingest/github_ingest.py — lookback window filter.
RED: tests document expected window filter behavior.
GREEN: implement is_within_window, is_outside_active_window.
REFACTOR: extract date math to helper.
"""
import pytest
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------

@pytest.fixture
def gh():
    import importlib.util
    from pathlib import Path

    module_path = Path(__file__).resolve().parents[1] / "ingest" / "github_ingest.py"
    spec = importlib.util.spec_from_file_location("github_ingest", module_path)
    gh_mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(gh_mod)
    return gh_mod


# ---------------------------------------------------------------------------
# is_within_window
# ---------------------------------------------------------------------------

class TestIsWithinWindow:

    def test_pr_merged_within_30_days(self, gh):
        recent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        result = gh.is_within_window(recent, window_days=30)
        assert result is True

    def test_pr_merged_outside_30_days(self, gh):
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        result = gh.is_within_window(old, window_days=30)
        assert result is False

    def test_pr_merged_exactly_at_boundary(self, gh):
        # Exactly at 30 days — inclusive boundary (>=)
        at_boundary = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        result = gh.is_within_window(at_boundary, window_days=30)
        assert result is True

    def test_pr_merged_one_day_past_boundary(self, gh):
        past = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        result = gh.is_within_window(past, window_days=30)
        assert result is False

    def test_90_day_window(self, gh):
        day60 = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        day100 = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        assert gh.is_within_window(day60, window_days=90) is True
        assert gh.is_within_window(day100, window_days=90) is False

    def test_180_day_window(self, gh):
        day150 = (datetime.now(timezone.utc) - timedelta(days=150)).isoformat()
        day200 = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        assert gh.is_within_window(day150, window_days=180) is True
        assert gh.is_within_window(day200, window_days=180) is False

    def test_355_day_window(self, gh):
        day300 = (datetime.now(timezone.utc) - timedelta(days=300)).isoformat()
        day400 = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        assert gh.is_within_window(day300, window_days=355) is True
        assert gh.is_within_window(day400, window_days=355) is False

    def test_none_timestamp(self, gh):
        result = gh.is_within_window(None, window_days=30)
        assert result is False

    def test_empty_string_timestamp(self, gh):
        result = gh.is_within_window("", window_days=30)
        assert result is False

    def test_invalid_timestamp(self, gh):
        result = gh.is_within_window("not-a-date", window_days=30)
        assert result is False

    def test_naive_datetime_is_utc_assumed(self, gh):
        # Naive datetime (no timezone) — should be treated as UTC
        naive = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S")
        result = gh.is_within_window(naive, window_days=30)
        assert result is True

    def test_is_within_window_returns_bool(self, gh):
        recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        assert isinstance(gh.is_within_window(recent, window_days=30), bool)


# ---------------------------------------------------------------------------
# is_outside_active_window (vault hygiene marker)
# ---------------------------------------------------------------------------

class TestOutsideActiveWindow:

    def test_outside_30_day_window(self, gh):
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        assert gh.is_outside_active_window(old, window_days=30) is True

    def test_within_30_day_window(self, gh):
        recent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        assert gh.is_outside_active_window(recent, window_days=30) is False

    def test_exactly_at_boundary(self, gh):
        at_boundary = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        # boundary is inclusive → NOT outside window
        assert gh.is_outside_active_window(at_boundary, window_days=30) is False

    def test_none_timestamp(self, gh):
        assert gh.is_outside_active_window(None, window_days=30) is False

    def test_inverse_of_is_within_window(self, gh):
        ts = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        within = gh.is_within_window(ts, window_days=30)
        outside = gh.is_outside_active_window(ts, window_days=30)
        assert within is False
        assert outside is True

    def test_different_windows_produce_different_results(self, gh):
        # 60 days ago: outside 30-day window, inside 90-day window
        ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        assert gh.is_outside_active_window(ts, window_days=30) is True
        assert gh.is_outside_active_window(ts, window_days=90) is False


# ---------------------------------------------------------------------------
# Window constants
# ---------------------------------------------------------------------------

class TestWindowConstants:
    """Document the four operational window values."""

    def test_standard_windows_are_defined(self, gh):
        assert gh.WINDOW_30_DAYS == 30
        assert gh.WINDOW_90_DAYS == 90
        assert gh.WINDOW_180_DAYS == 180
        assert gh.WINDOW_355_DAYS == 355

    def test_355_is_intentionally_near_yearly(self, gh):
        # 355 ≠ 365 — intentional non-calendar-year coupling
        assert gh.WINDOW_355_DAYS != 365
        assert 300 < gh.WINDOW_355_DAYS < 365
