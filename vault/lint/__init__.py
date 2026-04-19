"""Compatibility exports for :mod:`vault.lint`.

This package path (``vault/lint/``) coexists with the legacy module file
(``vault/lint.py``). A number of imports in the repo use:

    from vault.lint import ...

Python resolves that to this package, so we re-export symbols from the legacy
module to preserve backward compatibility.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_LEGACY_PATH = Path(__file__).resolve().parents[1] / "lint.py"
_SPEC = importlib.util.spec_from_file_location("vault._lint_legacy", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load legacy lint module: {_LEGACY_PATH}")

_LEGACY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LEGACY)

for _name in dir(_LEGACY):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_LEGACY, _name)

__all__ = [name for name in globals() if not name.startswith("_")]
