#!/usr/bin/env python3
"""Tests for memory evolution features."""
import sys, subprocess, requests, tempfile, pathlib, time, os
from unittest.mock import patch, MagicMock
sys.path.insert(0, 'scripts')
sys.path.insert(0, 'skills/memoria-consolidation')

def test_health_check_all_healthy(monkeypatch):
    """When all 3 layers are up, health_check returns True."""
    from autoresearch_cron import health_check

    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: MagicMock(returncode=0))
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: MagicMock(status_code=200, json=lambda: {"status": "ok"}))

    with patch('pathlib.Path.exists', return_value=True):
        result = health_check()
    assert result == True

def test_health_check_claude_mem_down(monkeypatch):
    """When claude-mem is unreachable, health_check returns False."""
    from autoresearch_cron import health_check

    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: MagicMock(returncode=0))
    def raise_connection_error(*a, **kw):
        raise requests.ConnectionError("Connection refused")
    monkeypatch.setattr(requests, 'get', raise_connection_error)

    with patch('pathlib.Path.exists', return_value=True):
        result = health_check()
    assert result == False

def test_health_check_openclaw_memory_down(monkeypatch):
    """When openclaw memory status fails, health_check returns False."""
    from autoresearch_cron import health_check

    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: MagicMock(returncode=1, stderr="error"))
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: MagicMock(status_code=200, json=lambda: {"status": "ok"}))

    with patch('pathlib.Path.exists', return_value=True):
        result = health_check()
    assert result == False

def test_health_check_curated_dir_missing(monkeypatch):
    """When curated_dir doesn't exist, health_check returns False."""
    from autoresearch_cron import health_check

    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: MagicMock(returncode=0))
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: MagicMock(status_code=200, json=lambda: {"status": "ok"}))

    with patch('pathlib.Path.exists', return_value=False):
        result = health_check()
    assert result == False


def test_detect_violations_no_frontmatter():
    """File without YAML frontmatter gets violation score 8 (frontmatter only)."""
    from consolidate import detect_violations

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "test-file.md"
        # File with all sections present but no frontmatter
        f.write_text("## Status\n**Status:** ativo\n\n## Decisões\n-架构: REST — motivo: testing\n")

        violations = detect_violations([f], {})
        assert len(violations) == 1
        assert violations[0]["file"].name == "test-file.md"
        assert violations[0]["score"] == 8
        assert "missing-frontmatter" in violations[0]["violations"]


def test_detect_violations_with_frontmatter():
    """File with correct frontmatter has no violations."""
    from consolidate import detect_violations

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "test-file.md"
        # Real pattern: status and decision in frontmatter
        f.write_text("---\nname: test\ndescription: test desc\ntype: reference\nstatus: ativo\ndecision: REST API — motivo: simplicidade\n---\n\n# Test\n")

        violations = detect_violations([f], {})
        assert len(violations) == 0


def test_detect_violations_decisions_without_reason():
    """File with decision but no reason gets content score 3."""
    from consolidate import detect_violations

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "test-file.md"
        # decision in frontmatter without reason word
        f.write_text("---\nname: test\ndescription: test\ntype: reference\nstatus: ativo\ndecision: REST API chosen\n---\n\n# Test\n")

        violations = detect_violations([f], {})
        assert any(v["file"].name == "test-file.md" for v in violations)


def test_detect_violations_stale_file():
    """File older than 60 days gets score 10."""
    from consolidate import detect_violations

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "old-file.md"
        f.write_text("---\nname: old\ndescription: old\ntype: reference\n---\n\n## Status\n**Status:** ativo\n\n## Decisões\n- arquitetura: REST — motivo: testing\n")
        # Set mtime to 70 days ago
        old_mtime = time.time() - (70 * 86400)
        os.utime(f, (old_mtime, old_mtime))

        violations = detect_violations([f], {})
        assert any(v["file"].name == "old-file.md" and v["score"] == 10 for v in violations)


def test_detect_violations_prioritization():
    """Files with multiple violations get summed score."""
    from consolidate import detect_violations

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "multi-violation.md"
        # Only frontmatter present (violations: no status=4, no decisions=6)
        f.write_text("---\nname: test\ndescription: t\ntype: reference\n---\n\n# Test\n\nNo other sections.\n")

        violations = detect_violations([f], {})
        assert len(violations) == 1
        v = violations[0]
        # no status(4) + no decisions(6) = 10
        assert v["score"] == 10
        assert "missing-status" in v["violations"]
        assert "missing-decisoes" in v["violations"]


def test_detect_violations_daily_log_skipped():
    """Daily log files (YYYY-MM-DD) in curated are skipped."""
    from consolidate import detect_violations

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "2026-03-31.md"
        f.write_text("# Daily log\n\nContent without frontmatter.")

        violations = detect_violations([f], {})
        # Daily logs are skipped — no violations
        assert len(violations) == 0


def test_detect_violations_decision_in_frontmatter_no_reason():
    """decision: in frontmatter without reason word triggers violation."""
    from consolidate import detect_violations

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "frontmatter-decision.md"
        f.write_text("---\nname: test\ndescription: t\ntype: reference\nstatus: ativo\ndecision: REST API chosen\n---\n\n# Test\n")

        violations = detect_violations([f], {})
        assert len(violations) == 1
        assert "decisoes-no-reason" in violations[0]["violations"]


def test_detect_violations_decision_in_frontmatter_with_reason():
    """decision: in frontmatter with reason word is clean."""
    from consolidate import detect_violations

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "frontmatter-decision-ok.md"
        f.write_text("---\nname: test\ndescription: t\ntype: reference\nstatus: ativo\ndecision: REST API chosen — motivo: performance superior\n---\n\n# Test\n")

        violations = detect_violations([f], {})
        assert len(violations) == 0


def test_detect_violations_stale_with_proper_frontmatter():
    """Stale file (>60d) with proper frontmatter gets score 10."""
    from consolidate import detect_violations

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "old-file.md"
        f.write_text("---\nname: old\ndescription: old\ntype: reference\nstatus: ativo\ndecision: arquitetura: REST — motivo: simplicity\n---\n\n# Old file\n")
        # Set mtime to 70 days ago
        old_mtime = time.time() - (70 * 86400)
        os.utime(f, (old_mtime, old_mtime))

        violations = detect_violations([f], {})
        assert any(v["file"].name == "old-file.md" and v["score"] == 10 for v in violations)
        assert "stale:>60d" in violations[0]["violations"]
