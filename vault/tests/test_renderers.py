"""Tests for vault/insights/renderers.py."""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _bundle(overrides=None):
    from vault.insights.claim_inspector import InsightsBundle, InsightsContradiction, InsightsAlert
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    base = InsightsBundle(
        total=10,
        by_source={"github": 6, "tldv": 2, "trello": 2},
        active=9,
        superseded_total=1,
        new_this_week={"github": 3, "tldv": 1, "trello": 1},
        superseded_this_week=[{
            "claim_id": "c-sup-1",
            "entity_id": "living/repo",
            "superseded_by": "c-new-1",
            "supersession_reason": "newer version",
            "event_timestamp": week_ago.isoformat(),
        }],
        contradictions=[
            InsightsContradiction(
                entity_id="living/livy-memory-bot",
                claim_type="status",
                delta=0.4,
                claim_old={"claim_id": "c-old", "confidence": 0.3, "text": "initial PR"},
                claim_new={"claim_id": "c-new", "confidence": 0.7, "text": "updated after review"},
            )
        ],
        alerts=[
            InsightsAlert(level="warning", message="trello: 3 supersessions esta semana (taxa elevada)"),
        ],
        week_start=week_ago.strftime("%Y-%m-%d"),
        week_end=now.strftime("%Y-%m-%d"),
    )
    return base


class TestRenderPersonalMarkdown:
    """test_render_personal_markdown — verify personal text output structure."""

    def test_renders_header(self):
        from vault.insights.renderers import render_personal
        bundle = _bundle()
        text = render_personal(bundle)
        assert "Insights Semanais" in text
        assert "Lincoln" in text
        assert bundle.week_start in text
        assert bundle.week_end in text

    def test_renders_source_counts(self):
        from vault.insights.renderers import render_personal
        bundle = _bundle()
        text = render_personal(bundle)
        assert "github" in text
        assert "tldv" in text
        assert "trello" in text

    def test_renders_active_and_superseded(self):
        from vault.insights.renderers import render_personal
        bundle = _bundle()
        text = render_personal(bundle)
        assert "Ativos:" in text or "Ativos" in text
        assert "Superseded" in text or "Supersession" in text

    def test_renders_new_this_week(self):
        from vault.insights.renderers import render_personal
        bundle = _bundle()
        text = render_personal(bundle)
        assert "Novos" in text or "github" in text  # new github claims section

    def test_renders_supersessions(self):
        from vault.insights.renderers import render_personal
        bundle = _bundle()
        text = render_personal(bundle)
        assert "supersession" in text.lower() or "Supersession" in text

    def test_renders_contradictions(self):
        from vault.insights.renderers import render_personal
        bundle = _bundle()
        text = render_personal(bundle)
        assert "Contradi" in text or "Contradiction" in text

    def test_renders_alerts(self):
        from vault.insights.renderers import render_personal
        bundle = _bundle()
        text = render_personal(bundle)
        assert "Alerts" in text or "Alert" in text or "trello" in text

    def test_renders_emoji(self):
        from vault.insights.renderers import render_personal
        bundle = _bundle()
        text = render_personal(bundle)
        assert any(c in text for c in ("🧠", "⚠️", "?", "🔴", "✅", "📊"))


class TestRenderPersonalSoftLimit4096:
    """test_render_personal_soft_limit_4096 — verify soft limit doesn't crash."""

    def test_very_large_bundle_renders_without_error(self):
        from vault.insights.claim_inspector import InsightsBundle, InsightsContradiction, InsightsAlert
        from vault.insights.renderers import render_personal
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        # Many sources
        many_sources = {f"source_{i}": 100 for i in range(50)}
        many_new = {f"source_{i}": 50 for i in range(50)}
        bundle = InsightsBundle(
            total=5000,
            by_source=many_sources,
            active=4500,
            superseded_total=500,
            new_this_week=many_new,
            superseded_this_week=[],
            contradictions=[],
            alerts=[InsightsAlert(level="info", message="x") for x in range(100)],
            week_start=week_ago.strftime("%Y-%m-%d"),
            week_end=now.strftime("%Y-%m-%d"),
        )
        # Should not raise — soft limit truncates gracefully
        text = render_personal(bundle)
        assert len(text) > 0

    def test_truncated_bundle_under_limit(self):
        from vault.insights.claim_inspector import InsightsBundle
        from vault.insights.renderers import render_personal
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        # Normal bundle should stay under 4096
        bundle = _bundle()
        text = render_personal(bundle)
        assert len(text) <= 4096


class TestRenderGroupHtml:
    """test_render_group_html — verify group HTML structure."""

    def test_renders_complete_html(self):
        from vault.insights.renderers import render_group_html
        bundle = _bundle()
        html = render_group_html(bundle)
        assert html.startswith("<!DOCTYPE html>") or html.startswith("<html")
        assert "</html>" in html

    def test_contains_style_block(self):
        from vault.insights.renderers import render_group_html
        bundle = _bundle()
        html = render_group_html(bundle)
        assert "<style" in html or "style>" in html

    def test_contains_svg_chart(self):
        from vault.insights.renderers import render_group_html
        bundle = _bundle()
        html = render_group_html(bundle)
        assert "<svg" in html

    def test_contains_title_with_date_range(self):
        from vault.insights.renderers import render_group_html
        bundle = _bundle()
        html = render_group_html(bundle)
        assert bundle.week_start in html
        assert bundle.week_end in html

    def test_contains_source_counts(self):
        from vault.insights.renderers import render_group_html
        bundle = _bundle()
        html = render_group_html(bundle)
        assert "github" in html.lower()
        assert "tldv" in html.lower()
        assert "trello" in html.lower()

    def test_contains_supersessions_section(self):
        from vault.insights.renderers import render_group_html
        bundle = _bundle()
        html = render_group_html(bundle)
        html_lower = html.lower()
        assert any(k in html_lower for k in ("supersession", "superseded", "replaced"))

    def test_contains_alerts_section(self):
        from vault.insights.renderers import render_group_html
        bundle = _bundle()
        html = render_group_html(bundle)
        html_lower = html.lower()
        assert any(k in html_lower for k in ("alert", "warning", "trello"))

    def test_is_self_contained(self):
        from vault.insights.renderers import render_group_html
        bundle = _bundle()
        html = render_group_html(bundle)
        # No external CSS/JS links — all inline
        assert "cdn." not in html.lower()
        assert "https://" not in html or html.count("https://") == 0  # no external deps
