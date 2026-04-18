import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests


SUPABASE_URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def normalize_topic(topic: str) -> str:
    return " ".join(topic.lower().split())[:70]


def run() -> Path:
    if not SUPABASE_URL or not KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing")

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/summaries"
        "?select=meeting_id,topics,decisions&order=created_at.desc&limit=200",
        headers=H,
        timeout=30,
    )
    r.raise_for_status()
    summaries = r.json()

    topic_meetings: dict[str, set] = defaultdict(set)
    topic_decisions: dict[str, int] = defaultdict(int)

    for s in summaries:
        mid = s.get("meeting_id")
        topics = s.get("topics") or []
        decisions = s.get("decisions") or []
        for t in topics:
            key = normalize_topic(t)
            if not key:
                continue
            topic_meetings[key].add(mid)
            if decisions:
                topic_decisions[key] += len(decisions)

    recurring = {k: v for k, v in topic_meetings.items() if len(v) >= 3}

    out = Path("memory/vault/insights/temas-recorrentes.md")
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Temas Recorrentes Sem Fechamento",
        f"_Gerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        f"**Total de temas recorrentes (3+ reuniões):** {len(recurring)}",
        "",
        "| Tema | Reuniões | Decisões | Status |",
        "| --- | --- | --- | --- |",
    ]

    for theme, mids in sorted(recurring.items(), key=lambda x: -len(x[1])):
        decisions = topic_decisions.get(theme, 0)
        status = "✅ Tem decisão" if decisions > 0 else "⚠️ Sem decisão"
        lines.append(f"| {theme[:60]} | {len(mids)} | {decisions} | {status} |")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run())
