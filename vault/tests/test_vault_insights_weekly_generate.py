"""Integration tests for vault_insights_weekly_generate cron wiring."""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _claim(overrides=None):
    base = {
        "claim_id": "c-001",
        "entity_type": "project",
        "entity_id": "living/livy-memory-bot",
        "topic_id": None,
        "claim_type": "status",
        "text": "PR merged",
        "source": "github",
        "source_ref": {"source_id": "pr-1", "url": "https://github.com/living/livy-memory-bot/pull/1"},
        "evidence_ids": ["ev-1"],
        "author": "lincoln",
        "event_timestamp": "2026-04-19T12:00:00+00:00",
        "ingested_at": "2026-04-19T13:00:00+00:00",
        "confidence": 0.85,
        "privacy_level": "internal",
        "superseded_by": None,
        "supersession_reason": None,
        "supersession_version": None,
        "audit_trail": {"model_used": "test", "parser_version": "v1", "trace_id": "t1"},
    }
    if overrides:
        base.update(overrides)
    return base


class TestUsesSSOTClaims:
    """test_uses_ssot_claims_when_week_covered — verify claims-first pipeline."""

    def test_loads_from_state_claims(self, tmp_path, monkeypatch):
        # Set up a mock state with recent claims
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=2)).isoformat()
        state = {
            "claims": [
                _claim({"claim_id": "c-1", "source": "github", "event_timestamp": recent}),
                _claim({"claim_id": "c-2", "source": "tldv", "event_timestamp": recent}),
            ],
            "processed_event_keys": {},
            "processed_content_keys": {},
            "last_seen_at": {},
            "version": 1,
        }
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(state))

        # Patch state store
        monkeypatch.chdir(tmp_path)
        with patch("vault.insights.claim_inspector.load_state", return_value=state):
            from vault.insights.claim_inspector import extract_insights
            bundle = extract_insights(state["claims"])
            assert bundle.by_source["github"] == 1
            assert bundle.by_source["tldv"] == 1
            assert bundle.total == 2

    def test_personal_renderer_receives_bundle(self, tmp_path, monkeypatch):
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        recent = (now - timedelta(days=2)).isoformat()
        state = {
            "claims": [_claim({"claim_id": "c-1", "source": "github", "event_timestamp": recent})],
            "processed_event_keys": {},
            "processed_content_keys": {},
            "last_seen_at": {},
            "version": 1,
        }
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(state))

        monkeypatch.chdir(tmp_path)
        with patch("vault.insights.claim_inspector.load_state", return_value=state):
            from vault.insights.claim_inspector import extract_insights
            from vault.insights.renderers import render_personal
            bundle = extract_insights(state["claims"])
            text = render_personal(bundle)
            assert "github" in text
            assert "Insights Semanais" in text

    def test_group_html_renderer_receives_bundle(self, tmp_path, monkeypatch):
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=2)).isoformat()
        state = {
            "claims": [_claim({"claim_id": "c-1", "source": "github", "event_timestamp": recent})],
            "processed_event_keys": {},
            "processed_content_keys": {},
            "last_seen_at": {},
            "version": 1,
        }
        monkeypatch.chdir(tmp_path)
        with patch("vault.insights.claim_inspector.load_state", return_value=state):
            from vault.insights.claim_inspector import extract_insights
            from vault.insights.renderers import render_group_html
            bundle = extract_insights(state["claims"])
            html = render_group_html(bundle)
            assert "<html" in html
            assert "<svg" in html


class TestFallbackToMarkdown:
    """test_fallback_to_markdown_when_week_not_covered — verify fallback fires."""

    def test_fallback_when_state_has_no_claims_key(self, tmp_path, monkeypatch):
        # State without "claims" key
        state = {
            "processed_event_keys": {},
            "processed_content_keys": {},
            "last_seen_at": {},
            "version": 1,
        }
        monkeypatch.chdir(tmp_path)
        with patch("vault.insights.claim_inspector.load_state", return_value=state):
            from vault.insights.claim_inspector import extract_insights
            bundle = extract_insights(state.get("claims", []))
            assert bundle.total == 0
            assert bundle.by_source == {}

    def test_fallback_when_claims_are_old(self, tmp_path, monkeypatch):
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=30)).isoformat()
        state = {
            "claims": [_claim({"claim_id": "c-1", "source": "github", "event_timestamp": old})],
            "processed_event_keys": {},
            "processed_content_keys": {},
            "last_seen_at": {},
            "version": 1,
        }
        monkeypatch.chdir(tmp_path)
        with patch("vault.insights.claim_inspector.load_state", return_value=state):
            from vault.insights.claim_inspector import extract_insights, week_covered_by_claims
            covered = week_covered_by_claims(state["claims"])
            assert covered is False

    def test_fallback_triggers_group_report_generation(self, tmp_path, monkeypatch):
        """When SSOT has no recent claims, fallback markdown should still produce output."""
        state = {
            "claims": [],
            "processed_event_keys": {},
            "processed_content_keys": {},
            "last_seen_at": {},
            "version": 1,
        }
        monkeypatch.chdir(tmp_path)
        with patch("vault.insights.claim_inspector.load_state", return_value=state):
            from vault.insights.claim_inspector import extract_insights
            from vault.insights.renderers import render_personal, render_group_html
            bundle = extract_insights([])
            personal = render_personal(bundle)
            group_html = render_group_html(bundle)
            assert len(personal) > 0
            assert "<html" in group_html


class TestWeekCoverageFallbackLogic:
    """Verify the week_covered_by_claims fallback decision logic."""

    def test_empty_claims_triggers_fallback(self):
        from vault.insights.claim_inspector import week_covered_by_claims
        assert week_covered_by_claims([]) is False

    def test_recent_claims_means_covered(self):
        from vault.insights.claim_inspector import week_covered_by_claims
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=1)).isoformat()
        claims = [_claim({"claim_id": "c-1", "event_timestamp": recent})]
        assert week_covered_by_claims(claims) is True

    def test_old_claims_only_triggers_fallback(self):
        from vault.insights.claim_inspector import week_covered_by_claims
        old = datetime.now(timezone.utc) - timedelta(days=14)
        claims = [_claim({"claim_id": "c-1", "event_timestamp": old.isoformat()})]
        assert week_covered_by_claims(claims) is False


class TestWeeklyGenerateCronWiring:
    """Integration-level wiring tests for vault_insights_weekly_generate cron."""

    def test_cron_uses_ssot_claims_and_writes_html(self, tmp_path, monkeypatch):
        from vault.crons import vault_insights_weekly_generate as cron

        workspace = tmp_path
        vault_dir = workspace / "memory" / "vault"
        (vault_dir / "insights").mkdir(parents=True, exist_ok=True)
        (workspace / "state" / "identity-graph").mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=1)).isoformat()
        claims = [_claim({"claim_id": "c-1", "source": "github", "event_timestamp": recent})]

        monkeypatch.setenv("DRY_RUN_INSIGHTS", "true")
        monkeypatch.setattr(cron, "load_env", lambda: None)
        monkeypatch.setattr(cron, "_resolve_workspace", lambda: workspace)
        monkeypatch.setattr(cron, "_resolve_vault", lambda: vault_dir)

        # No outbound telegram during test
        monkeypatch.setattr(cron, "_send_telegram_message", lambda *_a, **_k: True)
        monkeypatch.setattr(cron, "_send_telegram_document", lambda *_a, **_k: True)

        with patch("vault.insights.claim_inspector.load_claims_with_fallback", return_value=(claims, False)):
            result = cron.main()

        assert result["used_fallback"] is False
        assert result["claims_total"] == 1
        files = list((vault_dir / "insights").glob("living-insights-*.html"))
        assert files, "expected HTML report file to be generated"
        assert "<html" in files[0].read_text(encoding="utf-8")

    def test_cron_fallback_path_sets_used_fallback_true(self, tmp_path, monkeypatch):
        from vault.crons import vault_insights_weekly_generate as cron

        workspace = tmp_path
        vault_dir = workspace / "memory" / "vault"
        (vault_dir / "insights").mkdir(parents=True, exist_ok=True)
        (workspace / "state" / "identity-graph").mkdir(parents=True, exist_ok=True)

        old = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        markdown_claims = [_claim({"claim_id": "c-md-1", "source": "trello", "event_timestamp": old})]

        monkeypatch.setenv("DRY_RUN_INSIGHTS", "true")
        monkeypatch.setattr(cron, "load_env", lambda: None)
        monkeypatch.setattr(cron, "_resolve_workspace", lambda: workspace)
        monkeypatch.setattr(cron, "_resolve_vault", lambda: vault_dir)

        with patch("vault.insights.claim_inspector.load_claims_with_fallback", return_value=(markdown_claims, True)):
            result = cron.main()

        assert result["used_fallback"] is True
        assert result["claims_total"] == 1
