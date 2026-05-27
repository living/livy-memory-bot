"""
VaultCache — Thread-safe in-memory cache with TTL for vault index.md.

Cache strategy:
- index.md: cached for 5 minutes (300s), invalidated by mtime change
- relationships/: NOT cached (too dynamic)
- decisions/*.md: always read directly
"""

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CacheEntry:
    """Single cache entry with TTL tracking."""
    data: str
    mtime: float
    cached_at: float = field(default_factory=time.time)

    def is_valid(self, current_mtime: float, ttl: float) -> bool:
        """Check if entry is still valid based on TTL and mtime."""
        age = time.time() - self.cached_at
        return age < ttl and current_mtime == self.mtime


class VaultCache:
    """
    Thread-safe in-memory cache for vault index.md.
    
    Features:
    - 5-minute TTL (300s) for index.md
    - mtime-based invalidation
    - Automatic invalidation on vault writes
    - Force refresh capability
    """

    DEFAULT_TTL = 300  # 5 minutes

    def __init__(self, vault_path: Optional[str] = None):
        """
        Initialize cache.
        
        Args:
            vault_path: Path to vault root (defaults to memory/vault in workspace)
        """
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._vault_path = vault_path
        self._last_cursor_mtime: dict[str, float] = {}

    def _get_index_path(self) -> Path:
        """Get path to index.md."""
        if self._vault_path:
            base = Path(self._vault_path)
        else:
            base = Path(__file__).parent.parent.parent / "memory" / "vault"
        return base / "index.md"

    def _get_cache_key(self, file_path: Path) -> str:
        """Generate cache key from file path."""
        return str(file_path.resolve())

    def get_index(self, force_refresh: bool = False) -> Optional[str]:
        """
        Get index.md content with caching.
        
        Args:
            force_refresh: If True, bypass cache and re-read file
            
        Returns:
            index.md content or None if file doesn't exist
        """
        index_path = self._get_index_path()
        cache_key = self._get_cache_key(index_path)

        with self._lock:
            if not force_refresh and cache_key in self._cache:
                entry = self._cache[cache_key]
                
                # Check mtime
                try:
                    current_mtime = index_path.stat().st_mtime
                except OSError:
                    return entry.data  # Return stale if file gone
                
                if entry.is_valid(current_mtime, self.DEFAULT_TTL):
                    return entry.data

            # Cache miss or invalid — read from disk
            try:
                data = index_path.read_text(encoding="utf-8")
                mtime = index_path.stat().st_mtime
                self._cache[cache_key] = CacheEntry(data=data, mtime=mtime)
                return data
            except OSError:
                return None

    def invalidate(self, path: Optional[str] = None) -> None:
        """
        Invalidate cache entries.
        
        Args:
            path: Specific file to invalidate. If None, invalidates all entries.
        """
        with self._lock:
            if path:
                cache_key = self._get_cache_key(Path(path))
                self._cache.pop(cache_key, None)
            else:
                self._cache.clear()
            self._last_cursor_mtime.clear()

    def invalidate_on_write(self) -> None:
        """
        Invalidate cache when a write to vault occurs.
        Called after any write operation to the vault.
        """
        self.invalidate()

    def check_cursor_changes(self) -> bool:
        """
        Check if .cursors/ directory has changed.
        
        Returns:
            True if cursors changed (cache should be invalidated)
        """
        cursors_path = self._get_index_path().parent / ".cursors"
        if not cursors_path.exists():
            return False

        current_mtimes = {}
        for cursor_file in cursors_path.glob("*"):
            try:
                current_mtimes[str(cursor_file)] = cursor_file.stat().st_mtime
            except OSError:
                continue

        if current_mtimes != self._last_cursor_mtime:
            self._last_cursor_mtime = current_mtimes
            return True
        
        return False

    def get_stats(self) -> dict:
        """Get cache statistics for debugging."""
        with self._lock:
            return {
                "entries": len(self._cache),
                "cached_keys": list(self._cache.keys()),
                "ttl_seconds": self.DEFAULT_TTL,
            }
