"""
vault/lint.py — Daily lint checks for Memory Vault.
Detects contradictions, orphan pages, stale claims, coverage gaps,
and Wave C entity model requirements (meeting/card id_source, orphan edges, role validation).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from vault.slug_registry import resolve as _resolve_slug

except ImportError:
    _resolve_slug = lambda s: s  # type: ignore

try:
    from vault.domain.canonical_types import RELATIONSHIP_ROLES
except ImportError:
    RELATIONSHIP_ROLES = frozenset([
        "author", "reviewer", "commenter",
        "participant", "assignee", "decision_maker",
    ])

ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = ROOT / "memory" / "vault"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _all_pages(vault_root: Path) -> list[Path]:
    pages: list[Path] = []
    for section in ("entities", "decisions", "concepts", "evidence"):
        d = vault_root / section
        if d.exists():
            pages.extend(sorted(d.glob("*.md")))
    return pages


def _extract_feature(text: str) -> str | None:
    """Extract a feature/subject token used to group contradiction candidates."""
    low = text.lower()

    # Prefer explicit feature naming: "feature x", "feature-flag", etc.
    m = re.search(r"\bfeature\s+([a-z0-9_-]+)\b", low)
    if m:
        return m.group(1)

    # Fallback: first wikilink target can act as subject anchor.
    links = _extract_wikilinks(text)
    if links:
        return links[0].lower()

    return None


def detect_contradictions(vault_root: Path = VAULT_ROOT) -> list[dict]:
    """
    Contradiction detector grouped by subject/feature.
    Only flags enabled vs disabled when both decisions share the same feature subject.
    """
    decisions_dir = vault_root / "decisions"
    if not decisions_dir.exists():
        return []

    decisions = sorted(decisions_dir.glob("*.md"))
    entries: list[tuple[Path, str]] = [(p, p.read_text(encoding="utf-8")) for p in decisions]

    # Group by feature subject
    groups: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for path, text in entries:
        feature = _extract_feature(text)
        if feature is not None:
            groups[feature].append((path, text))

    contradictions: list[dict] = []
    for feature, group_entries in groups.items():
        enabled_texts = []
        disabled_texts = []
        for _, text in group_entries:
            tl = text.lower()
            if "enabled" in tl:
                enabled_texts.append(text)
            if "disabled" in tl:
                disabled_texts.append(text)
        if enabled_texts and disabled_texts:
            for a, b in [(e, d) for e in enabled_texts for d in disabled_texts]:
                # Use full text or just the meaningful body, not frontmatter-only truncation
                contradictions.append({"a": a, "b": b, "kind": "enabled_vs_disabled", "feature": feature})
    return contradictions


def _extract_wikilinks(text: str) -> list[str]:
    links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)
    cleaned = []
    for link in links:
        # Normalize: extract just the filename component (handles ../entities/foo)
        from pathlib import PurePosixPath
        name = PurePosixPath(link.strip()).stem or PurePosixPath(link.strip()).name
        if name and "/" not in name:
            cleaned.append(name)
        elif name:
            # strip path prefix to get just the filename
            clean = name.split("/")[-1]
            if clean:
                cleaned.append(clean)
    return cleaned


def detect_orphans(vault_root: Path = VAULT_ROOT) -> list[dict]:
    """
    Orphan detector: entity page with zero INBOUND links from other pages.
    """
    entities_dir = vault_root / "entities"
    if not entities_dir.exists():
        return []

    entity_names = {p.stem for p in sorted(entities_dir.glob("*.md"))}
    inbound = {name: 0 for name in entity_names}

    for page in _all_pages(vault_root):
        src = page.stem
        src_section = page.parent.name
        for link_name in _extract_wikilinks(_read(page)):
            if link_name not in inbound:
                continue
            # Ignore only true self-links from the same entity page.
            if src_section == "entities" and link_name == src:
                continue
            inbound[link_name] += 1

    orphans: list[dict] = []
    for name in sorted(entity_names):
        if inbound[name] == 0:
            orphans.append({"page": name, "inbound_links": 0})
    return orphans


def _extract_last_verified(text: str) -> str | None:
    m = re.search(r"^last_verified:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*$", text, flags=re.MULTILINE)
    return m.group(1) if m else None


def is_stale(last_verified: str, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(f"{last_verified.strip()}" + "T00:00:00+00:00")
    except Exception:
        return True
    # compare by date, 7+ days considered stale
    age_days = (now.date() - dt.date()).days
    return age_days > 7


def detect_stale_claims(vault_root: Path = VAULT_ROOT, now: datetime | None = None) -> list[dict]:
    stale: list[dict] = []
    for page in _all_pages(vault_root):
        text = _read(page)
        lv = _extract_last_verified(text)
        if not lv:
            continue
        if is_stale(lv, now=now):
            stale.append({"page": page.stem, "last_verified": lv})
    return stale


def detect_coverage_gaps(vault_root: Path = VAULT_ROOT) -> list[dict]:
    """
    Coverage gap = concept link [[concept-name]] referenced in pages but missing
    corresponding concepts/concept-name.md
    """
    concepts_dir = vault_root / "concepts"
    existing = {p.stem for p in concepts_dir.glob("*.md")} if concepts_dir.exists() else set()

    refs: set[str] = set()
    for page in _all_pages(vault_root):
        text = _read(page)
        for link in _extract_wikilinks(text):
            # Heuristic: links that look like concept names and are not direct entities/decisions files
            if link not in existing and "/" not in link:
                refs.add(link)

    gaps = [{"concept": c} for c in sorted(refs) if c not in existing]

    # Apply slug registry to resolve known aliases before reporting
    resolved_gaps: list[dict] = []
    for gap in gaps:
        concept = gap.get("concept", "")
        canonical = _resolve_slug(concept)
        # If canonical resolves to an existing page, drop the gap
        if canonical in existing:
            continue
        resolved_gaps.append({"concept": concept, "canonical": canonical})

    return resolved_gaps


def _report_markdown(now: datetime, contradictions: list[dict], orphans: list[dict], stale: list[dict], gaps: list[dict]) -> str:
    d = now.date().isoformat()
    lines = [
        f"# Lint Report — {d}",
        "",
        f"## Contradictions ({len(contradictions)})",
    ]
    if contradictions:
        for c in contradictions:
            lines.append(f"- {c.get('kind', 'contradiction')}")
    else:
        lines.append("- none")

    lines.extend([
        "",
        f"## Orphans ({len(orphans)})",
    ])
    if orphans:
        for o in orphans:
            lines.append(f"- {o['page']}")
    else:
        lines.append("- none")

    lines.extend([
        "",
        f"## Stale Claims ({len(stale)})",
    ])
    if stale:
        for s in stale:
            lines.append(f"- {s['page']} (last_verified: {s['last_verified']})")
    else:
        lines.append("- none")

    lines.extend([
        "",
        f"## Coverage Gaps ({len(gaps)})",
    ])
    if gaps:
        for g in gaps:
            lines.append(f"- {g['concept']}")
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def _append_log(vault_root: Path, now: datetime, contradictions: list[dict], orphans: list[dict], stale: list[dict], gaps: list[dict]) -> None:
    log = vault_root / "log.md"
    d = now.date().isoformat()
    lines = [
        f"## [{d}] lint | daily cycle",
        f"  contradictions: {len(contradictions)}",
        f"  orphans: {len(orphans)}",
        f"  stale_claims: {len(stale)}",
        f"  coverage_gaps: {len(gaps)}",
        "",
    ]
    mode = "a" if log.exists() else "w"
    with log.open(mode, encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_lint(vault_root: Path = VAULT_ROOT, now: datetime | None = None) -> Path:
    if now is None:
        now = datetime.now(timezone.utc)

    reports = vault_root / "lint-reports"
    reports.mkdir(parents=True, exist_ok=True)

    contradictions = detect_contradictions(vault_root)
    orphans = detect_orphans(vault_root)
    stale = detect_stale_claims(vault_root, now=now)
    gaps = detect_coverage_gaps(vault_root)

    report = _report_markdown(now, contradictions, orphans, stale, gaps)
    path = reports / f"{now.date().isoformat()}-lint.md"
    path.write_text(report, encoding="utf-8")

    _append_log(vault_root, now, contradictions, orphans, stale, gaps)
    return path


# ---------------------------------------------------------------------------
# Wave C: meeting/card id_source requirements + orphan edges + role validation
# ---------------------------------------------------------------------------

def _collect_id_canonical_set(vault_root: Path) -> set[str]:
    """Collect all id_canonical values from entities/ and decisions/."""
    ids: set[str] = set()
    for subdir in ("entities", "decisions"):
        d = vault_root / subdir
        if not d.exists():
            continue
        for md_file in d.glob("*.md"):
            text = _read(md_file)
            m = re.search(r"^id_canonical:\s*(.+)\s*$", text, flags=re.MULTILINE)
            if m:
                ids.add(m.group(1).strip())
    return ids


def _parse_frontmatter_value(text: str, key: str) -> str | None:
    """Extract a top-level frontmatter key value from markdown text."""
    pattern = rf"^{re.escape(key)}:\s*(.+)\s*$"
    m = re.search(pattern, text, flags=re.MULTILINE)
    return m.group(1).strip() if m else None


def detect_meeting_id_source_requirements(vault_root: Path = VAULT_ROOT) -> list[dict]:
    """
    Flag meeting-type entities missing the required meeting_id_source field.

    Each violation is a dict with:
      page   — stem of the markdown file
      reason — "missing_meeting_id_source"
    """
    entities_dir = vault_root / "entities"
    if not entities_dir.exists():
        return []

    violations: list[dict] = []
    for md_file in sorted(entities_dir.glob("*.md")):
        text = _read(md_file)
        entity_type = _parse_frontmatter_value(text, "type")
        if entity_type != "meeting":
            continue
        meeting_id_source = _parse_frontmatter_value(text, "meeting_id_source")
        if not meeting_id_source:
            violations.append({
                "page": md_file.stem,
                "reason": "missing_meeting_id_source",
            })
    return violations


def detect_card_id_source_requirements(vault_root: Path = VAULT_ROOT) -> list[dict]:
    """
    Flag card-type entities missing the required card_id_source field.

    Each violation is a dict with:
      page   — stem of the markdown file
      reason — "missing_card_id_source"
    """
    entities_dir = vault_root / "entities"
    if not entities_dir.exists():
        return []

    violations: list[dict] = []
    for md_file in sorted(entities_dir.glob("*.md")):
        text = _read(md_file)
        entity_type = _parse_frontmatter_value(text, "type")
        if entity_type != "card":
            continue
        card_id_source = _parse_frontmatter_value(text, "card_id_source")
        if not card_id_source:
            violations.append({
                "page": md_file.stem,
                "reason": "missing_card_id_source",
            })
    return violations


def detect_orphan_edges(vault_root: Path = VAULT_ROOT) -> list[dict]:
    """
    Flag relationship edges whose from_id or to_id does not correspond to any
    id_canonical found in the vault's entities/ or decisions/ directories.

    An "orphan edge" is one that references at least one entity ID that does
    not exist in the vault — indicating a dangling cross-reference.

    Each violation is a dict with:
      edge        — index of the offending edge (0-based)
      file        — relationship JSON filename
      orphan_id   — the referenced id that has no matching entity
      direction   — "from_id" or "to_id"
    """
    rel_dir = vault_root / "relationships"
    if not rel_dir.exists():
        return []

    known_ids = _collect_id_canonical_set(vault_root)
    violations: list[dict] = []

    for rel_file in sorted(rel_dir.glob("*.json")):
        try:
            data = json.loads(_read(rel_file))
        except Exception:
            continue
        edges = data if isinstance(data, list) else data.get("edges", [])
        for idx, edge in enumerate(edges):
            for direction in ("from_id", "to_id"):
                ref_id = edge.get(direction)
                if ref_id and ref_id not in known_ids:
                    violations.append({
                        "edge": idx,
                        "file": rel_file.name,
                        "orphan_id": ref_id,
                        "direction": direction,
                    })
    return violations


def detect_invalid_relationship_roles(vault_root: Path = VAULT_ROOT) -> list[dict]:
    """
    Flag relationship edges whose role field is not in the allowed RELATIONSHIP_ROLES
    set (author, reviewer, commenter, participant, assignee, decision_maker).

    Each violation is a dict with:
      edge  — index of the offending edge (0-based)
      file  — relationship JSON filename
      role  — the invalid role value
    """
    rel_dir = vault_root / "relationships"
    if not rel_dir.exists():
        return []

    violations: list[dict] = []
    for rel_file in sorted(rel_dir.glob("*.json")):
        try:
            data = json.loads(_read(rel_file))
        except Exception:
            continue
        edges = data if isinstance(data, list) else data.get("edges", [])
        for idx, edge in enumerate(edges):
            role = edge.get("role", "")
            if role and role not in RELATIONSHIP_ROLES:
                violations.append({
                    "edge": idx,
                    "file": rel_file.name,
                    "role": role,
                })
    return violations


if __name__ == "__main__":
    p = run_lint(VAULT_ROOT)
    print(str(p))
