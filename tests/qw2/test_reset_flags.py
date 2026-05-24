# tests/qw2/test_reset_flags.py
import pytest
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parents[3]))

RESEARCH_DIR = Path(".research/qw2")
CURSOR_FILES = {
    "tldv": RESEARCH_DIR / "last_seen_tldv.json",
    "github": RESEARCH_DIR / "last_seen_github.json",
    "trello": RESEARCH_DIR / "last_seen_trello.json",
}
WRITTEN_REFS = RESEARCH_DIR / "written_refs.json"
WRITE_LOG = RESEARCH_DIR / "write_log.jsonl"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")


def _setup_all():
    """Create all QW-2 research files."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    for p in CURSOR_FILES.values():
        _touch(p)
    _touch(WRITTEN_REFS)
    _touch(WRITE_LOG)


def _teardown():
    for p in CURSOR_FILES.values():
        p.unlink(missing_ok=True)
    WRITTEN_REFS.unlink(missing_ok=True)
    WRITE_LOG.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    _setup_all()
    yield
    _teardown()


def test_reset_clears_all():
    from vault.qw2.run import do_reset
    do_reset({"all"})
    for p in CURSOR_FILES.values():
        assert not p.exists(), f"{p} should not exist"
    assert not WRITTEN_REFS.exists()
    assert not WRITE_LOG.exists()


def test_reset_tldv_clears_only_tldv():
    from vault.qw2.run import do_reset
    do_reset({"tldv", "dedupe"})
    assert not CURSOR_FILES["tldv"].exists()
    assert CURSOR_FILES["github"].exists()
    assert CURSOR_FILES["trello"].exists()
    assert not WRITTEN_REFS.exists()


def test_reset_github_clears_only_github():
    from vault.qw2.run import do_reset
    do_reset({"github", "dedupe"})
    assert CURSOR_FILES["tldv"].exists()
    assert not CURSOR_FILES["github"].exists()
    assert CURSOR_FILES["trello"].exists()
    assert not WRITTEN_REFS.exists()


def test_reset_trello_clears_only_trello():
    from vault.qw2.run import do_reset
    do_reset({"trello", "dedupe"})
    assert CURSOR_FILES["tldv"].exists()
    assert CURSOR_FILES["github"].exists()
    assert not CURSOR_FILES["trello"].exists()
    assert not WRITTEN_REFS.exists()


def test_reset_cursors_keeps_dedupe():
    from vault.qw2.run import do_reset
    do_reset({"tldv", "github", "trello"})
    assert not CURSOR_FILES["tldv"].exists()
    assert not CURSOR_FILES["github"].exists()
    assert not CURSOR_FILES["trello"].exists()
    assert WRITTEN_REFS.exists()
    assert WRITE_LOG.exists()
