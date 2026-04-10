"""Entity-quality metrics for Wave B observability."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def compute_entity_quality_metrics(vault_root: Path) -> dict[str, Any]:
    """Compute Wave B quality metrics from vault markdown files.

    Returns metrics keys required by spec:
      - persons_total
      - projects_total
      - repos_total
      - stale_rate
      - orphan_rate
      - merge_candidate_count
      - high_confidence_without_multi_source
    """
    entities_dir = vault_root / "entities"
    decision_dir = vault_root / "decisions"

    persons_total = 0
    projects_total = 0
    repos_total = 0
    stale_count = 0
    orphan_count = 0
    total_checked = 0
    high_confidence_without_multi_source = 0

    if entities_dir.exists():
        for md in entities_dir.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            total_checked += 1
            if "type: person" in text:
                persons_total += 1
            if "type: project" in text:
                projects_total += 1
            if "type: repo" in text:
                repos_total += 1

            if "stale: true" in text:
                stale_count += 1
            if "orphan: true" in text:
                orphan_count += 1

            if "confidence: high" in text:
                # conservative heuristic for markdown frontmatter style
                src_keys_count = text.count("- github:") + text.count("- tldv:") + text.count("- mapper:")
                if src_keys_count < 2:
                    high_confidence_without_multi_source += 1

    merge_candidate_count = 0
    merge_candidates = vault_root / ".merge-candidates.jsonl"
    if merge_candidates.exists():
        merge_candidate_count = len([ln for ln in merge_candidates.read_text(encoding="utf-8").splitlines() if ln.strip()])

    denominator = total_checked if total_checked > 0 else 1
    stale_rate = round(stale_count / denominator, 4)
    orphan_rate = round(orphan_count / denominator, 4)

    return {
        "persons_total": persons_total,
        "projects_total": projects_total,
        "repos_total": repos_total,
        "stale_rate": stale_rate,
        "orphan_rate": orphan_rate,
        "merge_candidate_count": merge_candidate_count,
        "high_confidence_without_multi_source": high_confidence_without_multi_source,
    }
