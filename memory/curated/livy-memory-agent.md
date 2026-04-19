---
name: livy-memory-agent
description: Agente de memória agêntica da Living Consultoria — mantém contexto institucional de 3 camadas (observations → curated → operational)
type: agent
date: 2026-04-01
project: livy-memory-bot
status: ativo
---

# Livy Memory Agent

## Identidade

- **Bot:** @livy_agentic_memory_bot
- **Grupo Telegram:** `-5158607302`
- **Repo:** `living/livy-memory-bot`
- **Workspace:** `~/.openclaw/workspace-livy-memory/`
- **Timezone:** America/Sao_Paulo (UTC-3)
- **Agent ID real:** `memory-agent` (não `livy-memory` — ver Bug #1781)

## Arquitetura de Memória (3 camadas)

| Camada | Fonte | Path |
|---|---|---|
| 1 — Observations | claude-mem SQLite | `~/.claude-mem/claude-mem.db` |
| 2 — Curated | Topic files | `memory/curated/*.md` |
| 3 — Operational | HEARTBEAT + logs | `HEARTBEAT.md`, `memory/consolidation-log.md` |

## Stack de Memória

| Fonte | Path | Formato |
|---|---|---|
| Observations | `~/.claude-mem/claude-mem.db` | SQLite |
| Topic files | `memory/curated/*.md` | Markdown |
| Índice curado | `MEMORY.md` | Markdown |
| Archive | `memory/.archive/` | Markdown |
| Consolidation log | `memory/consolidation-log.md` | Markdown |

## Scripts de Operação

- `skills/memoria-consolidation/consolidate.py` — Auto Dream adaptado (consolidação)
- `skills/memoria-consolidation/autoresearch_metrics.py` — Métricas de qualidade
- `scripts/autoresearch_cron.py` — Cron de monitoramento (Mente Coletiva)

## Cron Jobs

| Job | Schedule | Descrição |
|---|---|---|
| `dream-memory-consolidation` | 07h BRT daily | Consolidação de stale entries |
| `memory-watchdog` | a cada 4h | Verificação de integridade |
| `autoresearch-hourly` | a cada 1h | Métricas + evolução automática + Mente Coletiva |

## Periodicidade

- Consolidação: 07h BRT (cron `dream-memory-consolidation`)
- Watchdog: a cada 4h (cron `memory-watchdog`)
- HEARTBEAT: a cada 4h
- Autoresearch: a cada 1h (cron `autoresearch-hourly`)

## Repositórios GitHub Associados

- `living/livy-memory-bot` — este workspace
- `living/livy-bat-jobs` — BAT/ConectaBot observability
- `living/livy-delphos-jobs` — Delphos video vistoria
- `living/livy-tldv-jobs` — TLDV pipeline
- `living/livy-forge-platform` — Forge platform

## Credenciais

- Token GitHub: `GITHUB_PERSONAL_ACCESS_TOKEN` em `~/.openclaw/.env`
- claude-mem worker: `127.0.0.1:37777`

## Cross-references

- Infra: [openclaw-gateway.md](openclaw-gateway.md) — gateway que hospeda o agente
- Memória: [claude-mem-observations.md](claude-mem-observations.md) — camada 1 da memória
- Projetos: [forge-platform.md](forge-platform.md), [bat-conectabot-observability.md](bat-conectabot-observability.md), [delphos-video-vistoria.md](delphos-video-vistoria.md), [tldv-pipeline-state.md](tldv-pipeline-state.md)

---

## Crosslink Pipeline (Vault Ingest)

Pipeline de enriquecimento de grafo que conecta PRs a projects e persons via GitHub API.

### Evolução Recente (2026-04-12)

| Item | Detalhe |
|---|---|
| Stage 8 | Corrigido (commit `dd0f7c1`) — dedup edge conflict |
| PR author resolution | `github-login-map.yaml` com 9 mapeamentos (github-login → person source_key) |
| Bot filtering | `dependabot`, `pre-commit-ci`, `renovate[bot]`, `github-actions[bot]`, `allcontributor[bot]` |
| Batch PR cache | 1 API call/repo vs N individual calls |
| Production validation | **31/31 PR authors resolvidos**, 729 edges totais |
| Testes | 4 rounds de review, **70 testes passando** |

### Schema de Identity Resolution

`github-login-map.yaml` é o novo schema para mapear GitHub logins a person entities no vault:

```yaml
# Exemplo de mapeamento
github_logins:
  estevesgs: person:trello:estevesgs
  lucasfsouza: person:trello:lucasfsouza
  # ... 9 total
```

**Commit:** `dd0f7c1` — crosslink resolver stage 8 fix + github-login-map.yaml

### Módulos Principais

| Módulo | Responsabilidade |
|---|---|
| `crosslink_resolver.py` | Resolve PR author → person via github-login-map.yaml |
| `crosslink_builder.py` | Construi edges pr→project e pr→person |
| `entity_writer.py` | Upsert de PR entities com YAML frontmatter |
| `mapping_loader.py` | Carrega schema YAML arbitrário via `get_schema_dir()` |
| `crosslink_dedup.py` | Fuzzy matching conservador para person names |

### Bugs Corrigidos

- **Cache key mismatch** no crosslink resolver (Round 3 review)
- **Duplicate import** de `upsert_pr` em `crosslink_builder.py`
- **Low fuzzy match rate** para github logins vs person names
- **PR details assignment** bug no enrichment pipeline

### Bot Accounts Filtrados

```python
BOT_ACCOUNTS = {
    "dependabot",
    "pre-commit-ci[bot]",
    "renovate[bot]",
    "github-actions[bot]",
    "allcontributor[bot]",
}
```

---

## Evo Wiki Research Pipeline (Fase 1)

Pipeline de pesquisa evolutiva que substitui o loop `dream-memory-consolidation` por um sistema de pesquisa incremental com deduplicação por `event_key` e resolução de identidade cross-source.

### Arquitetura (MVP read-only, Fase 1)

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| event_key builder | `vault/research/event_key.py` | `source:event_type:object_id[:action_id]` |
| state store (SSOT) | `vault/research/state_store.py` | `state/identity-graph/state.json`, retenção 180d |
| lock manager | `vault/research/lock_manager.py` | `flock(2)`, PID/start_ts, TTL 600s |
| retry policy | `vault/research/retry_policy.py` | 429→60-480s, 5xx→30-120s, 401/403→no retry |
| identity resolver | `vault/research/identity_resolver.py` | email exact → username partial → context/LLM |
| source priority | `vault/research/source_priority.py` | github>tldv>trello |
| archive guard | `vault/research/archive_guard.py` | 90d + sem ref ativa + sem conflito pendente |
| pipeline core | `vault/research/pipeline.py` | 11-step: state→poll→ingest→dedupe→context→resolve→hyp→validate→apply→verify→state |
| crons | `vault/crons/research_*_cron.py` | polling por fonte + consolidação diária 07h BRT |

### Crons Registrados (OpenClaw)

| Job ID | Schedule | Script |
|---|---|---|
| `88e37467` | `*/15 * * * *` BRT | `research_tldv_cron.py` |
| `b1b496f8` | `*/10 * * * *` BRT | `research_github_cron.py` |
| `49d1d21e` | `*/20 * * * *` BRT | `research_trello_cron.py` |
| `2664597b` | `0 7 * * *` BRT | `research_consolidation_cron.py` (substitui `dream-memory-consolidation`) |

### Self-Healing MVP

Fase 1 é **read-only**: acumula evidência em `self_healing_evidence.jsonl`, não aplica merges automaticamente. Próxima fase implementa aplicação automática.

### Testes

```bash
PYTHONPATH=. pytest -q tests/research/          # 150 tests
PYTHONPATH=. pytest -q vault/tests/test_identity_resolution.py vault/tests/test_resilience.py --ignore=vault/tests/test_reverify_module.py  # 46 tests
```

**Merge commit:** `e68d9cd` (PR #16)

---

## Status

**ativo** — 2026-04-18

- ✅ Bug #1781 corrigido: agent name era `livy-memory`, deveria ser `memory-agent`
- ✅ Bug #1661 corrigido: accountId `livy-memory-feed` → `memory`; regra channel-per-agent adicionada
- ✅ Feature #1778 integrada: evolução automática via round-robin cursor no autoresearch cron
- ✅ Mente Coletiva (#1727): sistema de consolidação multi-space ativo (memory-agent + Livy Deep)
- ✅ Crosslink pipeline Stage 8 corrigido (dd0f7c1) — 31/31 PR authors, 729 edges, 70 testes
- ✅ github-login-map.yaml: 9 mapeamentos github-login → person source_key
- ✅ Bot filtering: dependabot, pre-commit-ci, renovate, github-actions, allcontributor

---

## Decisões

### 2026-03-31 — Sistema de Memória de 3 Camadas

**Decisão:** Criar agente `@livy_agentic_memory_bot` com memória agêntica de 3 camadas.

**MOTIVO:** Decisões técnicas se perdiam entre sessões. A arquitetura em camadas (claude-mem SQLite → topic files → operational) permite que o agente mantenha contexto institucional persistente e que outros agentes consultem memória sem precisar reler tudo.

**Stack:** claude-mem SQLite (observations) → MEMORY.md + topic files (curated) → HEARTBEAT.md (operational)

### 2026-04-01 — Corrigir agent ID de `livy-memory` para `memory-agent` (Bug #1781)

**Decisão:** Todas as delegações para o workspace de memória devem usar `--agent memory-agent`.

**MOTIVO:** O `openclaw agents list` revelou que o agent ID correto é `memory-agent`, não `livy-memory`. Isso causava falha em todas as chamadas de delegação via `run_memory_evolution()`.发现的触发点: observação #1781.

### 2026-04-01 — accountId `livy-memory-feed` → `memory` (Bug #1661)

**Decisão:** Atualizar accountId de `livy-memory-feed` para `memory` no binding JSON.

**MOTIVO:** O accountId antigo estava desatualizado. Corrigido para permitir que o bot funcione corretamente no Telegram.

### 2026-04-01 — Regra: um bot por agente — não compartilhar bot token entre contas (Bug #1661)

**Decisão:** Cada agente deve ter seu próprio canal/Telegram bot token.

**MOTIVO:** Compartilhar bot token entre contas causa erro "Duplicate Telegram bot token". Arquitetura dedicada evita conflito.

### 2026-04-01 — Evolução automática via round-robin cursor (Feature #1778)

**Decisão:** Integrar `run_memory_evolution()` no `autoresearch_cron.py`, processando até 5 arquivos por ciclo com cursor round-robin persistido em `memory/.evolution_cursor`.

**MOTIVO:** O sistema de curadoria manual não acompanhava o volume de arquivos. A evolução automática com cursor round-robin garante que todos os topic files sejam revisados ciclicamente sem overload — cada ciclo processa 5 arquivos, o cursor avança e no próximo ciclo pega os próximos 5.

**Delegação:** cada arquivo é delegado ao agent `memory-agent` com 3-layer research prompt (built-in search → claude-mem API → curated files).

### 2026-04-01 — Mente Coletiva consolidation (Observation #1727)

**Decisão:** Sistema de monitoramento autoresearch usa consolidacao "Mente Coletiva" — múltiplos spaces (memory-agent + Livy Deep) escaneados por phases: Orientation (lê índices) → Gather Signal (detecta stale/orphaned).

**MOTIVO:** Consolidacao centralizada permite visão cross-agent. Lock via PID file (`/tmp/autoresearch.lock`) previne execução concorrente.

### 2026-04-10 — Vault Phase 2 como extensão balanceada de domínio (meeting+card+person strengthen)

**Decisão:** Executar ampliação do domain model como **Vault Phase 2 balanceada** (não Vault Phase 1+) com quick wins em entidades navegáveis (`meeting`, `card`) e fortalecimento conservador de `person` por sinais de participação.

**MOTIVO:** A Vault Phase 1 já foi entregue/mergeada. A extensão para visão 360° requer ciclo novo com guardrails explícitos para evitar regressão no resolver de identidade e manter compatibilidade com contratos existentes.

### 2026-04-10 — Karpathy LLM Wiki como referência semântica, não fonte factual

**Decisão:** Usar o gist de referência (`https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f`) apenas para orientar estrutura de curadoria contínua (ingest/query/lint, rastreio, manutenção incremental), sem tratá-lo como evidência canônica de conteúdo.

**MOTIVO:** Preservar hierarquia de confiança da memória Living (fontes primárias internas > referências externas). Evita contaminação factual e mantém auditabilidade.

### 2026-04-10 — Source key de card inclui board para evitar colisão

**Decisão:** Padrão de identidade para card: `trello:{board_id}:{card_id}`.

**MOTIVO:** O mesmo `card_id` pode ser ambíguo em integrações multi-board/workspace; incluir `board_id` melhora dedup, rastreio e navegação do grafo.

### 2026-04-10 — Participação em meeting/card fortalece identidade de person (com teto conservador)

**Decisão:** Sinais de participação (`tldv:participant:*`, `trello:assignee:*`) passam a reforçar `source_keys` de person e confiança de forma idempotente e conservadora, mantendo guardrail de auto-merge.

**MOTIVO:** Ganho de cobertura de identidade sem sacrificar segurança: melhora linking entre entidades sem permitir merge agressivo por evidência fraca.

---

## Pendências

- [ ] Criar symlink `~/.claude/skills/meetings-tldv` → workspace skills (próximo passo do Bug #1661)
- [x] Verificar se chat ID `-5158607302` é o grupo desejado para o observation feed SSE — ✅ CONFIRMADO: é o grupo Living Memory Observation
- [ ] Token JWT do TLDV — renovação pendente (impacta pipeline de meetings)

---

## Bugs

### #1781 — agent name errado (`livy-memory` → `memory-agent`) — ✅ CORRIGIDO

**Sintoma:** Todas as delegações via `run_memory_evolution()` falhavam silenciosamente.

**Root cause:** O código usava `--agent livy-memory` mas o agent ID real é `memory-agent`.

**Fix:** Substituir `livy-memory` por `memory-agent` em todas as chamadas de delegação.

### #1661 — accountId desatualizado + regra de canal — ✅ CORRIGIDO

**Sintoma:** Bot não enviava mensagens corretamente.

**Root cause:** accountId `livy-memory-feed` estava obsoleto; compartilhamento de bot token entre agentes causava "Duplicate Telegram bot token".

**Fix:** accountId → `memory`; adicionar regra de channel-per-agent.

---

## Regras Aprendidas

- `add_frontmatter`: +1 (bom trabalho)
- `archive_file`: -1 (não archive ainda)
- `agent_id`: sempre verificar com `openclaw agents list` antes de delegar
- `accountId`: não reutilizar tokens entre contas Telegram

## Notas de Operação

- Topic files nunca expiram — se um projeto está ativo, o topic file permanece
- Decisões técnicas devem ser registradas em `memory/curated/` ao serem tomadas
- HEARTBEAT.md é o dashboard operacional — consultar em cada sessão
- Nunca exponha dados de clientes fora do contexto permitido
