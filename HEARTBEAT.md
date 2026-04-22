# HEARTBEAT — Livy Memory Agent

_Atualizado: 2026-04-22 00:31 UTC (21:31 BRT)_

## Jobs Ativos — 21 crons

| Job | Schedule (BRT) | Status | Erros Consec. | Nota |
|---|---|---|---|---|
| **enrich-discover** | hourly :00 | ✅ ok | 0 | |
| **enrich-process** | hourly :30 | ✅ ok | 0 | timeout 600s |
| **bat-intraday** | 0,6,12,18h | ✅ ok | 0 | |
| **bat-daily** | 20h | ✅ ok | 0 | |
| **delphos-midday** | 12h | ✅ ok | 0 | |
| **delphos-daily** | 20h | ✅ ok | 0 | |
| **evo-analyze** | 02h | ✅ ok | 0 | |
| **evo-watchdog** | 08h | ✅ ok | 0 | |
| **tldv-archive-videos** | 03h | ✅ ok | 0 | |
| **research-tldv** | intervalo configurável (`RESEARCH_TLDV_INTERVAL_MIN`) | ✅ ok | 0 | lock + rebuild de estado derivado |
| **research-github** | intervalo configurável (`RESEARCH_GITHUB_INTERVAL_MIN`) | ✅ ok | 0 | lock + rebuild de estado derivado |
| **research-trello** | intervalo configurável (`RESEARCH_TRELLO_INTERVAL_MIN`) | ✅ ok | 0 | lock + rebuild de estado derivado |
| **research-consolidation** | 07h | ✅ ok | 0 | substitui loop dream-memory-consolidation |
| **vault-crosslink** | 01h | ✅ ok | 0 | 729 edges, 31 PR authors |
| **vault-ingest** | 10h,14h,20h | ✅ ok | 0 | delivery telegram ativo |
| **vault-lint** | 21h | ✅ ok | 0 | delivery telegram ativo |
| **vault-insights-weekly-validate** | seg 06:30 | ✅ ok | 0 | sintaxe + imports |
| **vault-insights-weekly-generate** | seg 07h | ✅ ok | 0 | geração + envio resumo |
| ~~agenda-trello-0930~~ | 09:30 | ❌ removido | — | job do Victor (neo); removido da memória-agent |
| ~~agenda-trello-1230~~ | 12:30 | ❌ removido | — | job do Victor (neo); removido da memória-agent |
| ~~agenda-trello-1700~~ | 17h | ❌ removido | — | job do Victor (neo); removido da memória-agent |

**Resumo:** 18/21 ok, 3 removidos (Victor/neo)

## Alertas

| Severidade | Alerta | Ação Necessária |
|---|---|---|
| 🟡 | Jobs legados desabilitados (openclaw-health, sonhar, signal-curation, daily-memory-save) | Manter desabilitados ou replanejar com configuração nova |
| 🟢 | Vault insights semanal operacional | Manter monitoramento das segundas 06:30/07:00 |
| 🟢 | Loop de research v1 (TLDV/GitHub/Trello/Consolidation) ativo | Manter observabilidade de lock, rebuild de estado e retry policy |
| ✅ | **Wiki v2 produção — github + trello + tldv** | commits `30a3b29` + `23e6019`; 3 fontes no caminho `fuse()` + SSOT claims + blob |
| ✅ | **agenda-trello-* removidos da memória-agent** | 3 jobs eram do Victor/neo e foram removidos do gateway |
| ✅ | **PR #18 mergeada — batch-first research clients + cadence wiring** | merge `08672fd` squash; 958 inserções; 6 correções de review implementadas; 343 testes research passando |
| ✅ | **PR #17 mergeada — Evo Wiki Research Phase 2** | merge `842852c` squash; 15 commits; 321 testes; 2 bloqueantes corrigidos (namespace event_key + untrack metrics) |
| ✅ | **PR #23 mergeada — Self-Healing Apply V2** | merge `cea58c8` squash; apply_decision v2 + apply_merge_to_ssot + circuit breaker v2 + rollback append-only; 50 testes passando; E2E validado |
| ✅ | **Hotfix `e645c42` — GitHub search cross-repo noise** | `repo:` + `org:` no search vazava PRs de outros repos; filtro defensivo por `repository_url` normalizado; suíte research 476 passing |
| ✅ | **PR #24 mergeada — Enriched Claims Rollout** | merge `fd0f9ac` squash; tasks 1–9 entregues (needs_review/review_reason, semantic keys, quality guardrails); validação: 545 tests/research + 140 tests/vault |

## Qualidade de Claims (Enriched Claims)

| Métrica | Valor atual | Threshold spec | Status |
|---|---:|---:|---:|
| `%decision` | 0.0% | >= 20% (proxy para meta combinada) | 🔴 abaixo |
| `%linkage` | 2.6% | >= 20% (proxy para meta combinada) | 🔴 abaixo |
| `%decision + %linkage` | 2.6% | >= 40% | 🔴 abaixo |
| `%status` | 97.4% | <= 80% (desejado) | 🟡 alto |
| `%with_evidence` | 100.0% | >= 70% | ✅ ok |
| `%needs_review` | 0.0% | <= 35% | ✅ ok |

**Observação:** quality guardrail ativo — emite alerta após **2 ciclos consecutivos** ruins. Heartbeat atual registra **1º ciclo ruim** pós-merge PR #24.

## Mudanças desde Último HEARTBEAT

| Mudança | Impacto |
|---|---|
| ✅ PR #13 mergeada (`bccbef7`) — 6 quick wins de insights | Pipeline de insights incorporado ao master |
| ✅ PR #14 mergeada (`a8f3626`) — envio real Telegram no `envia_resumo.py` | Resumo semanal automatizado com dedupe |
| ✅ PR #15 mergeada (`6ea8005`) — fallback `TELEGRAM_TOKEN` | Compatibilidade com ambiente de produção atual |
| 🆕 Cron `vault-insights-weekly-validate` | Validação preventiva semanal antes da geração |
| 🆕 Cron `vault-insights-weekly-generate` | Geração + envio semanal para `7426291192` |
| ✅ Weekly insights claims-first + fallback por cobertura temporal | Novos módulos `vault/insights/claim_inspector.py` + `renderers.py`; grupo recebe HTML como documento em `-5158607302` |
| 🆕 Crons `research-tldv`, `research-github` e `research-trello` | Polling por fonte com lock distribuído e rebuild de estado derivado |
| 🆕 Cron `research-consolidation` | Consolidação diária 07h BRT substituindo `dream-memory-consolidation` |
| ✅ Smoke test manual dos crons de research | `research-trello` processed=390, `research-github`/`research-tldv` ok, `research-consolidation` sem alertas |
| ✅ **PR #18 mergeada — batch-first research pipeline** | merge `08672fd` squash; github_client two-step (search→pulls), tldv_client cutoff always applied, cadence wired in pipeline, global cadence documented; sanity: 343 tests, smoke OK |
| ✅ **Hotfix `8e1bc76` — gh search GET** | `gh api search/issues` precisa `-X GET` senão usa POST → 404 em todos os repos; 370 tests passing; 11 PRs processados (inclui #19) |
| ✅ **PR #20 mergeada — Wiki v2 Phase 1 Foundation** | merge `a1c0dd3` squash; Memory Core + Fusion Engine + Azure-first capture + dual-key idempotency + ops (shadow/rollback/replay); validação pós-merge: 439 tests research + 90 tests vault |
| ✅ **PR #17 mergeada — Evo Wiki Research Phase 2** | merge `842852c` squash; Trello stream + circuit breaker + self-healing write-mode; 2 bloqueantes corrigidos (namespace event_key + untrack metrics); 321 testes passing |
| ✅ **PR #23 mergeada — Self-Healing Apply V2** | merge `cea58c8` squash; política v2 + lock/idempotência/prune; 50 testes passando |
| ✅ **Hotfix `e645c42` — GitHub search cross-repo noise** | remove `org:living` da query + filtro por `repository_url`; elimina 404 de pull lookup cross-repo |
| ✅ **PR #24 mergeada — Enriched Claims Rollout** | merge `fd0f9ac` squash; tasks 1–9 entregue; validação: 545 tests/research + 140 tests/vault; quality guardrail 1º ciclo ruim registrado |
| ✅ **Sincronização + validação pós-merge PR #24** | master sincronizada, 4 crons smoke OK; coverage decision/linkage baixo no baseline legados |

## Memória

| Camada | Estado |
|---|---|
| Observations (claude-mem) | ✅ worker 37777 ativo |
| Curated (topic files) | ✅ atualizado com PR #24; MEMORY.md + livy-memory-agent.md + HEARTBEAT.md |
| Operational (crons) | ✅ 18/21 jobs ok |

## Incident Playbook

### `research-*` — falha em lock/state/rebuild (novo)

**Sintomas típicos:**
- lock não libera (`Timeout acquiring lock` / lock stale)
- erro ao reconstruir cache derivado em `.research/<source>/state.json`
- divergência entre SSOT `state/identity-graph/state.json` e estado derivado por fonte

**Verificar primeiro:**
```bash
openclaw cron list | grep research-
```

```bash
# Conferir SSOT e caches derivados
ls -la state/identity-graph/state.json .research/tldv/state.json .research/github/state.json .research/trello/state.json
```

**Mitigação imediata:**
1. Garantir que apenas um job por fonte esteja ativo (evitar concorrência manual).
2. Se lock estiver stale, aguardar TTL (600s) ou remover lock stale conforme política do `lock_manager`.
3. Regenerar estado derivado rodando o cron da fonte uma vez em modo controlado.
4. Validar que SSOT permaneceu íntegro em `state/identity-graph/state.json`.

**Root cause provável:** execução concorrente fora da janela esperada, interrupção durante rebuild do cache derivado, ou erro transitório de fonte externa (TLDV/GitHub).

**Critério de recuperação:** próximo run conclui com lock acquire/release, rebuild sem erro e `lastRunStatus=ok`.

---

### `agenda-trello-*` — billing error em neo/anthropic (recorrente)

**Sintoma:** `FallbackSummaryError: All models failed (2): anthropic/claude-sonnet-4-6: Provider anthropic has billing issue`

**Verificar primeiro:**
```bash
gh api graphql -f query='{ marketplacePurchases(first:5) { nodes { plan { name } } } }'
```

**Mitigação imediata:**
1. Listar job IDs: `openclaw cron list | grep agenda-trello`
2. Trocar model de `fastest`/`github-copilot/gpt-5-mini` para provider ativo:
   ```bash
   # Exemplo: trocar model nos 3 jobs
   openclaw cron update <job-id> --model omniroute/fastest
   ```
3. Alternativas testadas em produção: `omniroute/PremiumFirst`, `zai/glm-5.1`

**Root cause provável:** provider anthropic sem créditos/billing ativo na conta neo.

**Resolução definitiva:** reativar billing em claude.ai/admin ou migrar para provider sem billing (omniroute/zai).

**Jobs afetados:**
- `agenda-trello-0930` (id: `24514a66`)
- `agenda-trello-1230` (id: `1a0e180b`)
- `agenda-trello-1700` (id: `23bc1aba`)

---

## Última Consolidação

- Sessão de implementação/documentação: 2026-04-22 00:31 BRT
- Alterações aplicadas: PR #24 merge + sincronização + validação + docs STM/LTM/napkin
- Próxima consolidação: 2026-04-23 07:00 BRT

## Mudanças desde Último HEARTBEAT (2026-04-22 00:31 UTC)

| Mudança | Impacto |
|---|---|
| ✅ **PR #24 mergeada — Enriched Claims Rollout** | merge `fd0f9ac` squash; GitHubRichClient; needs_review/review_reason; semantic dedupe keys; quality guardrails; 545 tests research + 140 tests vault |
| ✅ **Validação pós-merge PR #24** | master sincronizada; 4 crons smoke OK; quality guardrail ativado (1º ciclo ruim esperado — coverage baseline legados) |
| ✅ docs: MEMORY.md + livy-memory-agent.md + HEARTBEAT.md | registrados PR #24 + quality dashboard |
| ✅ docs: consolidation-log atualizado | session log de 2026-04-22 00:31 UTC |
