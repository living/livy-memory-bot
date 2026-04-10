"""
vault/lint.py — Daily lint checks for Memory Vault.
Detects contradictions, orphan pages, stale claims, and coverage gaps.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

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
        name = Path(link.strip()).stem
        if name:
            cleaned.append(name)
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
        for link_name in _extract_wikilinks(_read(page)):
            if link_name in inbound and link_name != src:
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
    return gaps


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


if __name__ == "__main__":
    p = run_lint(VAULT_ROOT)
    print(str(p))
