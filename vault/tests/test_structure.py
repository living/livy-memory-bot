from pathlib import Path


def test_vault_structure_exists():
    root = Path(__file__).resolve().parents[2]
    vault = root / "memory" / "vault"

    required = [
        vault,
        vault / "entities",
        vault / "decisions",
        vault / "concepts",
        vault / "evidence",
        vault / "lint-reports",
        vault / ".cache",
        vault / ".cache" / "fact-check",
        vault / "schema",
    ]

    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f"Missing required paths: {missing}"
