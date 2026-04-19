"""
Shadow run: executa nova implementação vs atual com mesmos inputs
e gera diff report (spec Section 9.3).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def run_shadow(
    pipeline_v1_output: list[dict],
    pipeline_v2_output: list[dict],
    threshold: float = 0.05,
) -> dict[str, Any]:
    """
    Compara outputs do pipeline v1 (atual) vs v2 (novo).

    Args:
        pipeline_v1_output: lista de claims do pipeline atual
        pipeline_v2_output: lista de claims do novo pipeline
        threshold: % máxima de divergência aceita (default 5%)

    Returns:
        dict com {passed, diff_ratio, diff_items, report_path}
    """
    v1_by_entity = {c["entity_id"]: c for c in pipeline_v1_output}
    v2_by_entity = {c["entity_id"]: c for c in pipeline_v2_output}

    all_entities = set(v1_by_entity) | set(v2_by_entity)
    diverged = []

    for entity_id in all_entities:
        c1 = v1_by_entity.get(entity_id)
        c2 = v2_by_entity.get(entity_id)

        if c1 is None or c2 is None:
            diverged.append({
                "entity_id": entity_id,
                "reason": "missing_in_one_version",
                "v1_text": c1.get("text", "")[:100] if c1 else "",
                "v2_text": c2.get("text", "")[:100] if c2 else "",
            })
        elif c1.get("text") != c2.get("text"):
            diverged.append({
                "entity_id": entity_id,
                "reason": "text_mismatch",
                "v1_text": c1.get("text", "")[:100],
                "v2_text": c2.get("text", "")[:100],
            })

    diff_ratio = len(diverged) / max(len(all_entities), 1)
    passed = diff_ratio <= threshold

    report = {
        "passed": passed,
        "diff_ratio": round(diff_ratio, 4),
        "threshold": threshold,
        "total_entities": len(all_entities),
        "diverged_count": len(diverged),
        "diverged_items": diverged[:50],
    }

    report_path = Path("state/shadow-run-reports") / f"report-{int(time.time())}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    report["report_path"] = str(report_path)
    return report
