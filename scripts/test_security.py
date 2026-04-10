from pathlib import Path


def validate_vault_path(root: Path, target: Path) -> Path:
    root = root.resolve()
    target = target.resolve()

    if root not in target.parents and target != root:
        raise ValueError("Write outside vault boundary")
    return target


def test_path_traversal_blocked():
    vault_root = Path("/tmp/project/memory/vault")
    evil = Path("/tmp/project/memory/vault/../../../../etc/passwd")

    try:
        validate_vault_path(vault_root, evil)
        assert False, "Expected ValueError"
    except ValueError:
        assert True


def test_absolute_path_outside_blocked():
    vault_root = Path("/tmp/project/memory/vault")
    outside = Path("/tmp/evil.md")

    try:
        validate_vault_path(vault_root, outside)
        assert False, "Expected ValueError"
    except ValueError:
        assert True


def test_in_vault_allowed():
    vault_root = Path("/tmp/project/memory/vault")
    inside = Path("/tmp/project/memory/vault/entities/tldv-pipeline.md")

    result = validate_vault_path(vault_root, inside)
    assert str(result).endswith("tldv-pipeline.md")
