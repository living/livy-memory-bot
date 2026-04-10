"""
vault/metrics.py — quality metrics for HEARTBEAT/dashboard.

Task 6 extensions:
- Domain metrics collection (entity/decision/concept counts)
- Domain lint metrics integration
- Per-source distribution metrics
"""
from __future__ import annotations

import re
from pathlib import Path

from vault.lint import detect_coverage_gaps, detect_orphans, detect_stale_claims
from vault.quality.domain_lint import run_domain_lint


def _all_decisions(vault_root: Path) -> list[Path]:
    d = vault_root / "decisions"
    if not d.exists():
        return []
    return sorted(d.glob("*.md"))


def _confidence_from_text(text: str) -> str:
    m = re.search(r"^confidence:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    return m.group(1).lower() if m else "unknown"


def _has_official_source(text: str) -> bool:
    official_markers = ["type: tldv_api", "type: github_api", "type: supabase_rest", "type: exec", "type: openclaw_config"]
    low = text.lower()
    return any(marker in low for marker in official_markers)


def _count_md(path: Path) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob("*.md")))


def _source_distribution(vault_root: Path) -> dict[str, int]:
    """Count source type occurrences across decision files."""
    counts: dict[str, int] = {}
    for decision in _all_decisions(vault_root):
        text = decision.read_text(encoding="utf-8").lower()
        for source_type in [
            "signal_event",
            "github_api",
            "tldv_api",
            "trello_api",
            "supabase_rest",
            "exec",
            "openclaw_config",
            "api_direct",
            "curated_topic",
            "observation",
            "chat_history",
        ]:
            marker = f"type: {source_type}"
            if marker in text:
                counts[source_type] = counts.get(source_type, 0) + 1
    return counts


def collect_domain_metrics(vault_root: Path) -> dict:
    """Collect domain-specific metrics for pipeline Task 6.

    Includes:
    - entity/decision/concept counts
    - relationship validity checks
    - source distribution
    - domain lint error counts
    """
    domain_lint_result = run_domain_lint(vault_root)

    entities_count = _count_md(vault_root / "entities")
    decisions_count = _count_md(vault_root / "decisions")
    concepts_count = _count_md(vault_root / "concepts")

    return {
        "entities_count": entities_count,
        "decisions_count": decisions_count,
        "concepts_count": concepts_count,
        "files_total": entities_count + decisions_count + concepts_count,
        "source_distribution": _source_distribution(vault_root),
        "domain_errors": len(domain_lint_result.get("errors", [])),
        "relationships_valid": domain_lint_result.get("relationships_valid", True),
        "relationship_errors": len(domain_lint_result.get("relationship_errors", [])),
        "edges_checked": domain_lint_result.get("edges_checked", 0),
    }


def collect_quality_metrics(vault_root: Path) -> dict:
    decisions = _all_decisions(vault_root)

    high_total = 0
    high_with_official = 0

    for p in decisions:
        text = p.read_text(encoding="utf-8")
        conf = _confidence_from_text(text)
        if conf == "high":
            high_total += 1
            if _has_official_source(text):
                high_with_official += 1

    pct_high_with_official = (high_with_official / high_total * 100.0) if high_total else 100.0

    return {
        "gaps": len(detect_coverage_gaps(vault_root)),
        "orphans": len(detect_orphans(vault_root)),
        "stale_claims": len(detect_stale_claims(vault_root)),
        "high_claims_total": high_total,
        "high_claims_with_official": high_with_official,
        "pct_high_with_official": round(pct_high_with_official, 2),
    }
