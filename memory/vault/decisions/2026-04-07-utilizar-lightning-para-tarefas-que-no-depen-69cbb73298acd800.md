---
entity: Utilizar Lightning para tarefas que não dependam de status (custos, tempo
  de sessão, contexto)
type: decision
confidence: medium
sources:
- source_type: signal_event
  source_ref: migration-derived:2026-04-07-utilizar-lightning-para-tarefas-que-no-depen-69cbb73298acd800.md
  retrieved_at: 2026-04-10 13:00:21+00:00
  mapper_version: signal-ingest-v1
- source_type: tldv_api
  source_ref: https://tldv.io/meeting/69cbb73298acd80013fa20ce
  retrieved_at: 2026-04-10 00:00:00+00:00
  mapper_version: signal-ingest-v1
  note: Status Kaba/BAT/BOT
last_verified: 2026-04-07
verification_log: []
last_touched_by: livy-agent
draft: false
id_canonical: decision:2026-04-07-utilizar-lightning-para-tarefas-que-no-depen-69cbb73298acd800
source_keys: &id001
- https://tldv.io/meeting/69cbb73298acd80013fa20ce
- migration-derived:2026-04-07-utilizar-lightning-para-tarefas-que-no-depen-69cbb73298acd800.md
first_seen_at: '2026-04-10T15:01:20Z'
last_seen_at: '2026-04-10T15:01:20Z'
lineage:
  run_id: domain-elevation-wave-a
  source_keys: *id001
  transformed_at: '2026-04-10T15:01:20Z'
  mapper_version: domain-elevation-v1
  actor: elevate_to_domain_model
---

# Utilizar Lightning para tarefas que não dependam de status (custos, tempo de sessão, contexto)

## Summary
Utilizar Lightning para tarefas que não dependam de status (custos, tempo de sessão, contexto)

## Evidence
- https://tldv.io/meeting/69cbb73298acd80013fa20ce

## Links
- Related entity: [[../entities/bat-conectabot-observability|bat-conectabot-observability]]
