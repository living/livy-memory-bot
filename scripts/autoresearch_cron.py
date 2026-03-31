#!/usr/bin/env python3
"""
Autoresearch Cron Wrapper — sends results via Telegram API (bot 8725269523)

1. Run autoresearch metrics + consolidation
2. Send each modified file as document attachment
3. Send summary with 👍/👎 feedback buttons
4. Feedback callbacks go to webhook handler on port 8080
"""

import ast
import json, os, subprocess, sys, requests
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8725269523:AAFqAFEFcbAa6daClbUiVH9qBLfzu46SMOQ"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
USER_ID = 7426291192  # Lincoln
CHAT_ID = USER_ID     # DM to Lincoln

WORKSPACE = Path("/home/lincoln/.openclaw/workspace-livy-memory")
MEMORY_DIR = WORKSPACE / "memory"
CURATED_DIR = MEMORY_DIR / "curated"

# ── Helpers ──────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def send_document(chat_id, file_path, caption=None):
    """Send a document via Telegram Bot API (no buttons in caption)."""
    url = f"{BASE_URL}/sendDocument"
    with open(file_path, "rb") as f:
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        files = {"document": (file_path.name, f)}
        resp = requests.post(url, data=data, files=files, timeout=30)
        result = resp.json()
        if not result.get("ok"):
            log(f"  ⚠️ sendDocument failed: {result.get('description', result)}")
        return result.get("ok")

def summarize_file(file_path, max_lines=7):
    """Gera resumo do arquivo (primeiras linhas / frontmatter)."""
    try:
        content = file_path.read_text()
        lines = content.split("\n")[:max_lines]
        summary_lines = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#+"):
                continue
            summary_lines.append(line)
            if len(summary_lines) >= 5:
                break
        summary = " | ".join(summary_lines[:5])
        if len(summary) > 150:
            summary = summary[:147] + "..."
        return summary if summary else "arquivo de memória"
    except:
        return "arquivo de memória"

def send_message(chat_id, text, reply_markup=None):
    """Send a text message via Telegram Bot API."""
    url = f"{BASE_URL}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    resp = requests.post(url, json=data, timeout=10)
    result = resp.json()
    if not result.get("ok"):
        log(f"  ⚠️ sendMessage failed: {result.get('description', result)}")
    return result.get("ok")

def feedback_buttons(action_id):
    """Inline keyboard with 👍/👎 for feedback."""
    return {
        "inline_keyboard": [[
            {"text": "👍", "callback_data": f"feedback:{action_id}:up"},
            {"text": "👎", "callback_data": f"feedback:{action_id}:down"},
        ]]
    }

# ── Metrics ─────────────────────────────────────────────────────────────────

def run_metrics():
    """Run autoresearch_metrics.py and return results."""
    log("Running metrics...")
    result = subprocess.run(
        ["python3", str(WORKSPACE / "skills/memoria-consolidation/autoresearch_metrics.py"), "--all"],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    if result.returncode != 0:
        log(f"⚠️ metrics failed: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout.strip())
    except:
        try:
            # Fallback: Python dict format
            return ast.literal_eval(result.stdout.strip())
        except:
            log(f"⚠️ metrics parse error: {result.stdout}")
            return None

# ── Consolidation ─────────────────────────────────────────────────────────────

def run_consolidation():
    """Run consolidate.py (dry-run first, apply if changes)."""
    log("Running consolidation (Mente Coletiva)...")
    result = subprocess.run(
        ["python3", str(WORKSPACE / "skills/memoria-consolidation/consolidate.py")],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    log(result.stdout)
    if result.returncode != 0:
        log(f"⚠️ consolidation failed: {result.stderr}")
    return result.returncode == 0

# ── Dream (Sessions) ──────────────────────────────────────────────────────────

def run_dream():
    """Run dream_all.py to process sessions."""
    log("Running dream (sessions do main)...")
    result = subprocess.run(
        ["python3", str(WORKSPACE / "skills/memoria-consolidation/dream_all.py")],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    if result.returncode != 0:
        log(f"⚠️ dream failed: {result.stderr}")
    return result.returncode == 0

# ── Get modified files ──────────────────────────────────────────────────────────

def get_curated_files():
    """List all curated markdown files."""
    if not CURATED_DIR.exists():
        return []
    return sorted(CURATED_DIR.glob("*.md"))

# ── Main ─────────────────────────────────────────────────────────────────────

# ── Feedback Learning ─────────────────────────────────────────────────────────────

def run_feedback_learning():
    """Lê feedback acumulado e atualiza learned-rules.md."""
    log("Processing accumulated feedback...")
    result = subprocess.run(
        ["python3", str(WORKSPACE / "skills/memoria-consolidation/learn_from_feedback.py")],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    if result.returncode == 0:
        log(result.stdout.strip())
    else:
        log(f"Feedback learning: {result.stderr.strip() or 'no feedback yet'}")
    return result.returncode == 0

def main():
    log("=== Autoresearch Cron (Telegram Direct) ===")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M BRT")

    # 0. Process feedback acumulado desde última execução
    run_feedback_learning()

    # 1. Run metrics before
    metrics_before = run_metrics()
    log(f"Metrics before: {metrics_before}")

    # 2. Run consolidation (Mente Coletiva)
    consolidation_ok = run_consolidation()

    # 3. Run dream (processa sessões do main)
    dream_ok = run_dream()

    # 3. Run metrics after
    metrics_after = run_metrics()
    log(f"Metrics after: {metrics_after}")

    # 4. Get files to send
    files = get_curated_files()
    log(f"Found {len(files)} curated files")

    # 5. Send intro message with file list and feedback buttons for each
    action_id = datetime.now().strftime("%Y%m%d%H%M")

    # Build buttons for each file
    file_buttons = []
    for f in files:
        file_buttons.append({"text": f"📄 {f.name}", "callback_data": f"view:{action_id}:{f.name}"})

    intro_keyboard = {
        "inline_keyboard": [
            [{"text": "👍 Tudo ok", "callback_data": f"feedback:{action_id}:all:up"},
             {"text": "👎 Precisa melhorar", "callback_data": f"feedback:{action_id}:all:down"}],
        ]
    }

    intro = f"""🧠 *Autoresearch — {timestamp}*

📊 *Métricas:* completeness {metrics_before.get('completeness',0):.1f} → {metrics_after.get('completeness',0):.1f} | crossrefs {metrics_before.get('crossrefs',0)} → {metrics_after.get('crossrefs',0)}

📁 *{len(files)} arquivos para revisar:*"""

    send_message(CHAT_ID, intro, reply_markup=intro_keyboard)

    # 6. Send each file as document (no buttons) + summary message with buttons
    sent_files = []
    for f in files:
        log(f"Sending {f.name}...")
        # Message 1: document only
        ok = send_document(
            CHAT_ID, f,
            caption=f"📄 {f.name}"
        )
        if ok:
            sent_files.append(f.name)
            # Message 2: summary + feedback buttons
            summary = summarize_file(f)
            msg = f"Resumo: {summary}\n\n"
            send_message(
                CHAT_ID, msg,
                reply_markup=feedback_buttons(f"{action_id}:{f.name}")
            )

    # 7. Send summary with feedback button
    if metrics_before and metrics_after:
        delta_completeness = metrics_after.get("completeness", 0) - metrics_before.get("completeness", 0)
        delta_crossrefs = metrics_after.get("crossrefs", 0) - metrics_before.get("crossrefs", 0)

        summary = f"""📋 *Resumo:*
• completeness: {metrics_before.get('completeness',0):.1f} → {metrics_after.get('completeness',0):.1f} {'✅' if delta_completeness >= 0 else '❌'}
• crossrefs: {metrics_before.get('crossrefs',0)} → {metrics_after.get('crossrefs',0)} {'✅' if delta_crossrefs >= 0 else '❌'}
• actions: {metrics_after.get('actions',0)}

Clique nos botões acima para avaliar."""

        if consolidation_ok:
            summary += f"\n\n✅ Consolidation completed."
    else:
        summary = f"⚠️ Metrics unavailable."

    ok = send_message(
        CHAT_ID, summary,
        reply_markup=feedback_buttons(f"{action_id}:summary")
    )

    if ok:
        log("=== Autoresearch Cron COMPLETE ===")
    else:
        log("⚠️ Summary send failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
