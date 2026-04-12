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
