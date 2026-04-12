import pytest
from pathlib import Path


def test_load_identity_map():
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    assert im is not None
    assert im.resolve_by_github("lincolnqjunior") == "Lincoln Quinan Junior"


def test_resolve_by_trello_name():
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    assert im.resolve_by_trello_name("esteves") == "Esteves Marques"
    assert im.resolve_by_trello_name("victorliving") == "Victor Neves"


def test_resolve_by_alias_fuzzy():
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    assert im.resolve("Lincoln") == "Lincoln Quinan Junior"
    assert im.resolve("luiz rogerio") == "Luiz Rogério"


def test_resolve_unknown_returns_none():
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    assert im.resolve("unknown_person_xyz") is None


def test_all_canonical_names_resolve():
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    for name in im.all_canonical_names():
        assert im.resolve(name) == name


def test_upsert_person_uses_identity_map(tmp_path):
    """upsert_person should redirect to canonical name via identity map."""
    from vault.ingest.entity_writer import upsert_person

    entity = {
        "id_canonical": "person:tldv:lincoln",
        "display_name": "Lincoln",  # Trello alias → should resolve to "Lincoln Quinan Junior"
        "source_keys": ["trello-member:Lincoln"],
        "confidence": "medium",
    }
    path, written = upsert_person(entity, vault_root=tmp_path)

    text = path.read_text(encoding="utf-8")
    # The entity should have been created with the canonical name
    assert "Lincoln Quinan Junior" in text
