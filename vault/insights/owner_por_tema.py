import os
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests


SUPABASE_URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def _resolve_source_vault() -> Path:
    env_vault = os.environ.get("SOURCE_VAULT")
    if env_vault:
        p = Path(env_vault)
    else:
        p = Path(__file__).resolve().parents[2] / "memory" / "vault"

    if not p.exists():
        raise RuntimeError(
            f"SOURCE_VAULT not set and default path does not exist: {p}. "
            "Set SOURCE_VAULT to a valid memory/vault directory."
        )
    return p


def run() -> Path:
    if not SUPABASE_URL or not KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing")

    V = _resolve_source_vault()

    # Load person-meeting edges
    pm_path = V / "relationships" / "person-meeting.json"
    if not pm_path.exists():
        raise FileNotFoundError("person-meeting.json missing")

    edges = json.loads(pm_path.read_text()).get("edges", [])

    # Group edges by meeting_id (to_id = meeting:id_canonical)
    meeting_people: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        meeting_people[e["to_id"]].append(e["from_id"])

    # Fetch summaries with topics and decisions
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/summaries"
        "?select=meeting_id,topics,decisions&order=created_at.desc&limit=50",
        headers=H,
        timeout=30,
    )
    r.raise_for_status()
    summaries = r.json()

    theme_owners: dict = defaultdict(lambda: {"meetings": 0, "people": set(), "decisions": 0})

    for s in summaries:
        mid = s.get("meeting_id", "")
        meeting_key = f"meeting:{mid}"
        people = meeting_people.get(meeting_key, [])
        topics = s.get("topics") or []
        decisions = s.get("decisions") or []

        for topic in topics:
            key = topic[:60].lower()
            theme_owners[key]["meetings"] += 1
            theme_owners[key]["decisions"] += len(decisions)
            for p in people:
                theme_owners[key]["people"].add(p)

        # Also track meetings without any topic
        if not topics and decisions:
            key = "sem-tema-definido"
            theme_owners[key]["meetings"] += 1
            theme_owners[key]["decisions"] += len(decisions)
            for p in people:
                theme_owners[key]["people"].add(p)

    out = V / "insights" / "owner-por-tema.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Owner por Tema de Reunião",
        f"_Gerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        f"| Tema | Reuniões | Decisões | Pessoas |",
        f"| --- | --- | --- | --- |",
    ]

    sorted_themes = sorted(theme_owners.items(), key=lambda x: -x[1]["decisions"])
    for theme, data in sorted_themes[:30]:
        people_list = sorted(data["people"])
        people_str = ", ".join(p.replace("person:tldv:", "").replace("person:", "") for p in people_list[:5])
        if len(data["people"]) > 5:
            people_str += f" (+{len(data['people']) - 5})"
        lines.append(f"| {theme[:55]} | {data['meetings']} | {data['decisions']} | {people_str} |")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run())
