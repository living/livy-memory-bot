"""Weekly insights generation cron — claims-first with HTML group attachment.

Scheduled: weekly via openclaw cron.
Loads from SSOT claims (state["claims"]), falls back to markdown when the
weekly window is not covered.

Outputs:
  - Personal: structured text → Telegram direct (7426291192) with weekly dedupe
  - Group:   self-contained HTML file → Telegram document to group (-5158607302)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Bootstrap: same pattern as other operational crons in this repo
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Load env after bootstrap so load_state and telegram calls pick up real tokens
def load_env() -> None:
    env_file = Path.home() / ".openclaw" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


import requests  # noqa: E402  (after load_env)


BOT_TOKEN: str = ""
CHAT_ID_PERSONAL: str = "7426291192"
CHAT_ID_GROUP: str = "-5158607302"
BASE_URL: str = ""


def _resolve_vault() -> Path:
    env_vault = os.environ.get("SOURCE_VAULT")
    if env_vault:
        return Path(env_vault)
    return Path(__file__).resolve().parents[2] / "memory" / "vault"


def _resolve_workspace() -> Path:
    return Path(__file__).resolve().parents[2]


def _send_telegram_message(chat_id: str, text: str) -> bool:
    """Send markdown text to a Telegram chat."""
    if not BOT_TOKEN:
        print(f"[TELEGRAM_DISABLED] dry-run message to {chat_id}: {text[:120]}")
        return False
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=20)
        result = resp.json()
        if not result.get("ok"):
            print(f"[TELEGRAM_ERROR] {result.get('description', result)}")
            return False
        return True
    except Exception as exc:
        print(f"[TELEGRAM_ERROR] {exc}")
        return False


def _send_telegram_document(chat_id: str, file_path: Path, caption: str = "") -> bool:
    """Send a file as a Telegram document attachment (asDocument=True)."""
    if not BOT_TOKEN:
        print(f"[TELEGRAM_DISABLED] dry-run document to {chat_id}: {file_path.name}")
        return False
    url = f"{BASE_URL}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            files = {"document": (file_path.name, f, "text/html")}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            resp = requests.post(url, data=data, files=files, timeout=30)
        result = resp.json()
        if not result.get("ok"):
            print(f"[TELEGRAM_ERROR] {result.get('description', result)}")
            return False
        return True
    except Exception as exc:
        print(f"[TELEGRAM_ERROR] {exc}")
        return False


def _dedupe_state_path() -> Path:
    return _resolve_vault() / "insights" / ".weekly_personal_sent.json"


def _check_dedupe() -> bool:
    """Return True if a real (non-dry-run) personal report was already sent this week."""
    state_path = _dedupe_state_path()
    if not state_path.exists():
        return False
    try:
        last = json.loads(state_path.read_text())
        week = datetime.now(timezone.utc).isocalendar()[1]
        return bool(last.get("week") == week and not last.get("dry_run"))
    except Exception:
        return False


def _record_dedupe(dry_run: bool) -> None:
    state_path = _dedupe_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({
        "week": datetime.now(timezone.utc).isocalendar()[1],
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
    }))


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def _load_openclaw_telegram_token(account_id: str = "memory") -> Optional[str]:
    """Fallback token loader from local OpenClaw config (for ops crons).

    Useful when .env TELEGRAM_TOKEN points to a different bot account.
    """
    try:
        cfg_path = Path.home() / ".openclaw" / "openclaw.json"
        if not cfg_path.exists():
            return None
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        token = (
            cfg.get("channels", {})
            .get("telegram", {})
            .get("accounts", {})
            .get(account_id, {})
            .get("botToken")
        )
        if isinstance(token, str) and token.strip():
            return token.strip()
        return None
    except Exception:
        return None


def _resolve_bot_token() -> str:
    """Resolve token with explicit precedence for memory-agent operations."""
    return (
        os.environ.get("TELEGRAM_BOT_TOKEN")
        or os.environ.get("TELEGRAM_MEMORY_BOT_TOKEN")
        or _load_openclaw_telegram_token("memory")
        or os.environ.get("TELEGRAM_TOKEN", "")
    )


def main() -> dict:
    load_env()

    global BOT_TOKEN, BASE_URL, CHAT_ID_PERSONAL, CHAT_ID_GROUP
    BOT_TOKEN = _resolve_bot_token()
    CHAT_ID_PERSONAL = os.environ.get("TELEGRAM_CHAT_ID_PERSONAL", CHAT_ID_PERSONAL)
    CHAT_ID_GROUP = os.environ.get("TELEGRAM_CHAT_ID_GROUP", CHAT_ID_GROUP)
    BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

    dry_run = os.environ.get("DRY_RUN_INSIGHTS", "").lower() in ("1", "true")
    vault = _resolve_vault()
    workspace = _resolve_workspace()

    # ---------------------------------------------------------------------------
    # Load claims — claims-first with temporal fallback
    # ---------------------------------------------------------------------------
    state_path = workspace / "state" / "identity-graph" / "state.json"
    claims_dir = vault / "claims"

    from vault.insights.claim_inspector import extract_insights, load_claims_with_fallback  # noqa: E402
    from vault.insights.renderers import render_personal, render_group_html  # noqa: E402

    claims, used_fallback = load_claims_with_fallback(state_path, claims_dir)
    bundle = extract_insights(claims)

    if used_fallback:
        _log(f"[FALLBACK] SSOT had no claims in weekly window — used {len(claims)} markdown claims")
    else:
        _log(f"[SSOT] Loaded {len(claims)} claims from state[{len(claims)}]")

    # ---------------------------------------------------------------------------
    # Render outputs
    # ---------------------------------------------------------------------------
    personal_text = render_personal(bundle)
    group_html = render_group_html(bundle)

    _log(f"Personal report: {len(personal_text)} chars")
    _log(f"Group HTML: {len(group_html)} bytes")

    results: dict = {
        "claims_total": len(claims),
        "used_fallback": used_fallback,
        "active": bundle.active,
        "superseded": bundle.superseded_total,
        "by_source": bundle.by_source,
        "personal_chars": len(personal_text),
        "group_html_bytes": len(group_html),
        "personal_sent": False,
        "group_sent": False,
    }

    # ---------------------------------------------------------------------------
    # Personal delivery (with dedupe)
    # ---------------------------------------------------------------------------
    if _check_dedupe() and not dry_run:
        _log("[SKIP] Personal report already sent this week — dedupe active")
    else:
        if dry_run:
            _log("=== PREVIEW PERSONAL REPORT ===")
            print("\n".join(personal_text.splitlines(True)[:20]))
            print("=== END PREVIEW ===")
        else:
            ok = _send_telegram_message(CHAT_ID_PERSONAL, personal_text)
            if ok:
                _log(f"[OK] Personal report sent to {CHAT_ID_PERSONAL}")
                results["personal_sent"] = True
                _record_dedupe(dry_run=False)
            else:
                _log("[FAIL] Personal report delivery failed")

    # ---------------------------------------------------------------------------
    # Group delivery (HTML document, no dedupe)
    # ---------------------------------------------------------------------------
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    html_file = vault / "insights" / f"living-insights-{today}.html"
    html_file.parent.mkdir(parents=True, exist_ok=True)
    html_file.write_text(group_html, encoding="utf-8")
    _log(f"HTML report written: {html_file}")

    if dry_run:
        _log(f"[DRY-RUN] Group document would be sent: {html_file.name}")
    else:
        caption = f"📊 Living Insights Semanais — {bundle.week_start} → {bundle.week_end}"
        ok = _send_telegram_document(CHAT_ID_GROUP, html_file, caption=caption)
        if ok:
            _log(f"[OK] Group HTML document sent to {CHAT_ID_GROUP}")
            results["group_sent"] = True
        else:
            _log("[FAIL] Group HTML document delivery failed")

    return results


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, ensure_ascii=False))
