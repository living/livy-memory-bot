import os
from datetime import datetime, timezone
from pathlib import Path

import requests


SUPABASE_URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def run() -> Path:
    if not SUPABASE_URL or not KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing")

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/meetings"
        "?select=id,name,created_at,enriched_at"
        "&enriched_at=not.is.null"
        "&order=created_at.desc"
        "&limit=100",
        headers=H,
        timeout=30,
    )
    r.raise_for_status()
    meetings = r.json()

    no_decisions = []
    for m in meetings:
        sid = m["id"]
        sr = requests.get(
            f"{SUPABASE_URL}/rest/v1/summaries"
            f"?select=decisions&meeting_id=eq.{sid}&limit=1",
            headers=H,
            timeout=15,
        )
        if sr.ok:
            summaries = sr.json()
            if not summaries or not summaries[0].get("decisions"):
                no_decisions.append(m)

    out = Path("memory/vault/insights/no-decisions.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Reuniões Sem Decisão Explícita",
        f"_Gerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        f"**Total:** {len(no_decisions)} de {len(meetings)} reuniões enriquecidas",
        "",
    ]
    for m in no_decisions:
        date = m.get("created_at", "")[:10]
        lines.append(f"- **{date}** · {m.get('name', 'sem nome')}")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run())
