import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests


SUPABASE_URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def run() -> Path:
    V = Path("memory/vault")

    # Metrics from local outputs
    no_dec_file = V / "insights" / "no-decisions.md"
    owner_file = V / "insights" / "owner-por-tema.md"
    recorr_file = V / "insights" / "temas-recorrentes.md"
    risk_file = V / "insights" / "risco-projetos.md"

    # Decisions in last 7 days
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/summaries"
        f"?select=meeting_id,decisions,topics,created_at&created_at=gte.{cutoff_date}",
        headers=H,
        timeout=30,
    )
    r.raise_for_status()
    recent = r.json()

    total_decisions = sum(len(s.get("decisions") or []) for s in recent)
    all_decisions = [d for s in recent for d in (s.get("decisions") or [])]

    all_topics = [t for s in recent for t in (s.get("topics") or [])]
    topic_freq = {}
    for t in all_topics:
        k = " ".join(str(t).split())[:60]
        topic_freq[k] = topic_freq.get(k, 0) + 1

    lines = [
        "# Resumo Executivo Semanal — Living Consultoria",
        f"_Gerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## Status dos Quick Wins",
        f"- QW1 no-decisions: {'✅' if no_dec_file.exists() else '❌'}",
        f"- QW2 owner por tema: {'✅' if owner_file.exists() else '❌'}",
        f"- QW3 temas recorrentes: {'✅' if recorr_file.exists() else '❌'}",
        f"- QW4 risco projetos: {'✅' if risk_file.exists() else '❌'}",
        "",
        "## Decisões da Semana",
        f"- Reuniões no período: **{len(recent)}**",
        f"- Decisões registradas: **{total_decisions}**",
        "",
        "## Top decisões (amostra)",
    ]

    for d in all_decisions[:8]:
        lines.append(f"- {str(d)[:140]}")
    if len(all_decisions) > 8:
        lines.append(f"- ... e mais {len(all_decisions) - 8} decisões")

    lines.extend(["", "## Temas mais frequentes"])
    for t, c in sorted(topic_freq.items(), key=lambda x: -x[1])[:5]:
        lines.append(f"- **{t}** ({c}x)")

    # Alerts from generated files
    alerts = []
    if no_dec_file.exists():
        for line in no_dec_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("**Total:**"):
                alerts.append(line)
                break

    if risk_file.exists():
        critical = [ln for ln in risk_file.read_text(encoding="utf-8").splitlines() if "🔴" in ln]
        if critical:
            alerts.append(f"Projetos críticos: {len(critical)}")

    if alerts:
        lines.extend(["", "## Alertas"])
        lines.extend(f"- {a}" for a in alerts[:5])

    out = V / "insights" / "resumo-semanal.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run())
