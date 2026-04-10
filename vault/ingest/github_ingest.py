"""
vault/ingest/github_ingest.py — GitHub ingestion with scope allowlist enforcement.
Phase 2: GitHub monitoring boundaries (org/repo allowlists) + lookback windows.

Implements:
  - is_repo_in_scope()
  - build_pr_query()
  - is_within_window()
  - is_outside_active_window()
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Constants — operational lookback windows (spec §7.1)
# ---------------------------------------------------------------------------

WINDOW_30_DAYS = 30
WINDOW_90_DAYS = 90
WINDOW_180_DAYS = 180
WINDOW_355_DAYS = 355  # intentionally near-yearly, not 365

VALID_DATE_MODES = frozenset(["created_at", "merged_at"])
DATE_MODE_TO_GITHUB_QUALIFIER = {
    "created_at": "created",
    "merged_at": "merged",
}


# ---------------------------------------------------------------------------
# Scope filtering
# ---------------------------------------------------------------------------

def is_repo_in_scope(
    repo_full_name: str,
    org_allowlist: Optional[list[str]] = None,
    repo_allowlist: Optional[list[str]] = None,
    repo_denylist: Optional[list[str]] = None,
) -> bool:
    """
    Enforce GitHub scope boundaries per spec §5.

    Rules (in priority order):
    1. repo_allowlist > org_allowlist  (if repo_allowlist is set, use it exclusively)
    2. org_allowlist scopes the orgs  (all repos under allowed orgs are in scope)
    3. repo_denylist always applies last  (even if explicitly allowlisted)
    4. No allowlist → reject everything

    Case-insensitive matching throughout.

    Args:
        repo_full_name: "owner/repo" string
        org_allowlist: list of org logins (e.g. ["living"])
        repo_allowlist: explicit repo list, overrides org_allowlist when set
        repo_denylist: always-blocked repos

    Returns:
        True if repo is within scope, False otherwise.
    """
    if not repo_full_name:
        return False

    repo_full_name_lower = repo_full_name.lower()

    # --- Denylist check (always applies) ---
    if repo_denylist:
        for entry in repo_denylist:
            if entry and entry.lower() == repo_full_name_lower:
                return False

    # --- repo_allowlist (higher priority than org_allowlist) ---
    if repo_allowlist is not None and len(repo_allowlist) > 0:
        for entry in repo_allowlist:
            if entry and entry.lower() == repo_full_name_lower:
                return True
        return False

    # --- org_allowlist fallback ---
    if org_allowlist is not None and len(org_allowlist) > 0:
        if "/" not in repo_full_name:
            return False
        org, _ = repo_full_name.split("/", 1)
        return org.lower() in {o.lower() for o in org_allowlist if o}

    # No allowlist configured → reject
    return False


# ---------------------------------------------------------------------------
# GitHub Search Query Builder
# ---------------------------------------------------------------------------

def build_pr_query(
    window_days: int,
    date_mode: str = "merged_at",
    repo: Optional[str] = None,
) -> str:
    """
    Build a GitHub search query string for PRs within a lookback window.

    Args:
        window_days: number of days to look back (must be > 0)
        date_mode: "merged_at" or "created_at" — which date field to filter on
        repo: optional "owner/repo" to restrict to a single repo

    Returns:
        GitHub search query string (e.g. "is:pr merged:>2026-03-11 repo:living/tldv")

    Raises:
        ValueError: if window_days <= 0 or date_mode not in VALID_DATE_MODES
    """
    if window_days <= 0:
        raise ValueError("window_days must be a positive integer")
    if date_mode not in VALID_DATE_MODES:
        raise ValueError(
            f"date_mode must be one of {sorted(VALID_DATE_MODES)}, got {date_mode!r}"
        )

    cutoff = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=window_days)
    date_str = cutoff.strftime("%Y-%m-%d")

    qualifier = DATE_MODE_TO_GITHUB_QUALIFIER[date_mode]
    parts = ["is:pr", f"{qualifier}:>{date_str}"]
    if repo:
        parts.append(f"repo:{repo}")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Window filter (vault hygiene)
# ---------------------------------------------------------------------------

def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string into a UTC datetime. Returns None on failure.

    Microseconds are normalised to 0 to avoid boundary comparison failures
    when a timestamp created at T is parsed back after T has advanced by µs.
    """
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # Normalize naive datetimes to UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Strip microseconds for stable boundary comparisons
        dt = dt.replace(microsecond=0)
        return dt
    except (ValueError, TypeError):
        return None


def is_within_window(
    timestamp: Optional[str],
    window_days: int,
) -> bool:
    """
    Check whether a timestamp falls within the lookback window.

    Boundary is inclusive: a timestamp exactly at the cutoff is considered "within".

    Args:
        timestamp: ISO-8601 datetime string (e.g. "2026-04-01T12:00:00+00:00")
        window_days: number of days to look back

    Returns:
        True if within window, False otherwise (including None/invalid timestamps)
    """
    if window_days <= 0:
        return False
    dt = _parse_ts(timestamp)
    if dt is None:
        return False
    cutoff = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=window_days)
    return dt >= cutoff


def is_outside_active_window(
    timestamp: Optional[str],
    window_days: int,
) -> bool:
    """
    Marker for vault hygiene: is this record outside the active lookback window?

    Inverse of is_within_window (spec §7.4).
    Records outside the window should NOT be hard-deleted — they are eligible
    for archive/consolidation policy (separate job).

    Args:
        timestamp: ISO-8601 datetime string
        window_days: active window in days

    Returns:
        True if outside window (and therefore eligible for archive, not deletion)
    """
    if not timestamp:
        return False
    return not is_within_window(timestamp, window_days)
