import os
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def run() -> Path:
    # In worktrees, memory/vault/entities is gitignored and may be absent.
    # Use SOURCE_VAULT when provided, otherwise fallback to the main workspace vault.
    source_vault = Path(os.environ.get("SOURCE_VAULT", "/home/lincoln/.openclaw/workspace-livy-memory/memory/vault"))
    out_vault = Path("memory/vault")

    # Load all projects
    projects_dir = source_vault / "entities" / "projects"
    projects = [p.stem for p in projects_dir.glob("*.md")]
    if not projects:
        raise RuntimeError(f"No projects found in source vault: {projects_dir}")

    # Load relationships
    card_person = json.loads((source_vault / "relationships" / "card-person.json").read_text())
    card_project = json.loads((source_vault / "relationships" / "card-project.json").read_text())
    pm = json.loads((source_vault / "relationships" / "person-meeting.json").read_text())

    # Count meeting edges (unique meetings with at least one person)
    meeting_ids_with_people = {e["to_id"] for e in pm.get("edges", [])}
    all_meetings_count = len(list((source_vault / "entities" / "meetings").glob("*.md")))
    orphan_meetings = all_meetings_count - len(meeting_ids_with_people)

    # Cards linked per project
    project_cards: dict[str, int] = defaultdict(int)
    for e in card_project.get("edges", []):
        proj_raw = e.get("properties", {}).get("project", "")
        if proj_raw:
            project_cards[proj_raw.strip()] += 1

    # All cards count
    all_cards_count = len(list((source_vault / "entities" / "cards").glob("*.md")))
    total_linked_cards = sum(project_cards.values())
    orphan_cards = all_cards_count - total_linked_cards

    # Score per project
    # - orphan cards relative to project size: +5 per orphan card share
    # - orphan meetings * 3
    # - age: meetings older than 30 days without enrich
    projects_scores = {}
    for proj in projects:
        linked = project_cards.get(proj, 0)
        # Score: orphan cards penalty proportional
        orphan_card_penalty = min(30, (all_cards_count - linked) * 2 if all_cards_count else 0)
        orphan_meeting_penalty = min(30, orphan_meetings * 2)
        # Participation completeness: meetings with people / total meetings
        score = orphan_card_penalty + orphan_meeting_penalty
        projects_scores[proj] = {
            "score": score,
            "cards_linked": linked,
            "orphan_cards": orphan_cards,
            "orphan_meetings": orphan_meetings,
        }

    out = out_vault / "insights" / "risco-projetos.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Painel de Risco por Projeto",
        f"_Gerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        f"| Projeto | Score | Cards | Órfãos Reuniões |",
        f"| --- | --- | --- | --- |",
    ]

    for proj, data in sorted(projects_scores.items(), key=lambda x: -x[1]["score"]):
        score = data["score"]
        risk = "🔴 CRÍTICO" if score > 50 else "🟡 ATENÇÃO" if score > 25 else "✅ OK"
        lines.append(
            f"| {proj[:40]} | {risk} {score} | {data['cards_linked']} | {data['orphan_meetings']} |"
        )

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run())
