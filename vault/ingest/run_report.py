"""Structured run metrics — persisted after each pipeline run."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def emit_run_report(
    summary: dict[str, Any],
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate a structured run report.

    1. Generate run_id (uuid4) and run_at (ISO8601 UTC)
    2. Merge into summary
    3. Write JSON to reports_dir/{date}-{run_id[:8]}.json
    4. Return enriched report dict

    Default reports_dir = memory/vault/run-reports/ relative to project root.
    """
    if reports_dir is None:
        project_root = Path(__file__).resolve().parents[2]
        reports_dir = project_root / "memory" / "vault" / "run-reports"

    run_id = str(uuid.uuid4())
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    report = {**summary, "run_id": run_id, "run_at": run_at}

    reports_dir.mkdir(parents=True, exist_ok=True)
    date_part = run_at[:10]
    filename = f"{date_part}-{run_id[:8]}.json"
    report_path = reports_dir / filename

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return report
