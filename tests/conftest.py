"""conftest.py — add project root to sys.path so vault/ packages resolve."""
import sys
from pathlib import Path

# Ensure the worktree root is on sys.path so 'vault.*' imports resolve.
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
