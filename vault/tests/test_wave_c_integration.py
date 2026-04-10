"""
vault/tests/test_wave_c_integration.py
======================================
TDD tests for C3.2: Wave C feature flags and observability integration.

Tests verify:
1. Feature flags WAVE_C_C1_ENABLED, WAVE_C_C2_ENABLED, WAVE_C_C3_ENABLED
   are read from environment with correct defaults (C1=True, C2=False, C3=False).
2. The pipeline return dict contains a wave_c_observer key with per-wave info.
"""
import os
import subprocess
import sys
from pathlib import Path


import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_events_file(tmp_path: Path) -> Path:
    """Create a minimal signal-events.jsonl with no real events."""
    path = tmp_path / "events.jsonl"
    path.write_text("")
    return path


def _run_in_subprocess(code: str, env_extra: dict | None = None) -> tuple[int, str, str]:
    """Run `code` as a subprocess; return (returncode, stdout, stderr)."""
    env = os.environ.copy()
    if env_extra:
        for k, v in env_extra.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# Feature flag defaults — verified via env-var parsing in a subprocess
# so each test gets a fresh interpreter (no stale module state).
# ---------------------------------------------------------------------------

class TestWaveCFeatureFlagDefaults:
    """C1 defaults True; C2 and C3 default False."""

    def test_c1_default_true(self, monkeypatch, tmp_path):
        """When WAVE_C_C1_ENABLED is not set, _get_wave_c_flag returns True."""
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault import pipeline as p
print(p._get_wave_c_flag("WAVE_C_C1_ENABLED", default=True))
"""
        monkeypatch.delenv("WAVE_C_C1_ENABLED", raising=False)
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert stdout.strip() == "True"

    def test_c2_default_false(self, monkeypatch, tmp_path):
        """When WAVE_C_C2_ENABLED is not set, _get_wave_c_flag returns False."""
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault import pipeline as p
print(p._get_wave_c_flag("WAVE_C_C2_ENABLED", default=False))
"""
        monkeypatch.delenv("WAVE_C_C2_ENABLED", raising=False)
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert stdout.strip() == "False"

    def test_c3_default_false(self, monkeypatch, tmp_path):
        """When WAVE_C_C3_ENABLED is not set, _get_wave_c_flag returns False."""
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault import pipeline as p
print(p._get_wave_c_flag("WAVE_C_C3_ENABLED", default=False))
"""
        monkeypatch.delenv("WAVE_C_C3_ENABLED", raising=False)
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert stdout.strip() == "False"


# ---------------------------------------------------------------------------
# Feature flag overrides from environment
# ---------------------------------------------------------------------------

class TestWaveCFeatureFlagEnvOverrides:
    """Feature flags respect WAVE_C_CN_ENABLED env var values."""

    @pytest.mark.parametrize("raw_value,expected_str", [
        ("true", "True"),
        ("false", "False"),
        ("True", "True"),
        ("False", "False"),
        ("1", "True"),
        ("0", "False"),
    ])
    def test_flag_from_env_parsed(self, monkeypatch, raw_value, expected_str):
        """Env var string value is parsed to boolean."""
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault import pipeline as p
result = p._get_wave_c_flag("WAVE_C_C1_ENABLED", default=True)
print(result)
"""
        monkeypatch.setenv("WAVE_C_C1_ENABLED", raw_value)
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert stdout.strip() == expected_str, f"WAVE_C_C1_ENABLED={raw_value!r} → {stdout.strip()!r}, expected {expected_str}"


# ---------------------------------------------------------------------------
# Pipeline return dict contains wave_c_observer
# ---------------------------------------------------------------------------

class TestWaveCObserverInReturnDict:
    """run_pipeline returns a dict with a 'wave_c_observer' key."""

    def test_return_dict_has_wave_c_observer_key(self, tmp_path):
        """Return dict includes wave_c_observer."""
        events_path = _make_minimal_events_file(tmp_path)
        vault_root = tmp_path / "vault"
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from pathlib import Path
from vault import pipeline as p
result = p.run_pipeline(
    events_path={str(events_path)!r},
    dry_run=True,
)
print(list(result.keys()))
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert "wave_c_observer" in stdout, f"wave_c_observer not in return keys: {stdout}"

    def test_wave_c_observer_is_dict(self, tmp_path):
        """wave_c_observer value is a dict."""
        events_path = _make_minimal_events_file(tmp_path)
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault import pipeline as p
result = p.run_pipeline(events_path={str(events_path)!r}, dry_run=True)
print(type(result["wave_c_observer"]).__name__)
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert stdout.strip() == "dict", f"wave_c_observer type: {stdout.strip()}"

    def test_wave_c_observer_contains_c1_c2_c3_keys(self, tmp_path):
        """wave_c_observer contains c1, c2, c3 keys."""
        events_path = _make_minimal_events_file(tmp_path)
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault import pipeline as p
result = p.run_pipeline(events_path={str(events_path)!r}, dry_run=True)
obs = result["wave_c_observer"]
print(sorted(obs.keys()))
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        keys_str = stdout.strip()
        assert "c1" in keys_str and "c2" in keys_str and "c3" in keys_str, \
            f"Missing c1/c2/c3 in wave_c_observer keys: {keys_str}"

    def test_wave_c_observer_reflects_default_flags(self, tmp_path):
        """c1 enabled=True; c2 and c3 enabled=False by default."""
        events_path = _make_minimal_events_file(tmp_path)
        # Clean env — no overrides
        code = f"""
import sys, os
sys.path.insert(0, {str(ROOT)!r})
for k in ["WAVE_C_C1_ENABLED", "WAVE_C_C2_ENABLED", "WAVE_C_C3_ENABLED"]:
    os.environ.pop(k, None)
from vault import pipeline as p
result = p.run_pipeline(events_path={str(events_path)!r}, dry_run=True)
obs = result["wave_c_observer"]
print(f"c1={{obs['c1']['enabled']}} c2={{obs['c2']['enabled']}} c3={{obs['c3']['enabled']}}")
"""
        returncode, stdout, stderr = _run_in_subprocess(code)
        assert returncode == 0, stderr
        assert stdout.strip() == "c1=True c2=False c3=False", \
            f"Unexpected default flags: {stdout.strip()}"

    def test_wave_c_observer_reflects_env_overrides(self, tmp_path, monkeypatch):
        """Env overrides are reflected in wave_c_observer enabled values."""
        events_path = _make_minimal_events_file(tmp_path)
        env_extra = {
            "WAVE_C_C1_ENABLED": "false",
            "WAVE_C_C2_ENABLED": "true",
            "WAVE_C_C3_ENABLED": "true",
        }
        code = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from vault import pipeline as p
result = p.run_pipeline(events_path={str(events_path)!r}, dry_run=True)
obs = result["wave_c_observer"]
print(f"c1={{obs['c1']['enabled']}} c2={{obs['c2']['enabled']}} c3={{obs['c3']['enabled']}}")
"""
        returncode, stdout, stderr = _run_in_subprocess(code, env_extra=env_extra)
        assert returncode == 0, stderr
        assert stdout.strip() == "c1=False c2=True c3=True", \
            f"Unexpected flag values from env: {stdout.strip()}"
