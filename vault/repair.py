"""
vault/repair.py — Auto-repair for Memory Vault coverage gaps and orphan pages.
Phase 1C: closes gaps by generating stub concept pages and adds backlinks to orphans.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from vault.lint import (
    detect_coverage_gaps,
    detect_orphans,
    _all_pages,
    _extract_wikilinks,
    _read,
)

ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = ROOT / "memory" / "vault"


def _concept_frontmatter(concept_name: str, date_str: str) -> str:
    safe = concept_name.replace("_", " ").replace("-", " ").title()
    return f"""---
entity: {safe}
type: concept
confidence: unverified
sources: []
last_verified: {date_str}
verification_log: []
last_touched_by: livy-agent
draft: true
---
"""


def _generate_concept_page(vault_root: Path, concept_name: str) -> tuple[Path, bool]:
    """Create a stub concept page for a coverage gap. Returns (path, created)."""
    concepts_dir = vault_root / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)

    slug = concept_name.lower().strip().replace(" ", "-")
    path = concepts_dir / f"{slug}.md"

    if path.exists():
        return path, False

    date_str = datetime.now(timezone.utc).date().isoformat()
    frontmatter = _concept_frontmatter(concept_name, date_str)

    body_lines = [
        frontmatter,
        f"# {concept_name.capitalize()}",
        "",
        "## Summary",
        "_Stub — needs manual verification._",
        "",
        "## Evidence",
        "- pending",
        "",
        "## Links",
        "- none",
        "",
    ]
    path.write_text("\n".join(body_lines), encoding="utf-8")
    return path, True


def repair_gaps(vault_root: Path = VAULT_ROOT, gaps: list[dict] | None = None) -> dict:
    """Generate stub concept pages for coverage gaps."""
    if gaps is None:
        gaps = detect_coverage_gaps(vault_root)

    repaired = 0
    for gap in gaps:
        concept = gap.get("concept", "")
        if not concept:
            continue
        _, created = _generate_concept_page(vault_root, concept)
        if created:
            repaired += 1

    remaining_gaps = detect_coverage_gaps(vault_root)
    return {
        "gaps_repaired": repaired,
        "gaps_remaining": len(remaining_gaps),
    }


def _find_parent_candidates(vault_root: Path, orphan_name: str) -> list[Path]:
    """Find pages that can host a backlink to the orphan entity."""
    candidates = []
    orphan_lower = orphan_name.lower()
    for page in _all_pages(vault_root):
        text = _read(page)
        links = _extract_wikilinks(text)

        # 1) Strong signal: page mentions orphan name in plain text and doesn't link yet
        if page.stem != orphan_name and orphan_lower in text.lower() and orphan_name not in links:
            candidates.append(page)
            continue

        # 2) Fallback: concept page with same stem as orphan can always backlink entity
        if page.parent.name == "concepts" and page.stem == orphan_name and orphan_name not in links:
            candidates.append(page)

    return candidates


def _add_backlink(page: Path, orphan_name: str) -> None:
    """Append a backlink section to a page if not already present."""
    text = _read(page)
    orphan_title = orphan_name.replace("-", " ").replace("_", " ").title()

    wikilink = f"[[../entities/{orphan_name}|{orphan_title}]]"

    if wikilink in text or f"[[{orphan_name}" in text:
        return

    # Append to the Links section
    if "## Links" in text:
        lines = text.splitlines()
        out_lines: list[str] = []
        in_links = False
        links_done = False
        for line in lines:
            out_lines.append(line)
            if line.strip() == "## Links":
                in_links = True
            elif in_links and not links_done and line.strip().startswith("#"):
                out_lines.append(f"- {wikilink}")
                links_done = True
                in_links = False
        if out_lines[-1].strip() == "- none":
            out_lines[-1] = f"- {wikilink}"
        elif not links_done:
            out_lines.append(f"- {wikilink}")
        text = "\n".join(out_lines)
    else:
        text += f"\n\n## Links\n- {wikilink}\n"

    page.write_text(text, encoding="utf-8")


def repair_orphans(vault_root: Path = VAULT_ROOT, orphans: list[dict] | None = None) -> dict:
    """Add backlinks to orphan entities from parent pages that mention them."""
    if orphans is None:
        orphans = detect_orphans(vault_root)

    repaired = 0
    for orphan in orphans:
        name = orphan.get("page", "")
        if not name:
            continue
        parents = _find_parent_candidates(vault_root, name)
        if parents:
            _add_backlink(parents[0], name)
            repaired += 1

    remaining_orphans = detect_orphans(vault_root)
    return {
        "orphans_repaired": repaired,
        "orphans_remaining": len(remaining_orphans),
    }


def run_repair(vault_root: Path = VAULT_ROOT, dry_run: bool = False) -> dict:
    """Full repair pipeline: gaps + orphans."""
    gaps = detect_coverage_gaps(vault_root)
    orphans = detect_orphans(vault_root)

    gaps_repaired = 0
    orphans_repaired = 0

    if not dry_run:
        gap_result = repair_gaps(vault_root, gaps)
        gaps_repaired = gap_result["gaps_repaired"]

        orphan_result = repair_orphans(vault_root, orphans)
        orphans_repaired = orphan_result["orphans_repaired"]

    remaining_gaps = detect_coverage_gaps(vault_root)
    remaining_orphans = detect_orphans(vault_root)

    return {
        "gaps_repaired": gaps_repaired,
        "orphans_repaired": orphans_repaired,
        "gaps_remaining": len(remaining_gaps),
        "orphans_remaining": len(remaining_orphans),
        "repaired_at": datetime.now(timezone.utc).isoformat(),
    }
