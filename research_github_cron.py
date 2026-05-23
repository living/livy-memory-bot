"""Wrapper to run research_github_cron.py from workspace root."""
import sys
import os
from pathlib import Path

# Add vault to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "vault"))

from crons.research_github_cron import main

if __name__ == "__main__":
    main()
