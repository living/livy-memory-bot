#!/usr/bin/env python3
"""
Autoresearch Verify — verification of metric after modification.

Usage:
  python3 autoresearch_verify.py --metric <name>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from autoresearch_metrics import (
    completeness_score, completeness_avg,
    count_crossrefs, count_actions, count_interventions,
    CURATED_DIR,
)

METRIC_MAP = {
    "completeness": completeness_avg,
    "crossrefs": count_crossrefs,
    "actions": count_actions,
    "interventions": count_interventions,
}

def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--metric":
        print("Usage: autoresearch_verify.py --metric <name>", file=sys.stderr)
        sys.exit(1)
    metric = sys.argv[2]
    if metric not in METRIC_MAP:
        print(f"Unknown metric: {metric}", file=sys.stderr)
        sys.exit(1)
    val = METRIC_MAP[metric]()
    print(val)

if __name__ == "__main__":
    main()
