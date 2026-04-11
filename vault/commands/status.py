"""Vault status utility — operational diagnostics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def vault_status(vault_root: Path) -> dict[str, Any]:
    """Return operational status of the vault."""
    from vault.ingest.cursor import is_locked, read_cursor, check_circuit_breaker

    cursors_dir = vault_root / ".cursors"

    # Lock state
    locked = is_locked(vault_root)
    lock_data = {}
    if locked:
        lock_file = cursors_dir / "vault.lock"
        try:
            lock_data = json.loads(lock_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Cursor state
    cursors = {}
    for source in ("tldv", "trello", "github"):
        cursor = read_cursor(vault_root, source)
        if cursor.get("last_run_at"):
            cursors[source] = cursor

    # Delivery failures
    failures_file = vault_root / ".delivery-failures.jsonl"
    delivery_failures = 0
    if failures_file.exists():
        content = failures_file.read_text().strip()
        delivery_failures = len(content.splitlines()) if content else 0

    # Circuit breakers
    circuit_breakers = {}
    for source in ("tldv", "trello", "github"):
        is_open = check_circuit_breaker(vault_root, source)
        if is_open:
            circuit_breakers[source] = {"open": True}

    return {
        "locked": locked,
        "lock_job": lock_data.get("job"),
        "lock_pid": lock_data.get("pid"),
        "lock_started_at": lock_data.get("started_at"),
        "cursors": cursors,
        "delivery_failures": delivery_failures,
        "circuit_breakers": circuit_breakers,
    }
