---
name: memory-vault-implementation-plan
status: drafted
created: 2026-04-10
design_ref: docs/superpowers/specs/2026-04-10-memory-vault-design.md
---

# Plano de Implementação — Memory Vault Autônomo (Fase 1)

## Escopo aprovado
- Vault paralelo em `memory/vault/` (estilo Obsidian).
- Curated legado permanece intacto na Fase 1.
- Raw imutável: TLDV/Signal/GitHub/Trello.
- Fact-check obrigatório com evidência oficial + confidence score.
- TDD, observabilidade e rastreabilidade end-to-end.

## Quick wins (incluindo plugins Obsidian)
1. Seed inicial de 8 entities a partir de `memory/curated/*.md`.
2. `index.md` e `log.md` auto-gerados.
3. Primeira evidence page (`evidence/omniroute-migration.md`).
4. Setup Obsidian privado (worktree/branch `vault/`).
5. Plugins quick wins para embarcar já:
   - Obsidian Git
   - Dataview
   - Templater
   - Metaedit
   - QuickAdd
   - Admonition
   - Heatmap Calendar
   - Outliner
   - Icon Shortcodes

## Fase 1A — Fundação (Dias 1-5)
- Criar estrutura:
  - `memory/vault/{entities,decisions,concepts,evidence,lint-reports,.cache/fact-check}`
  - `memory/vault/schema/AGENTS.md` (policy de manutenção)
- TDD base:
  - `vault/tests/test_entity_creation.py`
  - `vault/tests/test_fact_check.py`
  - `vault/tests/test_lint.py`
  - `scripts/test_security.py`
- Garantia de boundary:
  - bloquear path traversal e escrita fora de `memory/vault/`.

## Fase 1B — Autonomia (Dias 6-12)
- `vault/seed.py`: gera entities iniciais + `index.md` + `log.md`.
- `vault/fact_check.py`: confidence (high/medium/low/unverified), cache TTL 24h.
- `vault/ingest.py`: processa `memory/signal-events.jsonl` → atualiza entities/decisions.
- `vault/lint.py`: contradições, órfãos, stale claims (>7d), gaps de cobertura.
- `vault/status.py`: métricas operacionais para dashboard.

## Fase 1C — Integração e validação (Dias 13-14)
- Orquestrador: `vault/pipeline.py` (ingest → fact-check → write → lint).
- Dry-run + run real.
- Produzir `lint-reports/YYYY-MM-DD-lint.md`.
- Atualizar `HEARTBEAT.md` com métricas do vault.

## Observabilidade mínima
- `vault_pages_total` por tipo
- `vault_claims_total` por confidence
- `lint_contradictions_found`
- `lint_orphans_found`
- `ingest_claims_added`
- `fact_check_verifications` (hit/miss)
- `fact_check_latency_ms`
- `pipeline_errors`

## Critérios de saída da Fase 1
1. 8+ entity pages com evidência oficial.
2. 0 contradições no lint do seed.
3. `index.md` e `log.md` auto-atualizando.
4. Nenhuma escrita fora de `memory/vault/`.
5. Suite TDD completa passando.
6. Vault abrindo no Obsidian local (privado) com plugins instalados.

## Riscos e mitigação
- Drift factual: bloquear write sem evidência mínima.
- Stale claims high-confidence: re-verify automático em lint.
- Crescimento caótico: detecção de órfãos e gaps + repair.
- Conflito com legado: parallel-run até estabilizar.
- Custo de lookup: cache TTL + budget de verificações por ciclo.

_Last updated: 2026-04-10_
