#!/usr/bin/env python3
"""Tests for memory evolution features."""
import sys, subprocess, requests
from unittest.mock import patch, MagicMock
sys.path.insert(0, 'scripts')

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
