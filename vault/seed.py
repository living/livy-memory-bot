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


def seed_entities() -> list[tuple[str, str]]:
    entities_dir = VAULT / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)
    created = []

    for source_name, (slug, title, summary) in ENTITY_MAP.items():
        source_path = CURATED / source_name
        if not source_path.exists():
            continue

        out = entities_dir / f"{slug}.md"
        body = _frontmatter(title, source_name) + f"\n# {title}\n\n## Resumo\n{summary}\n\n## Fonte primária\n- [[../curated/{source_name}|{source_name}]]\n"
        out.write_text(body, encoding="utf-8")
        created.append((slug, title))

    return created


def write_index(entries: list[tuple[str, str]]) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    lines = [
        "# Vault Index",
        "",
        f"## Entities ({len(entries)})",
    ]
    for slug, title in sorted(entries, key=lambda t: t[1].lower()):
        lines.append(f"- [[entities/{slug}|{title}]] — seeded from curated · updated: {today}")

    lines.extend([
        "",
        "## Decisions (0)",
        "",
        "## Evidence (0)",
        "",
        "## Lint Reports",
        "- none",
        "",
    ])
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
    VAULT.mkdir(parents=True, exist_ok=True)
    created = seed_entities()
    write_index(created)
    append_log(created)
    print(f"Seed complete: {len(created)} entities")


if __name__ == "__main__":
    main()
