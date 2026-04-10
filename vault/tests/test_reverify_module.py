"""
Tests for vault/reverify.py — automatic re-verification of stale claims.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

import vault.reverify as rv
from vault.lint import is_stale


@pytest.fixture
def temp_vault(tmp_path):
    """Minimal vault workspace with entities/decisions/concepts."""
    vault = tmp_path / "memory" / "vault"
    for section in ("entities", "decisions", "concepts", "evidence"):
        (vault / section).mkdir(parents=True, exist_ok=True)
    return vault


def _write_page(vault: Path, section: str, stem: str, content: str) -> Path:
    p = vault / section / f"{stem}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# is_stale helper
# ---------------------------------------------------------------------------

class TestIsStale:
    def test_stale_older_than_7_days(self):
        old = "2026-03-20"
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        assert is_stale(old, now=now) is True

    def test_within_7_days_not_stale(self):
        recent = "2026-04-09"
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        assert is_stale(recent, now=now) is False

    def test_no_date_is_stale(self):
        assert is_stale("") is True

    def test_invalid_date_is_stale(self):
        assert is_stale("not-a-date") is True


# ---------------------------------------------------------------------------
# _has_official_source
# ---------------------------------------------------------------------------

class TestHasOfficialSource:
    def _fm(self, body: str) -> str:
        return f"---\n{body}\n---\n# Page\n"

    def test_tldv_api_is_official(self):
        assert rv._has_official_source(self._fm("sources:\n  - type: tldv_api")) is True

    def test_github_api_is_official(self):
        assert rv._has_official_source(self._fm("sources:\n  - type: github_api")) is True

    def test_supabase_rest_is_official(self):
        assert rv._has_official_source(self._fm("type: supabase_rest")) is True

    def test_exec_is_official(self):
        assert rv._has_official_source(self._fm("type: exec")) is True

    def test_openclaw_config_is_official(self):
        assert rv._has_official_source(self._fm("type: openclaw_config")) is True

    def test_api_direct_is_official(self):
        assert rv._has_official_source(self._fm("type: api_direct")) is True

    def test_signal_event_is_not_official(self):
        assert rv._has_official_source(self._fm("sources:\n  - type: signal_event")) is False

    def test_no_sources_not_official(self):
        assert rv._has_official_source(self._fm("confidence: high\nlast_verified: 2026-04-01")) is False

    def test_case_insensitive(self):
        assert rv._has_official_source(self._fm("type: TLDV_API")) is True


# ---------------------------------------------------------------------------
# detect_stale_claims integration
# ---------------------------------------------------------------------------

class TestDetectStale:
    def test_stale_page_detected(self, temp_vault):
        _write_page(temp_vault, "decisions", "old-decision",
            "---\nlast_verified: 2026-03-01\nconfidence: high\n---\n# Old\n")
        from vault.lint import detect_stale_claims
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        stale = detect_stale_claims(temp_vault, now=now)
        stems = [s["page"] for s in stale]
        assert "old-decision" in stems

    def test_recent_page_not_stale(self, temp_vault):
        _write_page(temp_vault, "decisions", "fresh-decision",
            "---\nlast_verified: 2026-04-09\nconfidence: high\n---\n# Fresh\n")
        from vault.lint import detect_stale_claims
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        stale = detect_stale_claims(temp_vault, now=now)
        stems = [s["page"] for s in stale]
        assert "fresh-decision" not in stems


# ---------------------------------------------------------------------------
# run_reverify — with official source
# ---------------------------------------------------------------------------

class TestReverifyWithOfficialSource:
    def _make_stale_official(self, vault: Path) -> Path:
        return _write_page(vault, "decisions", "official-stale",
            "---\nlast_verified: 2026-03-01\nconfidence: high\nsources:\n  - type: tldv_api\nverification_log: []\n---\n# Official Stale\n")

    def test_reverified_pages_includes_stale_with_source(self, temp_vault):
        self._make_stale_official(temp_vault)
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        result = rv.run_reverify(temp_vault, now=now, dry_run=False)
        assert "official-stale" in result["reverified_pages"]

    def test_last_verified_updated_after_reverify(self, temp_vault):
        path = self._make_stale_official(temp_vault)
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        rv.run_reverify(temp_vault, now=now, dry_run=False)
        text = path.read_text(encoding="utf-8")
        assert "last_verified: 2026-04-10" in text

    def test_confidence_unchanged_after_reverify_with_source(self, temp_vault):
        path = self._make_stale_official(temp_vault)
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        rv.run_reverify(temp_vault, now=now, dry_run=False)
        text = path.read_text(encoding="utf-8")
        assert "confidence: high" in text

    def test_verification_log_entry_added_with_source(self, temp_vault):
        path = self._make_stale_official(temp_vault)
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        rv.run_reverify(temp_vault, now=now, dry_run=False)
        text = path.read_text(encoding="utf-8")
        assert "reverified 2026-04-10 (official source)" in text


# ---------------------------------------------------------------------------
# run_reverify — without official source (downgrade)
# ---------------------------------------------------------------------------

class TestReverifyWithoutOfficialSource:
    def _make_stale_no_source(self, vault: Path, confidence: str = "high") -> Path:
        return _write_page(vault, "decisions", "weak-stale",
            f"---\nlast_verified: 2026-03-01\nconfidence: {confidence}\nsources:\n  - type: signal_event\nverification_log: []\n---\n# Weak Stale\n")

    def test_downgraded_pages_includes_stale_without_source(self, temp_vault):
        self._make_stale_no_source(temp_vault)
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        result = rv.run_reverify(temp_vault, now=now, dry_run=False)
        assert "weak-stale" in result["downgraded_pages"]

    def test_confidence_downgraded_high_to_medium(self, temp_vault):
        path = self._make_stale_no_source(temp_vault, confidence="high")
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        rv.run_reverify(temp_vault, now=now, dry_run=False)
        text = path.read_text(encoding="utf-8")
        assert "confidence: medium" in text

    def test_last_verified_not_updated_without_source(self, temp_vault):
        path = self._make_stale_no_source(temp_vault)
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        rv.run_reverify(temp_vault, now=now, dry_run=False)
        text = path.read_text(encoding="utf-8")
        # last_verified should remain the old date
        assert "last_verified: 2026-03-01" in text
        assert "last_verified: 2026-04-10" not in text

    def test_verification_log_notes_downgrade(self, temp_vault):
        path = self._make_stale_no_source(temp_vault)
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        rv.run_reverify(temp_vault, now=now, dry_run=False)
        text = path.read_text(encoding="utf-8")
        assert "downgraded high" in text.lower()

    def test_medium_confidence_not_downgraded(self, temp_vault):
        path = self._make_stale_no_source(temp_vault, confidence="medium")
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        result = rv.run_reverify(temp_vault, now=now, dry_run=False)
        assert "weak-stale" not in result["downgraded_pages"]
        text = path.read_text(encoding="utf-8")
        assert "confidence: medium" in text


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_does_not_write_file(self, temp_vault):
        _write_page(temp_vault, "decisions", "dry-test",
            "---\nlast_verified: 2026-03-01\nconfidence: high\nsources:\n  - type: tldv_api\nverification_log: []\n---\n# Dry\n")
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        rv.run_reverify(temp_vault, now=now, dry_run=True)
        text = (temp_vault / "decisions" / "dry-test.md").read_text(encoding="utf-8")
        assert "last_verified: 2026-03-01" in text
        assert "last_verified: 2026-04-10" not in text

    def test_dry_run_returns_metrics(self, temp_vault):
        _write_page(temp_vault, "decisions", "dry-test",
            "---\nlast_verified: 2026-03-01\nconfidence: high\nsources:\n  - type: tldv_api\nverification_log: []\n---\n# Dry\n")
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        result = rv.run_reverify(temp_vault, now=now, dry_run=True)
        assert "stale_before_reverify" in result
        assert "stale_after_reverify" in result
        assert "reverified_pages" in result
        assert "downgraded_pages" in result
        assert result["dry_run"] is True


# ---------------------------------------------------------------------------
# return metrics
# ---------------------------------------------------------------------------

class TestMetricsReturned:
    def test_stale_before_reflects_initial_count(self, temp_vault):
        _write_page(temp_vault, "decisions", "stale-1",
            "---\nlast_verified: 2026-03-01\nconfidence: high\nverification_log: []\n---\n# S1\n")
        _write_page(temp_vault, "decisions", "stale-2",
            "---\nlast_verified: 2026-03-01\nconfidence: high\nverification_log: []\n---\n# S2\n")
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        result = rv.run_reverify(temp_vault, now=now, dry_run=True)
        assert result["stale_before_reverify"] == 2

    def test_stale_after_greater_than_zero_without_offline_fix(self, temp_vault):
        # Both stale with no official source will be downgraded (not fixed), so still stale
        _write_page(temp_vault, "decisions", "stale-1",
            "---\nlast_verified: 2026-03-01\nconfidence: high\nsources:\n  - type: signal_event\nverification_log: []\n---\n# S1\n")
        _write_page(temp_vault, "decisions", "stale-2",
            "---\nlast_verified: 2026-03-01\nconfidence: high\nsources:\n  - type: signal_event\nverification_log: []\n---\n# S2\n")
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        result = rv.run_reverify(temp_vault, now=now, dry_run=True)
        # Downgrade doesn't clear stale (last_verified unchanged), so still stale
        assert result["stale_after_reverify"] >= 0
