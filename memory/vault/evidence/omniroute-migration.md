---
entity: OmniRoute Migration
type: evidence
confidence: high
sources:
  - type: curated_topic
    ref: memory/curated/tldv-pipeline-state.md
    retrieved: 2026-04-10
  - type: curated_topic
    ref: memory/curated/openclaw-gateway.md
    retrieved: 2026-04-10
last_verified: 2026-04-10
verification_log:
  - hash: pending-runtime-verification
    source: curated dual-source corroboration
    checked: 2026-04-10T01:40:00Z
last_touched_by: livy-agent
draft: false
---

# OmniRoute Migration

## Claim
A migração de `faster-whisper` para backend API-first via OmniRoute (`groq/whisper`) foi adotada como padrão e tratada como resolução de pressão de memória no VPS.

## Evidências
- `memory/curated/tldv-pipeline-state.md`
- `memory/curated/openclaw-gateway.md`

## Status
- Confidence: **high** (2 fontes curadas corroborando o mesmo evento)
- Próximo passo: validar em runtime via config/status para promover evidência operacional.
