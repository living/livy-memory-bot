"""Auto-fix common vault issues detected by lint scanner."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _all_existing_slugs(vault_root: Path) -> set[str]:
    """Collect all existing entity filenames (without .md) as a slug set."""
    slugs = set()
    for entities_sub in ["meetings", "persons", "projects", "cards", "prs"]:
        d = vault_root / "entities" / entities_sub
        if d.exists():
            for f in d.glob("*.md"):
                slugs.add(f.stem)
    return slugs


def auto_fix_orphan_links(vault_root: Path) -> dict[str, Any]:
    """Remove [[wiki-links]] pointing to non-existent entity files.

    Scans all .md files in the vault and removes links to missing entities.
    """
    existing = _all_existing_slugs(vault_root)
    fixes = {"orphan_links_removed": 0, "files_modified": 0}

    for md_file in vault_root.rglob("*.md"):
        if ".quarantine" in str(md_file) or ".cursors" in str(md_file):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        modified = False

        def _replace_link(m: re.Match) -> str:
            nonlocal modified
            slug = m.group(1).strip()
            found = slug in existing
            if not found:
                parts = slug.split(" ", 1)
                if len(parts) > 1 and parts[0].count("-") == 2:
                    title_slug = parts[1] if len(parts) > 1 else slug
                    found = title_slug in existing
            if found:
                return m.group(0)
            modified = True
            fixes["orphan_links_removed"] += 1
            return ""

        new_text = re.sub(r"\[\[([^\]]+)\]\]", _replace_link, text)

        if modified:
            new_text = re.sub(r"\n{3,}", "\n\n", new_text)
            md_file.write_text(new_text, encoding="utf-8")
            fixes["files_modified"] += 1

    return fixes
