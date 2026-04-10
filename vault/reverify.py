"""
vault/reverify.py — Automatic re-verification of stale Memory Vault claims.
For each stale page, either refresh verified date (if official source) or
downgrade confidence (if no official source).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from vault.lint import detect_stale_claims, VAULT_ROOT

# Official source markers (checked case-insensitively)
OFFICIAL_SOURCE_MARKERS = frozenset([
    "tldv_api",
    "github_api",
    "supabase_rest",
    "exec",
    "openclaw_config",
    "api_direct",
])


def _all_sections() -> list[str]:
    return ["entities", "decisions", "concepts", "evidence"]


def _find_page(vault_root: Path, page_stem: str) -> Path | None:
    """Locate a page by stem across all sections."""
    for section in _all_sections():
        p = vault_root / section / f"{page_stem}.md"
        if p.exists():
            return p
    return None


def _split_frontmatter(text: str) -> tuple[str, str, str]:
    """Return (opening, frontmatter-content, rest). Empty opening means no frontmatter."""
    match = re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", text, re.DOTALL)
    if not match:
        return "", "", text
    opening = match.group(1)
    fm = match.group(2)
    rest = match.group(4)
    return opening, fm, rest


def _extract_frontmatter(text: str) -> dict[str, str]:
    """Parse simple key/value frontmatter into a lowercased dict."""
    _, fm_text, _ = _split_frontmatter(text)
    if not fm_text:
        return {}
    fm: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip().lower()] = val.strip()
    return fm


def _has_official_source(text: str) -> bool:
    """Check frontmatter for at least one official source marker."""
    _, fm_text, _ = _split_frontmatter(text)
    low = fm_text.lower() if fm_text else ""
    return any(marker in low for marker in OFFICIAL_SOURCE_MARKERS)


def _update_frontmatter_field(text: str, key: str, value: str) -> str:
    """Update or insert a frontmatter field."""
    opening, fm_text, rest = _split_frontmatter(text)
    if not opening:
        return text

    lines = fm_text.splitlines()
    pat = re.compile(rf"^{re.escape(key)}:\s*.*$")
    replaced = False
    out: list[str] = []
    for line in lines:
        if pat.match(line):
            out.append(f"{key}: {value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}: {value}")

    return f"{opening}{'\n'.join(out)}\n---\n{rest}"


def _append_verification_log(text: str, entry: str) -> str:
    """Append a short entry to verification_log list in frontmatter."""
    opening, fm_text, rest = _split_frontmatter(text)
    if not opening:
        return text

    lines = fm_text.splitlines()
    out: list[str] = []
    i = 0
    inserted = False

    while i < len(lines):
        line = lines[i]
        out.append(line)
        if re.match(r"^verification_log:\s*(\[\])?\s*$", line.strip()):
            j = i + 1
            while j < len(lines) and re.match(r"^\s+-\s+", lines[j]):
                out.append(lines[j])
                j += 1
            out.append(f"  - {entry}")
            inserted = True
            i = j
            continue
        i += 1

    if not inserted:
        out.append("verification_log:")
        out.append(f"  - {entry}")

    return f"{opening}{'\n'.join(out)}\n---\n{rest}"


def run_reverify(
    vault_root: Path = VAULT_ROOT,
    now: datetime | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Re-verify stale claim pages in the vault.

    For each stale page:
      - If it has an official source: update last_verified + add log entry.
      - If no official source: downgrade confidence high→medium + add log entry.
      - Never update last_verified when no official source.

    Args:
        vault_root: path to memory/vault
        now: reference datetime (defaults to utcnow)
        dry_run: if True, never write any files

    Returns:
        dict with keys: stale_before_reverify, stale_after_reverify,
        reverified_pages, downgraded_pages
    """
    if now is None:
        now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()

    stale_before = detect_stale_claims(vault_root, now=now)
    reverified_pages: list[str] = []
    downgraded_pages: list[str] = []

    for item in stale_before:
        page_stem = item["page"]
        path = _find_page(vault_root, page_stem)
        if path is None:
            continue

        text = path.read_text(encoding="utf-8")
        has_official = _has_official_source(text)

        if has_official:
            # Update last_verified + log entry, keep confidence unchanged
            text = _update_frontmatter_field(text, "last_verified", today_str)
            text = _append_verification_log(text, f"reverified {today_str} (official source)")
            reverified_pages.append(page_stem)
        else:
            # No official source: downgrade high→medium, add log entry, no last_verified change
            fm = _extract_frontmatter(text)
            conf = fm.get("confidence", "low").lower()
            if conf == "high":
                text = _update_frontmatter_field(text, "confidence", "medium")
                text = _append_verification_log(
                    text,
                    f"reverify {today_str}: no official source, downgraded high→medium",
                )
                downgraded_pages.append(page_stem)
            else:
                # confidence already medium or low — just log
                text = _append_verification_log(
                    text,
                    f"reverify {today_str}: no official source, confidence unchanged ({conf})",
                )

        if not dry_run:
            path.write_text(text, encoding="utf-8")

    stale_after = detect_stale_claims(vault_root, now=now)

    return {
        "stale_before_reverify": len(stale_before),
        "stale_after_reverify": len(stale_after),
        "reverified_pages": reverified_pages,
        "downgraded_pages": downgraded_pages,
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    from pathlib import Path

    result = run_reverify(Path(__file__).resolve().parents[1] / "memory" / "vault")
    print(result)
