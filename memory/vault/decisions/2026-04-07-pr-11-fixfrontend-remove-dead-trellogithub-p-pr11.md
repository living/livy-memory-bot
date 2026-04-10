---
entity: PR
type: decision
confidence: low
sources:
- source_type: signal_event
  source_ref: migration-derived:2026-04-07-pr-11-fixfrontend-remove-dead-trellogithub-p-pr11.md
  retrieved_at: 2026-04-10 13:00:21+00:00
  mapper_version: signal-ingest-v1
- source_type: github_api
  source_ref: https://github.com/living/livy-tldv-jobs/pull/11
  retrieved_at: 2026-04-07 00:00:00+00:00
  mapper_version: signal-ingest-v1
  note: pr_state=closed; merged_at=2026-04-03T01:35:06Z; author=lincolnqjunior
last_verified: 2026-04-07
verification_log: []
last_touched_by: livy-agent
draft: false
id_canonical: decision:2026-04-07-pr-11-fixfrontend-remove-dead-trellogithub-p-pr11
source_keys: &id001
- https://github.com/living/livy-tldv-jobs/pull/11
- migration-derived:2026-04-07-pr-11-fixfrontend-remove-dead-trellogithub-p-pr11.md
first_seen_at: '2026-04-10T15:01:20Z'
last_seen_at: '2026-04-10T15:01:20Z'
lineage:
  run_id: domain-elevation-wave-a
  source_keys: *id001
  transformed_at: '2026-04-10T15:01:20Z'
  mapper_version: domain-elevation-v1
  actor: elevate_to_domain_model
---

# PR #11: fix(frontend): remove dead Trello/Github panels, wire insights_json + transcript merge

## Summary
PR #11: fix(frontend): remove dead Trello/Github panels, wire insights_json + transcript merge

## Evidence
- https://github.com/living/livy-tldv-jobs/pull/11

## Links
- Related entity: [[../entities/tldv-pipeline-state|tldv-pipeline-state]]
