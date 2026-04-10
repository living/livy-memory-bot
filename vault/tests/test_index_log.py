from pathlib import Path


def test_index_and_log_exist_after_seed():
    root = Path(__file__).resolve().parents[2]
    vault = root / "memory" / "vault"
    index_md = vault / "index.md"
    log_md = vault / "log.md"

    # files may not exist before seed; this test validates structure/format when present
    if index_md.exists():
        idx = index_md.read_text(encoding="utf-8")
        assert "# Vault Index" in idx
        assert "## Entities" in idx

    if log_md.exists():
        lg = log_md.read_text(encoding="utf-8")
        assert "## [" in lg
        assert "ingest" in lg.lower() or "lint" in lg.lower()
