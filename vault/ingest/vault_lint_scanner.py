"""Vault lint scanner — detect orphans, stale, gaps, contradictions."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict


class LintReport(TypedDict, total=False):
    orphans: list[str]
    stale: list[str]
    gaps: list[str]
    contradictions: list[dict[str, Any]]
    suggestions: list[dict[str, Any]]
    metrics: dict[str, Any]


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Simple YAML frontmatter parser (--- delimited).

    Returns a dict with scalar values and list values for list fields.
    """
    m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return {}
    fm: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in m.group(1).splitlines():
        # Indented list item under a list key
        if current_list_key and re.match(r'^\s{2}-\s+(.+)', line):
            item_m = re.match(r'^\s{2}-\s+(.+)', line)
            if item_m:
                fm[current_list_key].append(item_m.group(1).strip())
            continue
        # Reset list tracking on non-indented lines
        current_list_key = None
        if ":" in line and not line.startswith("  "):
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if v == "":
                # Potential list key — initialise empty list
                fm[k] = []
                current_list_key = k
            else:
                fm[k] = v
    return fm


def _scan_entities(vault_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Walk entities/ and collect (path, frontmatter) pairs."""
    entities: list[tuple[Path, dict[str, Any]]] = []
    entities_dir = vault_root / "entities"
    if not entities_dir.exists():
        return entities
    for f in entities_dir.rglob("*.md"):
        fm = _parse_frontmatter(f.read_text(encoding="utf-8"))
        fm["_path"] = str(f.relative_to(vault_root))
        entities.append((f, fm))
    return entities


def _scan_concepts(vault_root: Path) -> set[str]:
    """Collect concept id_canonicals from concepts/ directory."""
    concepts: set[str] = set()
    concepts_dir = vault_root / "concepts"
    if not concepts_dir.exists():
        return concepts
    for f in concepts_dir.rglob("*.md"):
        fm = _parse_frontmatter(f.read_text(encoding="utf-8"))
        cid = fm.get("id_canonical")
        if cid:
            concepts.add(str(cid))
    return concepts


def _read_index_paths(vault_root: Path) -> set[str]:
    """Parse index.md for registered entity paths (relative to vault root)."""
    idx = vault_root / "index.md"
    if not idx.exists():
        return set()
    paths: set[str] = set()
    for line in idx.read_text(encoding="utf-8").splitlines():
        # Match Markdown table rows like: | [Title](path/to/file.md) |
        lm = re.search(r'\]\(([^)]+)\)', line)
        if lm:
            paths.add(lm.group(1))
    return paths


def _count_relationships(vault_root: Path) -> tuple[int, dict[str, int]]:
    """Count relationships from relationships/*.json files.

    Returns (total_count, crosslink_breakdown) where crosslink_breakdown
    contains counts for card-person, card-project, pr-person, pr-project.
    """
    import json
    rel_dir = vault_root / "relationships"
    if not rel_dir.exists():
        return 0, {}
    total = 0
    breakdown: dict[str, int] = {}
    crosslink_files = {"card-person.json", "card-project.json", "pr-person.json", "pr-project.json"}
    for f in rel_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            edges = data.get("edges", [])
            count = len(edges)
            total += count
            if f.name in crosslink_files:
                breakdown[f.name.replace(".json", "")] = count
        except (json.JSONDecodeError, OSError):
            pass
    return total, breakdown

def run_lint_scans(vault_root: Path) -> LintReport:
    """Run all lint scans and return a structured report.

    Checks:
    - orphans: entities present on disk but missing from index.md
    - stale: entities with last_seen_at older than 30 days
    - gaps: concept IDs referenced in entity frontmatter but without their own concepts/ page
    - contradictions: multiple entity files sharing an id_canonical with conflicting confidence
    """
    entities = _scan_entities(vault_root)
    concepts = _scan_concepts(vault_root)
    index_paths = _read_index_paths(vault_root)

    # ── Orphans ────────────────────────────────────────────────────────────────
    # Any entity whose relative path (from vault root) is not registered in index.md
    orphans: list[str] = []
    for _f, fm in entities:
        rel = fm.get("_path", "")
        if rel not in index_paths:
            orphans.append(rel)

    # ── Stale ──────────────────────────────────────────────────────────────────
    # Entities with last_seen_at > 30 days ago
    stale: list[str] = []
    now = datetime.now(timezone.utc)
    for _f, fm in entities:
        last_seen = fm.get("last_seen_at")
        if last_seen:
            try:
                # Handle "Z" suffix (Python <3.11 fromisoformat doesn't accept Z)
                ts_str = str(last_seen).replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_str)
                if (now - ts).days > 30:
                    stale.append(fm.get("_path", ""))
            except (ValueError, TypeError):
                pass

    # ── Gaps ───────────────────────────────────────────────────────────────────
    # Concepts listed in entity frontmatter `concepts:` field that have no concepts/ page
    mentioned_concepts: set[str] = set()
    for _f, fm in entities:
        concepts_field = fm.get("concepts")
        if isinstance(concepts_field, list):
            for c in concepts_field:
                mentioned_concepts.add(str(c).strip())
    gaps: list[str] = [c for c in mentioned_concepts if c not in concepts]

    # ── Contradictions ─────────────────────────────────────────────────────────
    # Multiple files share the same id_canonical but disagree on `confidence`
    by_id: dict[str, list[dict[str, Any]]] = {}
    for _f, fm in entities:
        cid = fm.get("id_canonical")
        if cid:
            by_id.setdefault(str(cid), []).append(fm)

    contradictions: list[dict[str, Any]] = []
    for cid, fms in by_id.items():
        if len(fms) > 1:
            confidences = {fm.get("confidence", "") for fm in fms}
            if len(confidences) > 1:
                contradictions.append({
                    "id_canonical": cid,
                    "files": [fm["_path"] for fm in fms],
                    "confidences": sorted(confidences),
                })

    relationships, crosslink_breakdown = _count_relationships(vault_root)

    metrics: dict[str, Any] = {
        "total_entities": len(entities),
        "total_concepts": len(concepts),
        "total_relationships": relationships,
        "orphans_count": len(orphans),
        "stale_count": len(stale),
        "gaps_count": len(gaps),
        "contradictions_count": len(contradictions),
    }
    if crosslink_breakdown:
        metrics["crosslink_edges"] = crosslink_breakdown

    return LintReport(
        orphans=orphans,
        stale=stale,
        gaps=gaps,
        contradictions=contradictions,
        suggestions=[],
        metrics=metrics,
    )
