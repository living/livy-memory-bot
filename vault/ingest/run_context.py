"""Run context — carries run_id, started_at, vault_root, dry_run through the pipeline."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RunContext:
    run_id: str
    started_at: str
    vault_root: Path
    dry_run: bool

    def elapsed_seconds(self) -> float:
        start = datetime.fromisoformat(self.started_at)
        return (datetime.now(timezone.utc) - start).total_seconds()


def new_run_context(vault_root: Path | str, dry_run: bool = False) -> RunContext:
    return RunContext(
        run_id=str(uuid.uuid4()),
        started_at=datetime.now(timezone.utc).isoformat(),
        vault_root=Path(vault_root),
        dry_run=dry_run,
    )
