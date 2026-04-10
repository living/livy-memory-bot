from pathlib import Path


def test_lint_required_directories_exist():
    root = Path(__file__).resolve().parents[2]
    vault = root / "memory" / "vault"

    assert (vault / "lint-reports").exists()
    assert (vault / "entities").exists()
    assert (vault / "decisions").exists()


def test_lint_report_naming_convention_documented():
    root = Path(__file__).resolve().parents[2]
    agents_md = root / "memory" / "vault" / "schema" / "AGENTS.md"
    text = agents_md.read_text(encoding="utf-8").lower()

    assert "yyyy-mm-dd-lint.md" in text
    assert "contradi" in text  # contradições
    assert "orphan" in text
    assert "stale" in text
