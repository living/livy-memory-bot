# HEARTBEAT — Livy Memory Agent

_Atualizado: 2026-04-19 16:12 UTC (13:12 BRT)_

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

## Mudanças desde Último HEARTBEAT

| Mudança | Impacto |
|---|---|
| ✅ PR #13 mergeada (`bccbef7`) — 6 quick wins de insights | Pipeline de insights incorporado ao master |
| ✅ PR #14 mergeada (`a8f3626`) — envio real Telegram no `envia_resumo.py` | Resumo semanal automatizado com dedupe |
| ✅ PR #15 mergeada (`6ea8005`) — fallback `TELEGRAM_TOKEN` | Compatibilidade com ambiente de produção atual |
| 🆕 Cron `vault-insights-weekly-validate` | Validação preventiva semanal antes da geração |
| 🆕 Cron `vault-insights-weekly-generate` | Geração + envio semanal para `7426291192` |
| 🆕 Crons `research-tldv`, `research-github` e `research-trello` | Polling por fonte com lock distribuído e rebuild de estado derivado |
| 🆕 Cron `research-consolidation` | Consolidação diária 07h BRT substituindo `dream-memory-consolidation` |
| ✅ Smoke test manual dos crons de research | `research-trello` processed=390, `research-github`/`research-tldv` ok, `research-consolidation` sem alertas |
| ✅ **PR #18 mergeada — batch-first research pipeline** | merge `08672fd` squash; github_client two-step (search→pulls), tldv_client cutoff always applied, cadence wired in pipeline, global cadence documented; sanity: 343 tests, smoke OK |
| ✅ **Hotfix `8e1bc76` — gh search GET** | `gh api search/issues` precisa `-X GET` senão usa POST → 404 em todos os repos; 370 tests passing; 11 PRs processados (inclui #19) |
| ✅ **PR #20 mergeada — Wiki v2 Phase 1 Foundation** | merge `a1c0dd3` squash; Memory Core + Fusion Engine + Azure-first capture + dual-key idempotency + ops (shadow/rollback/replay); validação pós-merge: 439 tests research + 90 tests vault |
| ✅ **PR #17 mergeada — Evo Wiki Research Phase 2** | merge `842852c` squash; Trello stream + circuit breaker + self-healing write-mode; 2 bloqueantes corrigidos (namespace event_key + untrack metrics); 321 testes passing |

## Memória

| Camada | Estado |
|---|---|
| Observations (claude-mem) | ✅ worker 37777 ativo |
| Curated (topic files) | ✅ atualizado com Vault Insights + PRs #13/#14/#15/#17/#18/#19 + hotfix `8e1bc76` |
| Operational (crons) | ✅ 3 novos jobs operacionais adicionados |

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

- Sessão de implementação/documentação: 2026-04-18
- Alterações aplicadas: merge PRs #13, #14, #15 + criação de 3 crons de research (tldv/github/consolidation)
- Próxima consolidação: 2026-04-19 07:00 BRT

## Mudanças desde Último HEARTBEAT (2026-04-19 02:50 UTC)

| Mudança | Impacto |
|---|---|
| ✅ **PR #19 mergeada — GitHub Rich PR Events** | merge `787c10d` squash; GitHubRichClient; enriquecimento no fluxo `pr_merged`; 370 tests research passando |
| ✅ **Bug pre-existente: vault.lint import shadowing** | `vault/lint/` package sombreava `vault/lint.py` module; ImportError corrigido com re-export via importlib em `vault/lint/__init__.py`; commit `3ae6fec` |
| ✅ docs: MEMORY.md + livy-memory-agent.md atualizados | registro de PR #19 e fix |
| ✅ docs: consolidation-log atualizado | session log de 2026-04-19 02:50 UTC |
| 🟡 Test failure em `skills/meetings-tldv/` | pre-existente, não relacionado a PR #19; skill fora do escopo do repo |
| ✅ **WIKI_V2_ENABLED conectado ao ResearchPipeline** | commit `d81eb7e`; flag audita `wiki_v2_active` no `run_started`; TDD 4 testes passando; 443 tests research |
| ✅ **Wiki v2 produção habilitado (3 fontes)** | commits `30a3b29` + `23e6019`; github/trello/tldv no FusionEngine; old path mantido para flag=false |
| ✅ **agenda-trello-* removidos do monitoramento local** | jobs eram do Victor/neo e saíram do HEARTBEAT da memória-agent |
| ✅ **Consolidation backfill seg-sex executado** | `.research/backfill-monfri/state.json` isolado; SSOT produção intocado; 8 eventos Trello dentro da janela |
