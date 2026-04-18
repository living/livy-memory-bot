"""
Envia resumo-semanal.md para Telegram (chat 7426291192).
Controle semanal via .last_sent.json — não envia duas vezes na mesma semana.
Ambiente: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (opcionais, defaults definidos).
"""
import os
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7426291192")
DRY_RUN = False  # Ativado — enviar para Telegram de verdade
DRY_RUN_FALLBACK = os.environ.get("DRY_RUN_RESUMO", "false").lower() in ("1", "true")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""


def _send_telegram(text: str, chat_id: str) -> bool:
    """Envia texto via Telegram Bot API. Retorna True se ok."""
    if not BOT_TOKEN:
        print(f"[TELEGRAM_DISABLED] Modo Dry-Run: {text[:120]}")
        return False

    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, json=payload, timeout=15)
    result = resp.json()
    if not result.get("ok"):
        print(f"[TELEGRAM_ERROR] {result.get('description', result)}")
        return False
    return True


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def run() -> Path | None:
    dry_run = DRY_RUN or DRY_RUN_FALLBACK

    env_vault = os.environ.get("SOURCE_VAULT")
    if env_vault:
        V = Path(env_vault)
    else:
        V = Path(__file__).resolve().parents[2] / "memory" / "vault"

    resumo = V / "insights" / "resumo-semanal.md"
    state_file = V / "insights" / ".last_sent.json"

    if not resumo.exists():
        _log(f"[WARN] resumo-semanal.md não existe — pulando (vault: {V})")
        return None

    text = resumo.read_text(encoding="utf-8")
    current_week = datetime.now(timezone.utc).isocalendar()[1]

    # Deduplicação semanal
    if state_file.exists():
        last = json.loads(state_file.read_text())
        already_sent_real = last.get("week") == current_week and not bool(last.get("dry_run", False))
        if already_sent_real and not dry_run:
            _log(f"[SKIP] Já enviado na semana {current_week} — pulando")
            return None

    if dry_run:
        preview = "\n".join(text.splitlines(True)[:18])
        _log("=== PREVIEW DO RESUMO SEMANAL (DRY-RUN) ===")
        print(preview)
        print("=" * 42)
        _log(f"[DRY-RUN] Nenhuma mensagem enviada. week={current_week}")
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({
            "week": current_week,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
        }))
        _log(f"[STATE] dry-run logged to {state_file}")
        return None

    # Envio real
    _log(f"Enviando resumo semanal para {CHAT_ID} — {len(text)} chars")
    ok = _send_telegram(text, CHAT_ID)

    if ok:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({
            "week": current_week,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": False,
        }))
        _log(f"[OK] Resumo enviado e registrado (week={current_week})")
    else:
        _log(f"[FAIL] Envio Telegram retornou erro — state NÃO atualizado")

    return state_file


if __name__ == "__main__":
    run()
