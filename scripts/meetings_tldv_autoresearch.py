#!/usr/bin/env python3
"""
meetings_tldv_autoresearch.py — Daily feedback processing + hypothesis testing.

Reads memory/meetings-tldv-feedback-log.jsonl, calculates scores,
generates memory/meetings-tldv-learned-rules.md, commits to GitHub.
"""

import collections
import json
import subprocess
from datetime import date
from pathlib import Path

WORKSPACE = Path("/home/lincoln/.openclaw/workspace-livy-memory")
FEEDBACK_LOG = WORKSPACE / "memory/meetings-tldv-feedback-log.jsonl"
FEEDBACK_ARCHIVE = WORKSPACE / "memory/meetings-tldv-feedback-archive.jsonl"
LEARNED_RULES = WORKSPACE / "memory/meetings-tldv-learned-rules.md"


def load_feedback(path: Path) -> list[dict]:
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
            pass
    return entries


def compute_scores(entries: list[dict]) -> dict[str, dict]:
    """Group by action (mode|query_pattern), count up/down, calc score."""
    stats = collections.defaultdict(lambda: {"up": 0, "down": 0, "notes": []})
    for entry in entries:
        action = entry.get("action") or "unknown"
        rating = entry.get("rating")
        note = entry.get("note")
        if rating == "up":
            stats[action]["up"] += 1
        elif rating == "down":
            stats[action]["down"] += 1
        if note:
            stats[action]["notes"].append(note)
    for action, s in stats.items():
        s["score"] = s["up"] - s["down"]
    return dict(stats)


def build_markdown(stats: dict, today: str, prev_hypotheses: list[str]) -> str:
    positive = [(a, s) for a, s in stats.items() if s["score"] > 0]
    negative = [(a, s) for a, s in stats.items() if s["score"] < 0]
    neutral = [(a, s) for a, s in stats.items() if s["score"] == 0]

    positive.sort(key=lambda x: -x[1]["score"])
    negative.sort(key=lambda x: x[1]["score"])

    lines = [
        "# Learned Rules — meetings-tldv\n",
        f"> Gerado por: scripts/meetings_tldv_autoresearch.py | Atualizado: {today}\n",
        "---\n",
        "## Regras com score positivo (manter padrão)\n",
    ]
    if not positive:
        lines.append("_Nenhuma regra aprendida ainda._\n")
    else:
        for action, s in positive:
            notes_str = ""
            if s["notes"]:
                unique_notes = list(dict.fromkeys(s["notes"]))
                notes_str = f" — Notas: {', '.join(f'\"{n}\"' for n in unique_notes)}"
            lines.append(
                f"- `{action}`: score +{s['score']} ({s['up']}👍 {s['down']}👎){notes_str}\n"
            )

    lines.append("\n## Regras com score negativo (evitar)\n")
    if not negative:
        lines.append("_Nenhuma regra aprendida ainda._\n")
    else:
        for action, s in negative:
            notes_str = ""
            if s["notes"]:
                unique_notes = list(dict.fromkeys(s["notes"]))
                notes_str = f" — Notas: {', '.join(f'\"{n}\"' for n in unique_notes)}"
            lines.append(
                f"- `{action}`: score {s['score']} ({s['up']}👍 {s['down']}👎){notes_str}\n"
            )

    if prev_hypotheses:
        lines.append("\n## Hipóteses testadas\n")
        for h in prev_hypotheses:
            lines.append(f"- {h}\n")

    return "".join(lines)


def generate_hypotheses(stats: dict) -> list[str]:
    """Generate hypotheses based on score patterns."""
    hypotheses = []
    for action, s in stats.items():
        if s["score"] >= 2:
            hypotheses.append(f"HIPÓTESE: `{action}` tem score +{s['score']} — manter padrão.")
        elif s["score"] <= -2:
            parts = action.split("|")
            if len(parts) >= 1:
                mode = parts[0]
                if mode == "semantic":
                    hypotheses.append(
                        f"HIPÓTESE: `{action}` score {s['score']} — testar threshold maior (0.60)."
                    )
                elif mode == "temporal":
                    hypotheses.append(
                        f"HIPÓTESE: `{action}` score {s['score']} — revisar janela temporal."
                    )
    return hypotheses


def main():
    today = date.today().isoformat()
    entries = load_feedback(FEEDBACK_LOG)

    if not entries:
        print("Nenhum feedback para processar.")
        return

    # Archive and clear
    with FEEDBACK_ARCHIVE.open("a") as arch:
        for entry in entries:
            arch.write(json.dumps(entry, ensure_ascii=False) + "\n")
    FEEDBACK_LOG.write_text("")

    stats = compute_scores(entries)
    hypotheses = generate_hypotheses(stats)

    positive = sum(1 for s in stats.values() if s["score"] > 0)
    negative = sum(1 for s in stats.values() if s["score"] < 0)
    print(f"Feedback processado: {positive} positivas, {negative} negativas, {len(entries)} entradas")

    # Extract previous hypotheses for historical record
    prev_hypotheses = []
    if LEARNED_RULES.exists() and "## Hipóteses testadas" in LEARNED_RULES.read_text():
        section = LEARNED_RULES.read_text().split("## Hipóteses testadas")[1]
        for line in section.splitlines():
            if line.strip().startswith("- HIPÓTESE:"):
                prev_hypotheses.append(line.strip()[2:].strip())

    markdown = build_markdown(stats, today, hypotheses)
    LEARNED_RULES.write_text(markdown)
    print(f"Arquivo gerado: {LEARNED_RULES}")

    # Commit
    try:
        subprocess.run(["git", "add", "memory/meetings-tldv-learned-rules.md", "memory/meetings-tldv-feedback-archive.jsonl"],
                       cwd=str(WORKSPACE), check=True, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", f"feat(meetings-tldv): update learned rules ({today})"],
            cwd=str(WORKSPACE), capture_output=True, text=True,
        )
        if result.returncode == 0:
            print("Commit OK")
            push = subprocess.run(["git", "push"], cwd=str(WORKSPACE), capture_output=True, text=True)
            if push.returncode == 0:
                print("Push OK")
            else:
                print(f"Push failed (maybe nothing to push): {push.stderr}")
        else:
            print(f"Commit failed (maybe nothing to commit): {result.stderr}")
    except Exception as e:
        print(f"Git error: {e}")


if __name__ == "__main__":
    main()