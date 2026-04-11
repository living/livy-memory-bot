"""
vault/pipeline.py — Memory Vault orchestration (Phase 1C).

Task 6 pipeline integration:
- Domain enrichment wiring (quality hooks)
- Independent source flow processing
- Partial failure tolerance
- Domain metrics emission

Chains: ingest → confidence gate → write → lint → optional repair → domain metrics.
Supports dry-run mode for safe validation.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from vault.fact_check import cached_lookup
from vault.ingest import load_events, deduplicate_events, extract_signal, upsert_decision, upsert_concept
from vault.lint import run_lint, detect_coverage_gaps, detect_orphans
from vault.repair import run_repair
from vault.reverify import run_reverify
from vault.status import build_status_payload, render_markdown
from vault.confidence_gate import gate_decision
from vault.metrics import collect_domain_metrics
from vault.ingest.external_ingest import run_external_ingest

ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = ROOT / "memory" / "vault"
DEFAULT_EVENTS = ROOT / "memory" / "signal-events.jsonl"




def _enforce_confidence_gate(signal: dict) -> dict:
    """Enforce confidence based on source quality (official/corroborated/indirect)."""
    # In current ingest flow, incoming signal is an indirect source by default.
    result = gate_decision([{"type": "signal_event"}])
    enforced = result.get("enforced_confidence", "low")

    mapping = {
        "high": 0.95,
        "medium": 0.8,
        "low": 0.6,
        "unverified": 0.0,
    }
    current = signal.get("confidence", 0.0)
    new_conf = mapping.get(enforced, 0.6)

    if float(current or 0) != float(new_conf):
        return {**signal, "confidence": new_conf, "_gate_override": f"{current}->{enforced}"}
    return signal


def _process_single_event(
    event: dict,
    vault_root: Path,
    verbose: bool = False,
    dry_run: bool = False,
) -> Optional[dict]:
    """Process a single event with error handling.

    Returns dict with result info or None if skipped.
    Raises exceptions for unexpected errors (caller handles).
    """
    try:
        signal = extract_signal(event)
        if not signal:
            return {"status": "skipped", "reason": "no_signal"}

        sig_type = signal.get("signal_type", "")
        cache_key = f"{sig_type}:{signal.get('origin_id', '')}:{signal.get('description', '')}"
        cached = cached_lookup(cache_key)

        if verbose:
            status = "hit" if cached else "miss"
            print(f"  [cache {status}] {sig_type} {signal.get('description', '')[:60]}")

        # Apply confidence gate
        gate_overridden = False
        signal = _enforce_confidence_gate(signal)
        if "_gate_override" in signal:
            gate_overridden = True

        if sig_type == "decision":
            if dry_run:
                return {
                    "status": "success",
                    "type": sig_type,
                    "description": signal.get("description", ""),
                    "gate_override": gate_overridden,
                }
            path = upsert_decision(signal)
            return {"status": "success", "type": sig_type, "path": str(path), "description": signal.get("description", ""), "gate_override": gate_overridden}
        elif sig_type == "topic_mentioned":
            if dry_run:
                return {
                    "status": "success",
                    "type": sig_type,
                    "description": signal.get("description", ""),
                    "gate_override": gate_overridden,
                }
            path = upsert_concept(signal)
            return {"status": "success", "type": sig_type, "path": str(path), "description": signal.get("description", ""), "gate_override": gate_overridden}
        else:
            return {"status": "skipped", "reason": "unknown_type", "type": sig_type}

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__,
            "event_id": event.get("event_id", "unknown"),
        }



def run_signal_pipeline(
    *,
    events_path: Path | str = DEFAULT_EVENTS,
    dry_run: bool = False,
    verbose: bool = False,
    repair: bool = False,
    reverify: bool = False,
    enable_domain_metrics: bool = True,
) -> dict:
    """
    Full vault pipeline: ingest → confidence gate → write → lint → domain metrics → optional repair.

    Task 6 features:
    - Independent source flow processing (partial failure tolerance)
    - Domain quality metrics emission
    - Per-source event tracking

    Returns a summary dict with counts and paths.
    In dry-run mode, no files are written to the vault.
    """
    vault_root = VAULT_ROOT
    if not dry_run:
        vault_root.mkdir(parents=True, exist_ok=True)
        (vault_root / "decisions").mkdir(parents=True, exist_ok=True)
        (vault_root / "concepts").mkdir(parents=True, exist_ok=True)

    events = load_events(events_path)
    deduped = deduplicate_events(events)
    decisions_written: list[Path] = []
    concepts_written: list[Path] = []
    skipped_dry_run: list[str] = []
    gate_overrides = 0
    failed_events = 0
    skipped_events = 0
    source_counts: dict[str, int] = {}

    for event in deduped:
        # Track source distribution
        source = event.get("source", "signal")
        source_counts[source] = source_counts.get(source, 0) + 1

        # Process with error handling for partial failure tolerance
        result = _process_single_event(event, vault_root, verbose=verbose, dry_run=dry_run)

        if result is None:
            skipped_events += 1
            continue

        if result["status"] == "failed":
            failed_events += 1
            if verbose:
                print(f"  [FAIL] {result.get('event_id', '?')}: {result.get('error', 'unknown')}")
            continue

        if result["status"] == "skipped":
            skipped_events += 1
            continue

        # Success cases
        if result.get("gate_override"):
            gate_overrides += 1

        if dry_run:
            sig_type = result.get("type", "unknown")
            if sig_type == "decision":
                skipped_dry_run.append(f"decision: {result.get('description', '')[:80]}")
            elif sig_type == "topic_mentioned":
                skipped_dry_run.append(f"topic: {result.get('description', '')[:80]}")
            continue

        if result.get("type") == "decision":
            if not dry_run:
                decisions_written.append(Path(result.get("path", "")))
        elif result.get("type") == "topic_mentioned":
            if not dry_run:
                concepts_written.append(Path(result.get("path", "")))

    # External ingest stage (meeting + card entities)
    external_ingest_summary = run_external_ingest(
        vault_root=vault_root,
        dry_run=dry_run,
        verbose=verbose,
    )

    lint_report_path = run_lint(vault_root)

    gaps_after_lint = len(detect_coverage_gaps(vault_root))
    orphans_after_lint = len(detect_orphans(vault_root))

    gaps_after_repair = gaps_after_lint
    orphans_after_repair = orphans_after_lint

    if repair and not dry_run:
        repair_result = run_repair(vault_root)
        gaps_after_repair = repair_result["gaps_remaining"]
        orphans_after_repair = repair_result["orphans_remaining"]

    reverify_result: dict = {
        "stale_before_reverify": 0,
        "stale_after_reverify": 0,
        "reverified_pages": [],
        "downgraded_pages": [],
    }
    if reverify:
        reverify_result = run_reverify(vault_root, dry_run=dry_run)

    # Collect domain metrics (Task 6)
    domain_metrics: dict = {}
    if enable_domain_metrics and not dry_run:
        try:
            domain_metrics = collect_domain_metrics(vault_root)
        except Exception as e:
            # Domain metrics failure should not block pipeline
            if verbose:
                print(f"  [WARN] Domain metrics collection failed: {e}")
            domain_metrics = {"error": str(e), "entities_count": 0, "decisions_count": 0, "concepts_count": 0}

    return {
        "dry_run": dry_run,
        "events_total": len(events),
        "events_deduped": len(deduped),
        "decisions_written": len(decisions_written),
        "concepts_written": len(concepts_written),
        "skipped_dry_run": skipped_dry_run,
        "gate_overrides": gate_overrides,
        # Task 6: Failure tracking
        "failed_events": failed_events,
        "skipped_events": skipped_events,
        # Task 6: Source metrics
        "source_counts": source_counts,
        # Domain metrics (Task 6)
        "domain_metrics": domain_metrics,
        # External ingest summary
        "external_ingest": external_ingest_summary,
        # Lint results
        "lint_report": str(lint_report_path),
        "gaps_after_lint": gaps_after_lint,
        "orphans_after_lint": orphans_after_lint,
        "gaps_after_repair": gaps_after_repair,
        "orphans_after_repair": orphans_after_repair,
        # Reverify results
        "stale_before_reverify": reverify_result["stale_before_reverify"],
        "stale_after_reverify": reverify_result["stale_after_reverify"],
        "reverified_pages": reverify_result["reverified_pages"],
        "downgraded_pages": reverify_result["downgraded_pages"],
        "pipeline_at": datetime.now(timezone.utc).isoformat(),
    }


# Deprecated alias — prefer run_signal_pipeline
run_pipeline = run_signal_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Memory Vault Phase 1C Pipeline")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS, help="Path to signal-events.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Validate pipeline without writing any files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-event decisions")
    parser.add_argument("--lint-only", action="store_true", help="Skip ingest, run lint only")
    parser.add_argument("--repair", action="store_true", help="Run auto-repair after lint")
    parser.add_argument("--reverify", action="store_true", help="Run stale-claim re-verification after lint")
    args = parser.parse_args(argv)

    if args.lint_only:
        report = run_lint(VAULT_ROOT)
        print(f"lint report: {report}")
        return 0

    if args.dry_run:
        print("=== DRY RUN — no files will be written ===\n", flush=True)

    summary = run_signal_pipeline(
        events_path=args.events,
        dry_run=args.dry_run,
        verbose=args.verbose,
        repair=args.repair,
        reverify=args.reverify,
    )

    print("\n=== Pipeline Summary ===")
    print(f"  at: {summary['pipeline_at']}")
    print(f"  events loaded: {summary['events_total']}")
    print(f"  events deduped: {summary['events_deduped']}")

    if args.dry_run:
        print("  [DRY RUN] would have written:")
        print(f"    signals: {len(summary['skipped_dry_run'])}")
        print("  first 5 candidates:")
        for s in summary["skipped_dry_run"][:5]:
            print(f"    - {s}")
    else:
        print(f"  decisions written:  {summary['decisions_written']}")
        print(f"  concepts written:   {summary['concepts_written']}")
        print(f"  gate overrides:     {summary['gate_overrides']}")
        print(f"  lint report: {summary['lint_report']}")
        print(f"  gaps/orphans after lint: {summary['gaps_after_lint']}/{summary['orphans_after_lint']}")
        if args.repair:
            print(f"  gaps/orphans after repair: {summary['gaps_after_repair']}/{summary['orphans_after_repair']}")
        if args.reverify:
            print(f"  stale before/after reverify: {summary['stale_before_reverify']}/{summary['stale_after_reverify']}")
            print(f"  reverified pages: {len(summary['reverified_pages'])}")
            print(f"  downgraded pages: {len(summary['downgraded_pages'])}")

        payload = build_status_payload(VAULT_ROOT)
        print("\n--- Vault Status ---")
        print(render_markdown(payload))

    return 0


if __name__ == "__main__":
    sys.exit(main())
