"""Vault cron entry points."""

from vault.crons.research_tldv_cron import main as run_research_tldv
from vault.crons.research_github_cron import main as run_research_github
from vault.crons.research_trello_cron import main as run_research_trello
from vault.crons.research_consolidation_cron import main as run_research_consolidation
from vault.crons.vault_insights_weekly_generate import main as run_insights_weekly

__all__ = [
    "run_research_tldv",
    "run_research_github",
    "run_research_trello",
    "run_research_consolidation",
    "run_insights_weekly",
]
