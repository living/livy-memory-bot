"""Tests for RunContext dataclass."""
from vault.ingest.run_context import RunContext, new_run_context


class TestRunContext:
    def test_new_run_context_generates_uuid(self):
        ctx = new_run_context(vault_root="/tmp/vault", dry_run=False)
        assert ctx.run_id is not None
        assert len(ctx.run_id) == 36  # UUID4

    def test_run_context_fields(self):
        ctx = new_run_context(vault_root="/tmp/vault", dry_run=True)
        assert ctx.vault_root == __import__("pathlib").Path("/tmp/vault")
        assert ctx.dry_run is True
        assert ctx.started_at is not None

    def test_run_context_elapsed(self):
        ctx = new_run_context(vault_root="/tmp/vault", dry_run=False)
        assert ctx.elapsed_seconds() >= 0
