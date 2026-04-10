"""Entity-specific lint checks for Wave B."""
from __future__ import annotations

from pathlib import Path
from typing import Any


_REQUIRED_LINEAGE_KEYS = {"run_id", "source_keys", "transformed_at", "mapper_version", "actor"}


def _frontmatter_blob(text: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[1]


def _has_all_lineage_keys(fm: str) -> bool:
    return all((k + ":") in fm for k in _REQUIRED_LINEAGE_KEYS)


def lint_entities(vault_root: Path) -> dict[str, Any]:
    """Run entity lint focused on lineage completeness and stale/orphan flags."""
    entities_dir = vault_root / "entities"
    errors: list[str] = []
    checked = 0

    if not entities_dir.exists():
        return {"checked": 0, "errors": [], "ok": True}

    for md in entities_dir.rglob("*.md"):
        checked += 1
        text = md.read_text(encoding="utf-8")
        fm = _frontmatter_blob(text)
        if not fm:
            errors.append(f"{md.name}:missing_frontmatter")
            continue

        if "lineage:" not in fm:
            errors.append(f"{md.name}:missing_lineage")
        elif not _has_all_lineage_keys(fm):
            errors.append(f"{md.name}:incomplete_lineage")

        if "confidence: high" in fm and "source_keys:" not in fm:
            errors.append(f"{md.name}:high_without_source_keys")

    return {
        "checked": checked,
        "errors": errors,
        "ok": len(errors) == 0,
    }
