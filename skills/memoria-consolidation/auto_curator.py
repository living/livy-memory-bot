#!/usr/bin/env python3
"""
auto_curator.py — Applies candidate changes to topic files when conditions are met.
"""
from datetime import datetime, timezone
from pathlib import Path

from topic_analyzer import CandidateChange


class AutoCurator:
    """
    Evaluates candidate changes and applies them to topic files.
    Conditions for auto-apply:
      - evidence is present
      - change_type is add_decision or deprecate_entry
    """

    def should_apply(self, change: CandidateChange) -> bool:
        """Return True if change should be auto-applied."""
        # Must have evidence for auto-apply
        if not change.evidence:
            return False
        # add_decision and deprecate_entry are auto-applicable
        if change.change_type not in ("add_decision", "deprecate_entry"):
            return False
        return True

    def apply_change(self, topic_path: Path, change: CandidateChange) -> bool:
        """Apply a single candidate change to a topic file. Returns True if applied."""
        if not topic_path.exists():
            return False

        content = topic_path.read_text()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if change.change_type == "add_decision":
            new_content = self._apply_add_decision(content, change, timestamp)
        elif change.change_type == "deprecate_entry":
            new_content = self._apply_deprecate_entry(content, change, timestamp)
        else:
            return False

        topic_path.write_text(new_content)
        return True

    def _apply_add_decision(self, content: str, change: CandidateChange, timestamp: str) -> str:
        """Append a decision entry to the topic file."""
        evidence = f" [{change.evidence}]" if change.evidence else ""
        new_entry = f"- [{timestamp}] {change.description}{evidence} — via {change.signal_source}\n"

        # Find the Decisões section
        if "## Decisões\n(nenhuma)\n" in content:
            content = content.replace(
                "## Decisões\n(nenhuma)\n",
                f"## Decisões\n{new_entry}"
            )
        elif "## Decisões" in content:
            # Append to existing decisions
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("## Decisões"):
                    # Find next non-empty line
                    insert_idx = i + 1
                    while insert_idx < len(lines) and not lines[insert_idx].strip():
                        insert_idx += 1
                    lines.insert(insert_idx, new_entry.rstrip())
                    break
            content = "\n".join(lines)
        else:
            # No decisions section — add at end
            content += f"\n\n## Decisões\n{new_entry}"
        return content

    def _apply_deprecate_entry(self, content: str, change: CandidateChange, timestamp: str) -> str:
        """Mark an entry as deprecated."""
        desc = change.description
        deprecated = f"~~{desc}~~ **[DEPRECADO {timestamp}]** — {change.signal_source}"
        content = content.replace(desc, deprecated)
        return content