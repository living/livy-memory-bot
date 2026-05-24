"""Módulo de lock partilhado para QW-2 com TTL de 600s."""

from pathlib import Path
import time
import os

LOCK_FILE = Path(".research/qw2/.qw2.lock")
LOCK_TTL_SECONDS = 600


def _ensure_dir():
    """Cria diretório do lock file se não existir."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)


def _read_lock():
    """Lê lock file. Retorna (pid, timestamp) ou (None, None) se corrupto/inexistente."""
    if not LOCK_FILE.exists():
        return None, None
    try:
        content = LOCK_FILE.read_text().strip()
        pid_str, ts_str = content.split("|")
        return int(pid_str), float(ts_str)
    except (ValueError, OSError):
        # Corrupto — não é lock real
        return None, None


def acquire_lock() -> bool:
    """Cria lock file. Retorna True se adquirido, False se lock existe e é fresco."""
    _ensure_dir()
    pid, ts = _read_lock()
    if pid is not None:
        age = time.time() - ts
        if age < LOCK_TTL_SECONDS:
            # Lock fresco — não sobrescrever
            return False
    # Sem lock ou lock stale — adquirir
    LOCK_FILE.write_text(f"{os.getpid()}|{time.time()}")
    return True


def release_lock() -> bool:
    """Remove lock file. Retorna True se removido, False se não era o lock atual."""
    if not LOCK_FILE.exists():
        return False
    pid, _ = _read_lock()
    if pid is not None and pid != os.getpid():
        # Lock de outro processo
        return False
    try:
        LOCK_FILE.unlink()
        return True
    except OSError:
        return False


def is_locked() -> bool:
    """Check se lock existe e não é stale."""
    pid, ts = _read_lock()
    if pid is None:
        return False
    age = time.time() - ts
    return age < LOCK_TTL_SECONDS
