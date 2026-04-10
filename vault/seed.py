from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "memory" / "vault"
CURATED = ROOT / "memory" / "curated"

ENTITY_MAP = {
    "forge-platform.md": ("forge-platform", "Forge Platform", "Plataforma Forge em progresso."),
    "bat-conectabot-observability.md": ("bat-conectabot", "BAT ConectaBot", "Observability do ConectaBot (monitoramento)."),
    "delphos-video-vistoria.md": ("delphos-video-vistoria", "Delphos Video Vistoria", "Pipeline de vistoria em vídeo (status OK)."),
    "tldv-pipeline-state.md": ("tldv-pipeline", "TLDV Pipeline", "Pipeline TLDV ativo com bugs conhecidos."),
    "projeto-super-memoria-robert.md": ("super-memoria-corporativa", "Super Memória Corporativa", "Proposta de expansão de memória institucional."),
    "livy-evo.md": ("livy-evo", "livy-evo", "Ciclo evolutivo conforme cronograma."),
    "openclaw-gateway.md": ("openclaw-gateway", "OpenClaw Gateway", "Configuração e operação do gateway."),
    "livy-memory-agent.md": ("livy-memory-agent", "Livy Memory Agent", "Agente de memória agêntica da Living."),
}

REQUIRED_DIRS = [
    "entities",
    "decisions",
    "concepts",
    "evidence",
    "lint-reports",
    ".cache/fact-check",
    "schema",
]


def _frontmatter(title: str, source_file: str) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    return f"""---
entity: {title}
type: entity
confidence: medium
sources:
  - type: curated_topic
    ref: memory/curated/{source_file}
    retrieved: {today}
last_verified: {today}
verification_log: []
last_touched_by: livy-agent
draft: false
---
"""


def ensure_structure() -> None:
    VAULT.mkdir(parents=True, exist_ok=True)
    for rel in REQUIRED_DIRS:
        (VAULT / rel).mkdir(parents=True, exist_ok=True)


def seed_entities() -> list[tuple[str, str]]:
    entities_dir = VAULT / "entities"
    entries: list[tuple[str, str]] = []

    for source_name, (slug, title, summary) in ENTITY_MAP.items():
        source_path = CURATED / source_name
        if not source_path.exists():
            continue

        out = entities_dir / f"{slug}.md"
        if not out.exists():
            body = _frontmatter(title, source_name) + (
                f"\n# {title}\n\n## Resumo\n{summary}\n\n"
                f"## Fonte primária\n- [[memory/curated/{source_name}|{source_name}]]\n"
            )
            out.write_text(body, encoding="utf-8")

        entries.append((slug, title))

    return entries


def _count_md_files(path: Path) -> int:
    return sum(1 for p in path.glob("*.md") if p.name != ".gitkeep")


def write_index(entries: list[tuple[str, str]]) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    decisions_count = _count_md_files(VAULT / "decisions")
    evidence_count = _count_md_files(VAULT / "evidence")
    lint_reports = sorted((VAULT / "lint-reports").glob("*.md"), reverse=True)

    lines = [
        "# Vault Index",
        "",
        f"## Entities ({len(entries)})",
    ]
    for slug, title in sorted(entries, key=lambda t: t[1].lower()):
        lines.append(f"- [[entities/{slug}|{title}]] — seeded from curated · updated: {today}")

    lines.extend([
        "",
        f"## Decisions ({decisions_count})",
        "",
        f"## Evidence ({evidence_count})",
        "",
        "## Lint Reports",
    ])

    if lint_reports:
        for report in lint_reports[:5]:
            lines.append(f"- [[lint-reports/{report.stem}|{report.name}]]")
    else:
        lines.append("- none")

    lines.append("")
    (VAULT / "index.md").write_text("\n".join(lines), encoding="utf-8")


def append_log(entries: list[tuple[str, str]]) -> None:
    log = VAULT / "log.md"
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d")
    text = [
        f"## [{stamp}] ingest | seed entities from curated",
        f"  entities_seeded: {len(entries)}",
        "  confidence_default: medium",
        "  notes: initial bootstrap",
        "",
    ]
    mode = "a" if log.exists() else "w"
    with log.open(mode, encoding="utf-8") as f:
        f.write("\n".join(text))


def main() -> None:
    ensure_structure()
    created = seed_entities()
    write_index(created)
    append_log(created)
    print(f"Seed complete: {len(created)} entities")


if __name__ == "__main__":
    main()
