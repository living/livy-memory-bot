from pathlib import Path


REQUIRED_TOKENS = [
    "# AGENTS.md — Memory Vault Autônomo",
    "Níveis de Confiança",
    "Context7 Policy",
    "Form\nat\no Frontmatter".replace("\n", ""),
    "Campos obrigatórios",
    "log.md",
    "index.md",
    "nunca escrever fora de `memory/vault/`",
]


def test_agents_md_exists_and_has_required_sections():
    root = Path(__file__).resolve().parents[2]
    agents_md = root / "memory" / "vault" / "schema" / "AGENTS.md"

    assert agents_md.exists(), "AGENTS.md not found"

    content = agents_md.read_text(encoding="utf-8")

    # normalized contains no line breaks for tolerant matching
    normalized = content.replace("\n", " ").lower()

    assert "confidence" in normalized
    assert "context7" in normalized
    assert "frontmatter" in normalized
    assert "memory/vault/" in content

    for token in REQUIRED_TOKENS:
        assert token.lower() in normalized, f"Missing token in AGENTS.md: {token}"
