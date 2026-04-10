"""
vault/status.py — Operational metrics for the Memory Vault dashboard.
Phase 1B minimal functional implementation.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = ROOT / "memory" / "vault"


def _count_md(section: str, vault_root: Path) -> int:
    d = vault_root / section
    if not d.exists():
        return 0
    return sum(1 for p in d.glob("*.md"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def collect_metrics(vault_root: Path = VAULT_ROOT) -> dict:
    """Collect all numeric/dated metrics from the vault."""
    cache_dir = vault_root / ".cache" / "fact-check"
    cache_entries = sum(1 for p in cache_dir.glob("*.json")) if cache_dir.exists() else 0

    lint_reports_dir = vault_root / "lint-reports"
    lint_reports = sorted(lint_reports_dir.glob("*.md"), reverse=True) if lint_reports_dir.exists() else []
    last_lint: str | None = None
    if lint_reports:
        m = re.search(r"(\d{4}-\d{2}-\d{2})-lint\.md", lint_reports[0].name)
        if m:
            last_lint = m.group(1)

    log_text = _read(vault_root / "log.md")
    ingest_runs = len(re.findall(r"## \[[^\]]+\]\s*ingest\s*\|", log_text, flags=re.IGNORECASE))
    lint_runs = len(re.findall(r"## \[[^\]]+\]\s*lint\s*\|", log_text, flags=re.IGNORECASE))

    last_activity_dates = re.findall(r"## \[(\d{4}-\d{2}-\d{2})\]", log_text)
    last_activity = max(last_activity_dates) if last_activity_dates else ""

    return {
        "entities_count": _count_md("entities", vault_root),
        "decisions_count": _count_md("decisions", vault_root),
        "concepts_count": _count_md("concepts", vault_root),
        "evidence_count": _count_md("evidence", vault_root),
        "lint_reports_count": _count_md("lint-reports", vault_root),
        "fact_check_cache_entries": cache_entries,
        "last_lint_report": last_lint or "",
        "ingest_runs": ingest_runs,
        "lint_runs": lint_runs,
        "last_activity": last_activity,
    }


def build_status_payload(vault_root: Path = VAULT_ROOT) -> dict:
    """Build the full dashboard payload with health status."""
    metrics = collect_metrics(vault_root)

    # Health: degraded if essential directories missing
    essential = ["entities", "decisions", "concepts", "evidence"]
    missing = [d for d in essential if not (vault_root / d).exists()]
    vault_health = "degraded" if missing else "ok"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vault_health": vault_health,
        "metrics": metrics,
    }


def render_markdown(payload: dict) -> str:
    """Render the status payload as a readable markdown table."""
    m = payload["metrics"]
    rows = [
        "| Metric | Value |",
        "|---|---|",
        "| entities_count | " + str(m["entities_count"]) + " |",
        "| decisions_count | " + str(m["decisions_count"]) + " |",
        "| concepts_count | " + str(m["concepts_count"]) + " |",
        "| evidence_count | " + str(m["evidence_count"]) + " |",
        "| lint_reports_count | " + str(m["lint_reports_count"]) + " |",
        "| fact_check_cache_entries | " + str(m["fact_check_cache_entries"]) + " |",
        "| last_lint_report | " + str(m["last_lint_report"]) + " |",
        "| ingest_runs | " + str(m["ingest_runs"]) + " |",
        "| lint_runs | " + str(m["lint_runs"]) + " |",
        "| last_activity | " + str(m["last_activity"]) + " |",
    ]
    return (
        "# Memory Vault Status\n\n"
        f"Generated: {payload['generated_at'][:10]}\n"
        f"Health: **{payload['vault_health']}**\n\n"
        + "\n".join(rows)
        + "\n"
    )


if __name__ == "__main__":
    import json
    payload = build_status_payload(VAULT_ROOT)
    print(render_markdown(payload))
