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
        "&limit=200",
        headers=H,
        timeout=30,
    )
    r.raise_for_status()
    meetings = r.json()

    if not meetings:
        out = Path("memory/vault/insights/no-decisions.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            "# Reuniões Sem Decisão Explícita\n\nNenhuma reunião enriquecida encontrada.",
            encoding="utf-8",
        )
        return out

    # Batch fetch summaries in chunks to avoid N+1 requests
    meeting_ids = [m["id"] for m in meetings if m.get("id")]
    summaries_by_meeting = {}

    chunk_size = 100
    for i in range(0, len(meeting_ids), chunk_size):
        chunk = meeting_ids[i:i + chunk_size]
        ids = ",".join(chunk)
        sr = requests.get(
            f"{SUPABASE_URL}/rest/v1/summaries"
            f"?select=meeting_id,decisions&meeting_id=in.({ids})",
            headers=H,
            timeout=30,
        )
        sr.raise_for_status()
        for row in sr.json():
            summaries_by_meeting.setdefault(row.get("meeting_id"), []).append(row)

    no_decisions = []
    for m in meetings:
        sid = m["id"]
        rows = summaries_by_meeting.get(sid, [])
        has_decision = any((row.get("decisions") or []) for row in rows)
        if not has_decision:
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
