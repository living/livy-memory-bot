"""Log.md management with monthly rotation + delivery failure tracking."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def append_log(
    vault_root: Path,
    job: str,
    summary: dict[str, Any],
    *,
    run_id: str,
    dry_run: bool = False,
) -> None:
    log_file = vault_root / "log.md"
    vault_root.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prefix = "[dry-run] " if dry_run else ""
    header = f"## [{date_str}] {prefix}{job}  <!-- run_id={run_id} -->"
    lines = [header]
    for k, v in summary.items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    entry = "\n".join(lines) + "\n"
    if log_file.exists():
        with open(log_file, "a") as f:
            f.write(entry)
    else:
        log_file.write_text("# Vault Log\n\n" + entry)


def maybe_rotate_log(vault_root: Path, max_bytes: int = 500_000) -> None:
    log_file = vault_root / "log.md"
    if not log_file.exists() or log_file.stat().st_size < max_bytes:
        return
    month_str = datetime.now(timezone.utc).strftime("%Y-%m")
    archive_dir = vault_root / "log-archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_file = archive_dir / f"{month_str}.md"
    content = log_file.read_text()
    if archive_file.exists():
        with open(archive_file, "a") as f:
            f.write("\n" + content)
    else:
        archive_file.write_text(content)
    log_file.write_text("# Vault Log\n\n")


def log_delivery_failure(
    vault_root: Path,
    job: str,
    summary: dict[str, Any],
    *,
    run_id: str,
) -> None:
    vault_root.mkdir(parents=True, exist_ok=True)
    f = vault_root / ".delivery-failures.jsonl"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job": job,
        "summary": summary,
        "run_id": run_id,
    }
    with open(f, "a") as fh:
        fh.write(json.dumps(payload) + "\n")
