from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "elevate_to_domain_model.py"
    spec = importlib.util.spec_from_file_location("elevate_to_domain_model", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_md(path: Path, frontmatter: str, body: str = "Body\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")


def test_dry_run_reports_changes_without_writing(tmp_path, capsys):
    mod = _load_module()

    vault_root = tmp_path / "memory" / "vault"
    decision = vault_root / "decisions" / "escolha-arquitetura.md"
    original = (
        "type: decision\n"
        "summary: Escolha de arquitetura\n"
        "decision_date: 2026-04-10\n"
        "sources:\n"
        "  - source_type: tldv_api\n"
        "    source_ref: https://tldv.io/meeting/abc\n"
        "    retrieved_at: 2026-04-10T10:00:00Z\n"
        "    mapper_version: signal-ingest-v1"
    )
    _write_md(decision, original)

    rc = mod.main(["--dry-run", "--scope", "all", "--vault-root", str(vault_root)])
    assert rc == 0

    output = capsys.readouterr().out
    assert "would_migrate: 1" in output

    # Dry-run must not modify file content.
    assert decision.read_text(encoding="utf-8") == f"---\n{original}\n---\n\nBody\n"


def test_apply_creates_backup_before_modification(tmp_path):
    mod = _load_module()

    vault_root = tmp_path / "memory" / "vault"
    decision = vault_root / "decisions" / "limpeza-supabase.md"
    _write_md(
        decision,
        "type: decision\n"
        "summary: Limpeza Supabase\n"
        "decision_date: 2026-04-10\n"
        "sources:\n"
        "  - source_type: signal_event\n"
        "    source_ref: event:123\n"
        "    retrieved_at: 2026-04-10T10:00:00Z\n"
        "    mapper_version: signal-ingest-v1",
    )

    rc = mod.main(["--scope", "all", "--vault-root", str(vault_root)])
    assert rc == 0

    backup = vault_root / ".migration-backup" / "decisions" / "limpeza-supabase.md"
    assert backup.exists(), "apply must create backup before write"

    migrated = decision.read_text(encoding="utf-8")
    assert "id_canonical: decision:limpeza-supabase" in migrated
    assert "lineage:" in migrated


def test_second_run_no_changes_when_already_elevated(tmp_path, capsys):
    mod = _load_module()

    vault_root = tmp_path / "memory" / "vault"
    entity = vault_root / "entities" / "tldv-pipeline.md"
    _write_md(
        entity,
        "type: project\n"
        "name: TLDV Pipeline\n"
        "slug: tldv-pipeline\n"
        "sources:\n"
        "  - source_type: tldv_api\n"
        "    source_ref: https://tldv.io/meeting/xyz\n"
        "    retrieved_at: 2026-04-10T10:00:00Z\n"
        "    mapper_version: signal-ingest-v1",
    )

    first_rc = mod.main(["--scope", "all", "--vault-root", str(vault_root)])
    assert first_rc == 0
    after_first = entity.read_text(encoding="utf-8")

    second_rc = mod.main(["--scope", "all", "--vault-root", str(vault_root)])
    assert second_rc == 0
    after_second = entity.read_text(encoding="utf-8")

    output = capsys.readouterr().out
    assert "migrated: 0" in output
    assert after_second == after_first
