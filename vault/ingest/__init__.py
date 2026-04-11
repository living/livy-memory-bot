"""vault.ingest — compatibility facade for legacy ingest module + source-specific ingestors.

This package coexists with legacy `vault/ingest.py`.
To preserve existing imports (`from vault.ingest import ...`), we proxy
core ingest functions to the legacy module.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

# Load legacy module from ../ingest.py as a private module object.
_LEGACY_PATH = Path(__file__).resolve().parents[1] / "ingest.py"
_SPEC = importlib.util.spec_from_file_location("vault._legacy_ingest", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load legacy ingest module from {_LEGACY_PATH}")

_legacy = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_legacy)

# Mirror mutable globals used by tests/monkeypatching.
VAULT_ROOT = _legacy.VAULT_ROOT
DEFAULT_EVENTS = _legacy.DEFAULT_EVENTS


def _sync_globals() -> None:
    """Propagate patched globals in this facade to the legacy module."""
    _legacy.VAULT_ROOT = VAULT_ROOT
    _legacy.DEFAULT_EVENTS = DEFAULT_EVENTS


def load_events(path=DEFAULT_EVENTS):
    _sync_globals()
    return _legacy.load_events(path)


def map_signal_confidence(value):
    _sync_globals()
    return _legacy.map_signal_confidence(value)


def deduplicate_events(events):
    _sync_globals()
    return _legacy.deduplicate_events(events)


def extract_signal(event):
    _sync_globals()
    return _legacy.extract_signal(event)


def upsert_decision(decision):
    _sync_globals()
    return _legacy.upsert_decision(decision)


def upsert_concept(topic):
    _sync_globals()
    return _legacy.upsert_concept(topic)


def run_ingest(events_path=DEFAULT_EVENTS):
    _sync_globals()
    return _legacy.run_ingest(events_path)


# Source-specific ingest orchestrators
from .external_ingest import run_external_ingest  # noqa: E402

__all__ = [
    "VAULT_ROOT",
    "DEFAULT_EVENTS",
    "load_events",
    "map_signal_confidence",
    "deduplicate_events",
    "extract_signal",
    "upsert_decision",
    "upsert_concept",
    "run_ingest",
    "run_external_ingest",
]
