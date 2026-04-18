"""
Envia resumo-semanal.md para Telegram (chat 7426291192).
Dry-run: apenas valida, mostra preview e log. Não envia de verdade.
Para ativar, trocar DRY_RUN = False.
"""
import os
import json
from datetime import datetime, timezone
from pathlib import Path


DRY_RUN = True
CHAT_ID = "7426291192"
STATE_FILE = Path("memory/vault/insights/.last_sent.json")


def run():
    # Resolve vault path relative to script location, not hardcoded machine path.
    env_vault = os.environ.get("SOURCE_VAULT")
    if env_vault:
        V = Path(env_vault)
    else:
        V = Path(__file__).parent.parent.parent / "memory" / "vault"

    resumo = V / "insights" / "resumo-semanal.md"

    if not resumo.exists():
        print("[WARN] resumo-semanal.md não existe — pulando")
        return

    text = resumo.read_text(encoding="utf-8")
    current_week = datetime.now(timezone.utc).isocalendar()[1]

    # Check if already sent this week
    if STATE_FILE.exists():
        last = json.loads(STATE_FILE.read_text())
        if last.get("week") == current_week and not DRY_RUN:
            print(f"[SKIP] Já enviado na semana {current_week}")
            return

    # Build compact preview (first 18 lines)
    preview = "\n".join(text.splitlines(True)[:18])
    print("=== PREVIEW DO RESUMO SEMANAL ===")
    print(preview)
    print("=================================")

    if DRY_RUN:
        print("[DRY-RUN] Nenhuma mensagem enviada. "
              "Defina DRY_RUN=False para ativar o envio real via message tool.")
        print(f"[INFO] Resumo: {len(text)} chars, week={current_week}")
        # Write state anyway to simulate
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({
            "week": current_week,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
        }))
        print(f"[STATE] Logged dry-run to {STATE_FILE}")
    else:
        print("[TODO] Wire message tool here to send to Telegram")


if __name__ == "__main__":
    run()
