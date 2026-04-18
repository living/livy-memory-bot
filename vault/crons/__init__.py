"""Vault cron entry points."""

from vault.crons.research_tldv_cron import main as run_research_tldv
from vault.crons.research_github_cron import main as run_research_github
from vault.crons.research_consolidation_cron import main as run_research_consolidation

__all__ = [
    "run_research_tldv",
    "run_research_github",
    "run_research_consolidation",
]
