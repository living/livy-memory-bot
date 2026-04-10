"""Observability primitives for Wave C runs.

Includes:
- build_run_id(): unique run identifier helper
- Counter: in-memory monotonic counter
- Histogram: in-memory distribution tracker
- RunAuditor: atomic run persistence (tmp then rename)

Run artifacts are stored under: memory/vault/wave-c-runs/
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
import secrets
from typing import Any


DEFAULT_RUNS_DIR = Path("memory") / "vault" / "wave-c-runs"


def build_run_id(prefix: str = "run") -> str:
    """Build unique run identifier.

    Format: {prefix}-{timestamp}-{rand}
    Example: run-20260410T224600123456Z-a1b2c3d4
    """
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    rand = secrets.token_hex(4)
    return f"{prefix}-{ts}-{rand}"


@dataclass
class Counter:
    """Simple in-memory counter."""

    label: str = "counter"
    value: int = 0

    def increment(self, amount: int = 1) -> int:
        self.value += int(amount)
        return self.value

    def get(self) -> int:
        return self.value

    def reset(self) -> None:
        self.value = 0


@dataclass
class Histogram:
    """In-memory histogram-like recorder.

    Tracks raw values for min/max and aggregate stats for count/sum/mean.
    """

    label: str = "histogram"
    values: list[float] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def sum(self) -> float:
        return float(sum(self.values))

    def record(self, value: float) -> None:
        self.values.append(float(value))

    def mean(self) -> float:
        if self.count == 0:
            return 0.0
        return self.sum / self.count

    def min(self) -> float:
        if self.count == 0:
            return 0.0
        return float(min(self.values))

    def max(self) -> float:
        if self.count == 0:
            return 0.0
        return float(max(self.values))

    def reset(self) -> None:
        self.values.clear()


@dataclass
class RunAuditor:
    """Persist observability snapshots for each run atomically.

    Atomicity contract: write JSON to a temporary file in the same directory,
    then rename to final destination.
    """

    runs_dir: Path = field(default_factory=lambda: DEFAULT_RUNS_DIR)

    def __post_init__(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _run_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def record_run(
        self,
        *,
        run_id: str,
        phase: str,
        counters: dict[str, Any],
        histograms: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> Path:
        """Record one run atomically to {runs_dir}/{run_id}.json."""
        now = datetime.now(UTC).isoformat()
        payload = {
            "run_id": run_id,
            "phase": phase,
            "recorded_at": now,
            "counters": counters,
            "histograms": histograms,
        }
        if extra:
            payload["extra"] = extra

        final_path = self._run_path(run_id)
        tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")

        tmp_path.replace(final_path)
        return final_path

    def audit_read(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Read stored run snapshots ordered by filename descending (newest first)."""
        files = sorted(self.runs_dir.glob("*.json"), reverse=True)
        if limit is not None:
            files = files[:limit]

        result: list[dict[str, Any]] = []
        for file in files:
            with file.open("r", encoding="utf-8") as f:
                result.append(json.load(f))
        return result
