#!/usr/bin/env python3
"""
logs_collector.py — Collects failure signals from BAT/Delphos job reports.
Priority: 2 (secondary — verification)

IMPORTANT: No per-run logs exist. Reports are aggregated JSON in:
  /home/lincoln/.openclaw/workspace/operacional/bat/reports/{intraday,daily}/
  /home/lincoln/.openclaw/workspace/operacional/delphos/reports/{intraday,daily}/

Failure proxy: total_errors > 0 in the latest report.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_bus import SignalEvent


JOB_TOPIC_MAP = {
    "bat-intraday": "bat-conectabot-observability.md",
    "bat-daily": "bat-conectabot-observability.md",
    "delphos-midday": "delphos-video-vistoria.md",
    "delphos-daily": "delphos-video-vistoria.md",
    "tldv-enrich": "tldv-pipeline-state.md",
}

BAT_REPORTS_DIR = Path("/home/lincoln/.openclaw/workspace/operacional/bat/reports")
DELPHOS_REPORTS_DIR = Path("/home/lincoln/.openclaw/workspace/operacional/delphos/reports")


class BATReportParser:
    """Parses BAT report JSON and emits failure signals."""

    @staticmethod
    def parse(job_name: str, report: dict, source_path: str) -> list[SignalEvent]:
        """Parse a BAT report JSON. Returns failure signal if errors > 0."""
        total_errors = report.get("total_errors", 0)
        signals = []

        if total_errors == 0:
            return signals

        ops = report.get("operations", [])
        ops_with_errors = [op["name"] for op in ops if op.get("errors", 0) > 0]
        ops_str = ", ".join(ops_with_errors) if ops_with_errors else f"total_errors={total_errors}"

        signal = SignalEvent(
            source="logs",
            priority=2,
            topic_ref=JOB_TOPIC_MAP.get(job_name),
            signal_type="failure",
            payload={
                "description": f"{job_name}: {ops_str} (total_errors={total_errors})",
                "evidence": source_path,
                "confidence": 1.0,
            },
            origin_id=f"{job_name}-{datetime.now(timezone.utc).date().isoformat()}",
            origin_url=None,
        )
        signals.append(signal)
        return signals


class LogsCollector:
    """Collects failure signals from BAT and Delphos report directories."""
    source = "logs"
    priority = 2

    def collect(self) -> list[SignalEvent]:
        """Scan latest BAT and Delphos reports. Return failure signals."""
        signals = []

        # BAT intraday
        signals.extend(self._scan_dir(BAT_REPORTS_DIR / "intraday", "bat-intraday"))
        signals.extend(self._scan_dir(BAT_REPORTS_DIR / "daily", "bat-daily"))

        # Delphos
        signals.extend(self._scan_dir(DELPHOS_REPORTS_DIR / "intraday", "delphos-midday"))
        signals.extend(self._scan_dir(DELPHOS_REPORTS_DIR / "daily", "delphos-daily"))

        return signals

    def _scan_dir(self, dir_path: Path, job_name: str) -> list[SignalEvent]:
        """Find latest report in directory, parse for failures."""
        signals = []
        if not dir_path.exists():
            return signals
        # Get most recent file
        files = sorted(dir_path.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return signals
        latest = files[0]
        try:
            report = json.loads(latest.read_text())
            signals = BATReportParser.parse(job_name, report, str(latest))
        except Exception:
            pass
        return signals