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

    backups = sorted((vault_root / ".migration-backup" / "decisions").glob("limpeza-supabase*.md"))
    assert backups, "apply must create backup before write"

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


def test_invalid_vault_root_returns_non_zero_and_clear_error(tmp_path, capsys):
    mod = _load_module()

    missing = tmp_path / "does-not-exist"
    rc = mod.main(["--scope", "all", "--vault-root", str(missing)])

    assert rc != 0
    err = capsys.readouterr().err.lower()
    assert "vault root" in err
    assert "does not exist" in err


def test_scope_poc_only_processes_curated_poc_files(tmp_path, capsys):
    mod = _load_module()

    vault_root = tmp_path / "memory" / "vault"
    poc_file = vault_root / "decisions" / "decision-1.md"
    non_poc_file = vault_root / "decisions" / "outside-poc.md"

    _write_md(
        poc_file,
        "type: decision\n"
        "summary: POC file\n"
        "sources:\n"
        "  - source_ref: event:poc\n"
        "    retrieved_at: 2026-04-10T10:00:00Z",
    )
    _write_md(
        non_poc_file,
        "type: decision\n"
        "summary: Outside POC\n"
        "sources:\n"
        "  - source_ref: event:outside\n"
        "    retrieved_at: 2026-04-10T10:00:00Z",
    )

    rc = mod.main(["--dry-run", "--scope", "poc", "--vault-root", str(vault_root)])

    assert rc == 0
    output = capsys.readouterr().out
    assert "total_files: 1" in output
    assert "would_migrate: 1" in output


def test_malformed_frontmatter_is_reported_and_batch_continues(tmp_path, capsys):
    mod = _load_module()

    vault_root = tmp_path / "memory" / "vault"
    bad = vault_root / "decisions" / "malformed.md"
    good = vault_root / "decisions" / "ok.md"

    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text(
        "---\n"
        "type: decision\n"
        "sources:\n"
        "  - source_ref: [broken\n"
        "---\n\nBody\n",
        encoding="utf-8",
    )
    _write_md(
        good,
        "type: decision\n"
        "summary: Good\n"
        "sources:\n"
        "  - source_ref: event:ok\n"
        "    retrieved_at: 2026-04-10T10:00:00Z",
    )

    rc = mod.main(["--scope", "all", "--vault-root", str(vault_root)])

    assert rc != 0
    output = capsys.readouterr().out
    assert "errors: 1" in output
    assert "migrated: 1" in output
    assert "id_canonical: decision:ok" in good.read_text(encoding="utf-8")


def test_backup_is_never_overwritten_uses_unique_names(tmp_path):
    mod = _load_module()

    vault_root = tmp_path / "memory" / "vault"
    decision = vault_root / "decisions" / "never-overwrite.md"

    _write_md(
        decision,
        "type: decision\n"
        "summary: First\n"
        "sources:\n"
        "  - source_ref: event:first\n"
        "    retrieved_at: 2026-04-10T10:00:00Z",
    )
    rc1 = mod.main(["--scope", "all", "--vault-root", str(vault_root)])
    assert rc1 == 0

    _write_md(
        decision,
        "type: decision\n"
        "summary: Second\n"
        "sources:\n"
        "  - source_ref: event:second\n"
        "    retrieved_at: 2026-04-10T11:00:00Z",
    )
    rc2 = mod.main(["--scope", "all", "--vault-root", str(vault_root)])
    assert rc2 == 0

    backups = sorted((vault_root / ".migration-backup" / "decisions").glob("never-overwrite*.md*"))
    assert len(backups) >= 2


def test_backup_error_on_one_file_does_not_stop_batch(tmp_path, monkeypatch, capsys):
    mod = _load_module()

    vault_root = tmp_path / "memory" / "vault"
    bad = vault_root / "decisions" / "bad-backup.md"
    good = vault_root / "decisions" / "good-backup.md"

    _write_md(
        bad,
        "type: decision\n"
        "summary: Bad backup\n"
        "sources:\n"
        "  - source_ref: event:bad\n"
        "    retrieved_at: 2026-04-10T10:00:00Z",
    )
    _write_md(
        good,
        "type: decision\n"
        "summary: Good backup\n"
        "sources:\n"
        "  - source_ref: event:good\n"
        "    retrieved_at: 2026-04-10T10:00:00Z",
    )

    real_copy2 = mod.shutil.copy2

    def _copy2(src, dst, *args, **kwargs):
        if Path(src) == bad:
            raise OSError("simulated backup failure")
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(mod.shutil, "copy2", _copy2)

    rc = mod.main(["--scope", "all", "--vault-root", str(vault_root)])

    assert rc != 0
    output = capsys.readouterr().out
    assert "errors: 1" in output
    assert "migrated: 1" in output
    assert "id_canonical: decision:good-backup" in good.read_text(encoding="utf-8")


def test_lineage_source_keys_are_normalized_sorted_unique(tmp_path):
    mod = _load_module()

    frontmatter = {
        "type": "decision",
        "sources": [
            {"source_ref": "event:b", "retrieved_at": "2026-04-10T10:00:00Z"},
            {"source_ref": "event:a", "retrieved_at": "2026-04-10T11:00:00Z"},
        ],
        "lineage": {
            "run_id": "domain-elevation-wave-a",
            "source_keys": ["event:b", "event:a", "event:b"],
            "transformed_at": "2026-04-10T12:00:00Z",
            "mapper_version": "domain-elevation-v1",
            "actor": "elevate_to_domain_model",
        },
    }

    elevated, changed = mod.elevate_frontmatter(frontmatter, tmp_path / "d.md")

    assert changed is True
    assert elevated["lineage"]["source_keys"] == ["event:a", "event:b"]
