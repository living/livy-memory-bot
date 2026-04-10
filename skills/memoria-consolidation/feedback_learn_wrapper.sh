#!/bin/bash
# feedback_learn_wrapper.sh — Wrapper for memory-agent-feedback-learn cron job
# Executes learn_from_feedback.py to process feedback log and generate learned rules

set -euo pipefail

WORKSPACE="/home/lincoln/.openclaw/workspace-livy-memory"
SCRIPT="$WORKSPACE/skills/memoria-consolidation/learn_from_feedback.py"

cd "$WORKSPACE"

echo "=== Feedback Learning Started: $(date -Iseconds) ==="

if [[ ! -f "$SCRIPT" ]]; then
    echo "ERROR: Script not found: $SCRIPT"
    exit 1
fi

python3 "$SCRIPT" 2>&1

echo "=== Feedback Learning Complete: $(date -Iseconds) ==="
echo "FEEDBACK_LEARN_CONCLUIDO"
