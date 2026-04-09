#!/usr/bin/env python3
"""
learn_from_feedback.py — Feedback log → learned rules

Reads memory/feedback-log.jsonl, calculates score per action type,
and generates/updates memory/learned-rules.md.

Score = (count of "up") - (count of "down")
Actions with rating: null are counted but don't affect score.
"""

import json
import collections
from datetime import date
from pathlib import Path

FEEDBACK_LOG   = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/feedback-log.jsonl")
FEEDBACK_ARCHIVE = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/feedback-archive.jsonl")
LEARNED_RULES  = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/learned-rules.md")


def load_feedback(path: Path) -> list[dict]:
    """Lê feedback-log.jsonl, retorna lista de dicts."""
    if not path.exists():
        return []

    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            # Skip malformed lines silently
            pass
    return entries


def get_feedback_buffer() -> list[dict]:
    """Expose structured feedback buffer for confidence calibrator ingestion.

    Returns raw feedback entries from FEEDBACK_LOG (JSONL).
    This function is intentionally read-only and deterministic.
    """
    return load_feedback(FEEDBACK_LOG)


def build_calibration_feedback(entries: list[dict]) -> list[dict]:
    """Normalize feedback entries into calibrator schema.

    Calibrator schema:
    - decision: "promote" | "defer"
    - outcome:  "up" | "down"

    Mapping from feedback log fields:
    - action -> decision (only promote/defer retained)
    - rating -> outcome (only up/down retained)

    Entries without required valid pairs are skipped.
    """
    normalized: list[dict] = []
    for entry in entries:
        decision = entry.get("action")
        outcome = entry.get("rating")
        if decision not in {"promote", "defer"}:
            continue
        if outcome not in {"up", "down"}:
            continue
        normalized.append({"decision": decision, "outcome": outcome})
    return normalized


def compute_scores(entries: list[dict]) -> dict[str, dict]:
    """
    Agrupa entries por action, conta up/down/null.
    Retorna dict: action -> {up, down, null, score}
    """
    # action -> {'up': int, 'down': int, 'null': int, 'notes': list[str]}
    stats = collections.defaultdict(lambda: {"up": 0, "down": 0, "null": 0, "notes": []})

    for entry in entries:
        action  = entry.get("action") or "unknown"
        rating  = entry.get("rating")
        note    = entry.get("note")

        if rating == "up":
            stats[action]["up"] += 1
        elif rating == "down":
            stats[action]["down"] += 1
        else:
            stats[action]["null"] += 1

        if note:
            stats[action]["notes"].append(note)

    # Calculate score
    for action, s in stats.items():
        s["score"] = s["up"] - s["down"]

    return dict(stats)


def build_markdown(stats: dict[str, dict], today: str) -> str:
    """Gera conteúdo markdown para learned-rules.md."""
    positive = [(a, s) for a, s in stats.items() if s["score"] > 0]
    negative = [(a, s) for a, s in stats.items() if s["score"] < 0]
    neutral  = [(a, s) for a, s in stats.items() if s["score"] == 0]

    positive.sort(key=lambda x: -x[1]["score"])
    negative.sort(key=lambda x: x[1]["score"])
    neutral.sort(key=lambda x: x[0])

    lines = [
        "# Learned Rules — Livy Memory Agent",
        "",
        f"Gerado por: learn_from_feedback.py",
        f"Atualizado: {today}",
        "",
    ]

    # Positive rules
    lines.append("## Regras com score positivo (manter padrão)")
    if not positive:
        lines.append("_Nenhuma regra aprendida ainda._")
    else:
        for action, s in positive:
            thumbs_up   = s["up"]
            thumbs_down = s["down"]
            notes_str   = ""
            if s["notes"]:
                unique_notes = list(dict.fromkeys(s["notes"]))
                notes_str = "\n  Notas: " + ", ".join(f'"{n}"' for n in unique_notes)
            lines.append(
                f"- `{action}`: score +{s['score']} ({thumbs_up}\u270d {thumbs_down}\u270e){notes_str}"
            )
    lines.append("")

    # Negative rules
    lines.append("## Regras com score negativo (evitar)")
    if not negative:
        lines.append("_Nenhuma regra aprendida ainda._")
    else:
        for action, s in negative:
            thumbs_up   = s["up"]
            thumbs_down = s["down"]
            notes_str   = ""
            if s["notes"]:
                unique_notes = list(dict.fromkeys(s["notes"]))
                notes_str = "\n  Notas: " + ", ".join(f'"{n}"' for n in unique_notes)
            lines.append(
                f"- `{action}`: score {s['score']} ({thumbs_up}\u270d {thumbs_down}\u270e){notes_str}"
            )
    lines.append("")

    # Neutral rules
    lines.append("## Regras neutras (experimentar aborduras alternativas)")
    if not neutral:
        lines.append("_Nenhuma regra aprendida ainda._")
    else:
        for action, s in neutral:
            thumbs_up   = s["up"]
            thumbs_down = s["down"]
            notes_str   = ""
            if s["notes"]:
                unique_notes = list(dict.fromkeys(s["notes"]))
                notes_str = "\n  Notas: " + ", ".join(f'"{n}"' for n in unique_notes)
            lines.append(
                f"- `{action}`: score 0 ({thumbs_up}\u270d {thumbs_down}\u270e){notes_str}"
            )
    lines.append("")
    lines.append("---")
    lines.append("_score = thumbs_up - thumbs_down por tipo de ação_")

    return "\n".join(lines)


def main():
    today = date.today().isoformat()

    entries = load_feedback(FEEDBACK_LOG)

    if not entries:
        print("Nenhum feedback para processar.")
        return

    # Archive feedback before processing
    with FEEDBACK_ARCHIVE.open("a") as arch:
        for entry in entries:
            arch.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # Clear the feedback log
    FEEDBACK_LOG.write_text("")
    print(f"Feedback arquivado ({len(entries)} entradas) e log limpo.")

    stats = compute_scores(entries)

    positive = sum(1 for s in stats.values() if s["score"] > 0)
    negative = sum(1 for s in stats.values() if s["score"] < 0)
    neutral  = sum(1 for s in stats.values() if s["score"] == 0)

    print(f"Regras geradas: {positive} positivas, {negative} negativas, {neutral} neutras")

    markdown = build_markdown(stats, today)
    LEARNED_RULES.write_text(markdown)
    print(f"Arquivo gerado: {LEARNED_RULES}")


if __name__ == "__main__":
    main()
