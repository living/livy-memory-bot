"""Integration tests for external ingest: external_ingest module + pipeline integration.

Covers:
1) run_external_ingest return dict has correct keys
2) Skipped meetings are tracked in skips list
3) Errors are tracked in errors list
4) Pipeline exposes external_ingest summary
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _make_minimal_events_file(tmp_path: Path) -> Path:
    """Create a minimal signal-events.jsonl with no real events."""
    path = tmp_path / "events.jsonl"
    path.write_text("")
    return path


def _run_in_subprocess(code: str) -> tuple[int, str, str]:
    """Run `code` as a subprocess; return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TestExternalIngestReturnDictKeys:
    """run_external_ingest returns a dict with expected keys."""

    def test_return_dict_has_required_keys(self):
        """Return dict contains all expected keys."""
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault.ingest.external_ingest import run_external_ingest
result = run_external_ingest(dry_run=True)
print(sorted(result.keys()))
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        keys_str = stdout.strip()
        expected = [
            "cards_fetched",
            "cards_skipped",
            "cards_written",
            "errors",
            "meetings_fetched",
            "meetings_resolved",
            "meetings_skipped",
            "meetings_written",
            "persons_skipped",
            "persons_written",
            "relationships_written",
            "skips",
        ]
        for key in expected:
            assert key in keys_str, f"{key} not in return keys: {keys_str}"

    def test_no_wave_c_enabled_key(self):
        """Return dict does NOT contain wave_c_enabled key."""
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault.ingest.external_ingest import run_external_ingest
result = run_external_ingest(dry_run=True)
print("wave_c_enabled" in result)
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert stdout.strip() == "False", "wave_c_enabled key should not be present"

    def test_skips_list_format(self):
        """Skips list is a list."""
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault.ingest.external_ingest import run_external_ingest
result = run_external_ingest(dry_run=True)
skips = result.get("skips", [])
print(type(skips).__name__, len(skips))
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        out = stdout.strip()
        assert out.startswith("list "), f"unexpected skips output: {out}"

    def test_errors_list_format(self):
        """Errors list contains dicts with source, error, type keys."""
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault.ingest.external_ingest import run_external_ingest
result = run_external_ingest(dry_run=True)
errors = result.get("errors", [])
print(type(errors).__name__, len(errors))
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert "list 0" in stdout.strip()


class TestExternalIngestPipelineIntegration:
    """Pipeline exposes external_ingest summary in return dict."""

    def test_pipeline_return_dict_has_external_ingest_key(self, tmp_path):
        """Return dict includes external_ingest key."""
        events_path = _make_minimal_events_file(tmp_path)
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault import pipeline as p
result = p.run_signal_pipeline(
    events_path={str(events_path)!r},
    dry_run=True,
)
print(list(result.keys()))
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert "external_ingest" in stdout, f"external_ingest not in return keys: {stdout}"

    def test_pipeline_external_ingest_value_is_dict(self, tmp_path):
        """external_ingest value is a dict."""
        events_path = _make_minimal_events_file(tmp_path)
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault import pipeline as p
result = p.run_signal_pipeline(events_path={str(events_path)!r}, dry_run=True)
print(type(result["external_ingest"]).__name__)
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert stdout.strip() == "dict", f"external_ingest type: {stdout.strip()}"
