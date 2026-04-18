import os
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _resolve_source_vault() -> Path:
    env_vault = os.environ.get("SOURCE_VAULT")
    if env_vault:
        p = Path(env_vault)
    else:
        # repo_root/vault/insights/.. -> repo_root
        p = Path(__file__).resolve().parents[2] / "memory" / "vault"

    if not p.exists():
        raise RuntimeError(
            f"SOURCE_VAULT not set and default path does not exist: {p}. "
            "Set SOURCE_VAULT to a valid memory/vault directory."
        )
    return p


def run() -> Path:
    source_vault = _resolve_source_vault()
    out_vault = Path("memory/vault")

    projects_dir = source_vault / "entities" / "projects"
    projects = [p.stem for p in projects_dir.glob("*.md")]
    if not projects:
        raise RuntimeError(f"No projects found in source vault: {projects_dir}")

    card_project = json.loads((source_vault / "relationships" / "card-project.json").read_text())
    card_person = json.loads((source_vault / "relationships" / "card-person.json").read_text())
    person_meeting = json.loads((source_vault / "relationships" / "person-meeting.json").read_text())

    # project -> cards
    project_cards: dict[str, set[str]] = defaultdict(set)
    for e in card_project.get("edges", []):
        project_id = e.get("to_id", "")
        card_id = e.get("from_id", "")
        if project_id and card_id:
            project_cards[project_id].add(card_id)

    # card -> people
    card_people: dict[str, set[str]] = defaultdict(set)
    for e in card_person.get("edges", []):
        card_id = e.get("from_id", "")
        person_id = e.get("to_id", "")
        if card_id and person_id:
            card_people[card_id].add(person_id)

    # person -> meetings
    person_meetings: dict[str, set[str]] = defaultdict(set)
    for e in person_meeting.get("edges", []):
        person_id = e.get("from_id", "")
        meeting_id = e.get("to_id", "")
        if person_id and meeting_id:
            person_meetings[person_id].add(meeting_id)

    projects_scores = {}
    for project in projects:
        project_id = f"project:{project}"
        cards = project_cards.get(project_id, set())

        # People assigned to cards of this project
        people = set()
        for card_id in cards:
            people.update(card_people.get(card_id, set()))

        # Meetings linked to those people
        meetings = set()
        active_people = 0
        for person_id in people:
            p_meetings = person_meetings.get(person_id, set())
            if p_meetings:
                active_people += 1
                meetings.update(p_meetings)

        orphan_cards = sum(1 for card_id in cards if not card_people.get(card_id))
        orphan_card_rate = (orphan_cards / max(len(cards), 1)) * 100
        meeting_coverage = (active_people / max(len(people), 1)) * 100 if people else 0

        # Per-project score (0..100-ish)
        # - high orphan cards => risk
        # - low meeting coverage of assigned people => risk
        # - very low card volume => slight uncertainty penalty
        orphan_penalty = min(50, orphan_card_rate * 0.6)
        meeting_penalty = min(40, (100 - meeting_coverage) * 0.4)
        volume_penalty = 10 if len(cards) < 3 else 0
        score = round(orphan_penalty + meeting_penalty + volume_penalty, 1)

        projects_scores[project] = {
            "score": score,
            "cards_total": len(cards),
            "orphan_cards": orphan_cards,
            "people_total": len(people),
            "active_people": active_people,
            "meeting_coverage": round(meeting_coverage, 1),
            "meetings": len(meetings),
        }

    out = out_vault / "insights" / "risco-projetos.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Painel de Risco por Projeto",
        f"_Gerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "Cálculo por projeto: taxa de cards órfãos + cobertura de reuniões por pessoas do projeto.",
        "",
        "| Projeto | Score | Cards | Órfãos | Pessoas | Cobertura reuniões |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for project, data in sorted(projects_scores.items(), key=lambda x: -x[1]["score"]):
        score = data["score"]
        risk = "🔴 CRÍTICO" if score >= 60 else "🟡 ATENÇÃO" if score >= 30 else "✅ OK"
        lines.append(
            f"| {project[:40]} | {risk} {score} | {data['cards_total']} | {data['orphan_cards']} "
            f"| {data['people_total']} | {data['meeting_coverage']}% |"
        )

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run())
