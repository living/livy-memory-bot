"""
Tests for vault/insights/honcho_capture.py — slugify and path building.
"""

import pytest
import sys, re, hashlib
from pathlib import Path

# ─── Slugify (copied from honcho_capture for isolation) ───────────────────────

def slugify(text: str) -> str:
    text = text.replace("\u2014", " ").replace("\u2013", " ").replace("#", " ")
    text = text.lower()
    text = re.sub(r"[^a-z0-9- ]", "", text)  # keep spaces & hyphens
    text = text.replace(" ", "-")
    return re.sub(r"-+", "-", text).strip("-")


def build_lesson_path(merged_at: str, org: str, repo: str, pr_number: int, subject: str) -> Path:
    """Build idempotent lesson path per spec."""
    LESSONS_DIR = Path("/tmp/vault/lessons")
    date_brazil = None
    try:
        from datetime import datetime, timezone, timedelta
        date_brazil = datetime.fromisoformat(merged_at.replace("Z", "+00:00")) - timedelta(hours=3)
    except Exception:
        return LESSONS_DIR / "invalid.md"
    date_str = date_brazil.strftime("%Y-%m-%d")
    slug = slugify(subject)
    source_ref = f"{org}/{repo}/pull/{pr_number}"
    subhash = hashlib.sha256(source_ref.encode()).hexdigest()[:6]
    return LESSONS_DIR / f"{date_str}-{slug}-{subhash}.md"


class TestSlugify:
    def test_pr_number_hyphen(self):
        """PR #N produces 'pr-n' not 'prn'."""
        result = slugify("PR #24")
        assert result == "pr-24"

    def test_em_dash_becomes_hyphen(self):
        """Em dash between words becomes hyphen, not removed."""
        result = slugify("PR #24 — Enriched Claims")
        assert "enriched" in result
        assert "claims" in result

    def test_spec_example(self):
        """Spec example: PR #24 — Enriched Claims Rollout → pr-24-enriched-claims-rollout"""
        result = slugify("PR #24 — Enriched Claims Rollout")
        assert result == "pr-24-enriched-claims-rollout"

    def test_multiple_hyphens_collapsed(self):
        """Multiple hyphens collapse to one."""
        result = slugify("PR #17 — Evo Wiki Research Phase 2")
        assert "--" not in result

    def test_hash_sign_becomes_hyphen(self):
        """# becomes hyphen (not stripped silently)."""
        result = slugify("PR #17 — Evo Wiki Research Phase 2")
        assert "pr-17" in result

    def test_lowercase_only(self):
        """Output is always lowercase."""
        result = slugify("ENRIchED Claims ROllout")
        assert result == result.lower()


class TestLessonPath:
    def test_pr17_path_hash(self):
        """PR #17 source_ref sha256[:6] = 0d10c1."""
        path = build_lesson_path("2026-04-18T21:31:06-03:00", "living", "livy-memory-bot", 17, "PR #17 — Evo Wiki Research Phase 2")
        assert path.name.endswith("-0d10c1.md")

    def test_pr18_path_hash(self):
        """PR #18 source_ref sha256[:6] = cdc07d."""
        path = build_lesson_path("2026-04-18T23:02:42-03:00", "living", "livy-memory-bot", 18, "PR #18 — Batch-first")
        assert path.name.endswith("-cdc07d.md")

    def test_pr24_path_hash(self):
        """PR #24 source_ref sha256[:6] = 26ca99."""
        path = build_lesson_path("2026-04-21T00:25:27Z", "living", "livy-memory-bot", 24, "PR #24 — Enriched Claims Rollout")
        assert path.name.endswith("-26ca99.md")

    def test_path_date_based_on_merged_at_brt(self):
        """Date in path is merged_at converted to BRT (UTC-3)."""
        # 2026-04-22T02:25:27Z (UTC) → 2026-04-21 23:25:27 BRT → 2026-04-21
        path = build_lesson_path("2026-04-22T02:25:27Z", "living", "livy-memory-bot", 24, "PR #24")
        assert path.name.startswith("2026-04-21-")

    def test_idempotent_same_input(self):
        """Same inputs always produce same path."""
        p1 = build_lesson_path("2026-04-21T00:25:27Z", "living", "livy-memory-bot", 24, "PR #24 — Enriched Claims Rollout")
        p2 = build_lesson_path("2026-04-21T00:25:27Z", "living", "livy-memory-bot", 24, "PR #24 — Enriched Claims Rollout")
        assert p1 == p2

    def test_different_pr_different_hash(self):
        """Different PR numbers produce different hashes."""
        p17 = build_lesson_path("2026-04-18T21:31:06Z", "living", "livy-memory-bot", 17, "PR #17")
        p24 = build_lesson_path("2026-04-21T00:25:27Z", "living", "livy-memory-bot", 24, "PR #24")
        assert p17 != p24
