"""
Rollback do Wiki v2 (spec Section 9.4).

Executa rollback via Gateway config.patch para desabilitar feature flag.
"""
from __future__ import annotations

import os
from typing import Any


WIKI_V2_FLAG = "WIKI_V2_ENABLED"


def rollback_wiki_v2() -> dict[str, Any]:
    """
    Executa rollback do feature wiki_v2 via Gateway config.patch.

    Spec format:
    {
      "action": "config.patch",
      "patch": {"features": {"wiki_v2": {"enabled": False}}}
    }

    Returns:
        dict com {success, patch, note}
    """
    patch = {"features": {"wiki_v2": {"enabled": False}}}

    return {
        "success": True,
        "patch": patch,
        "note": "Execute via gateway tool: gateway(action='config.patch', raw=json.dumps(patch), note='Rollback wiki_v2')",
    }


def is_wiki_v2_enabled() -> bool:
    """Checa se wiki_v2 está habilitada via feature flag."""
    return os.environ.get(WIKI_V2_FLAG, "false").lower() == "true"


def enable_wiki_v2() -> dict[str, Any]:
    """
    Habilita o feature wiki_v2 via config patch.

    Returns:
        dict com {success, patch, note}
    """
    patch = {"features": {"wiki_v2": {"enabled": True}}}

    return {
        "success": True,
        "patch": patch,
        "note": "Execute via gateway tool: gateway(action='config.patch', raw=json.dumps(patch), note='Enable wiki_v2')",
    }
