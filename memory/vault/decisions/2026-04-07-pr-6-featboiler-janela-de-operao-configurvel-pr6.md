---
entity: PR
type: decision
confidence: low
sources:
- source_type: signal_event
  source_ref: migration-derived:2026-04-07-pr-6-featboiler-janela-de-operao-configurvel-pr6.md
  retrieved_at: 2026-04-10 13:00:21+00:00
  mapper_version: signal-ingest-v1
- source_type: github_api
  source_ref: https://github.com/living/livy-forge-platform/pull/6
  retrieved_at: 2026-04-07 00:00:00+00:00
  mapper_version: signal-ingest-v1
  note: pr_state=closed; merged_at=2026-03-14T00:05:39Z; author=lincolnqjunior
last_verified: 2026-04-07
verification_log: []
last_touched_by: livy-agent
draft: false
id_canonical: decision:2026-04-07-pr-6-featboiler-janela-de-operao-configurvel-pr6
source_keys: &id001
- https://github.com/living/livy-forge-platform/pull/6
- migration-derived:2026-04-07-pr-6-featboiler-janela-de-operao-configurvel-pr6.md
first_seen_at: '2026-04-10T15:01:20Z'
last_seen_at: '2026-04-10T15:01:20Z'
lineage:
  run_id: domain-elevation-wave-a
  source_keys: *id001
  transformed_at: '2026-04-10T15:01:20Z'
  mapper_version: domain-elevation-v1
  actor: elevate_to_domain_model
---

# PR #6: feat(boiler): janela de operação configurável — múltiplas janelas + modo 24h (#5)

## Summary
PR #6: feat(boiler): janela de operação configurável — múltiplas janelas + modo 24h (#5)

## Evidence
- https://github.com/living/livy-forge-platform/pull/6

## Links
- Related entity: [[../entities/forge-platform|forge-platform]]
