---
name: livy-evo
description: Agente evolutivo da Living Consultoria — 6-phase auto-evolution loop com watchdog, experiments.jsonl, risk tiers e napkin-driven workflow
type: agent
date: 2026-04-01
project: livy-evo
status: ativo
---

# livy-evo — Auto-Evolução da Operação Living

## Repositório

`living/livy-evo-jobs`
- **Path local:** `operacional/livy-evo/`
- **Repo do workspace:** `~/.openclaw/workspace-evo/`
- **Estado:** PRODUÇÃO — desde 2026-03-22 12:56 UTC

## Contexto

Sistema de evolução automática da operação Living. Cada ciclo executa: investigar → planejar → implementar → validar → documentar → promover. Artefatos chamados "napkins" (specs ligeras em markdown).

## Arquitetura do Ciclo de Evolução

```
6 fases: investigar → planejar → implementar → validar → documentar → promover
```

## Risk Tiers

| Tier | Risco | Fluxo |
|---|---|---|
| Tier 1 | Low | Automated |
| ... | ... | ... |
| Tier 6 | High | Requires approval |

## Napkins

Specs ligeras em markdown — documentam decisões técnicas, PRDs, eevoluções. Localização: `operacional/livy-evo/napkins/`

## Artefatos

| Artefato | Descrição |
|---|---|
| `experiments.jsonl` | Log de experimentos com campo `verdict` (approve/reject/pending) |
| `state.json` | Estado do workflow (paused/active) |
| `evolution/pending/{slug}.approved` | Arquivo de aprovação |

## Cron Jobs

| Job | ID | Schedule (BRT) | Status | Model |
|---|---|---|---|---|
| `evo-analyze` | `62465a9d-...` | `0 2 * * *` | ✅ ok | github-copilot/gpt-5-mini |
| `evo-watchdog` | `6bbc9e76-...` | `0 8 * * *` | ✅ ok | minimax-portal/MiniMax-M2.7 |

**Modelo:** `evo-analyze` usa gpt-5-mini (tarefas de script); `evo-watchdog` usa M2.7 (análise mais pesada).

## Watchdog System

Arquitetura de monitoramento automático do workflow de evolução:

- **Lê:** `AGENTS.md`, `PROGRAM.md`, `state.json` de `~/.openclaw/workspace-evo/`
- **Estado:** `state.json` controla se workflow está paused ou active
- **Aprovações:** Experiments pendentes armazenados como slug em `state.json`; arquivo de aprovação em `evolution/pending/{slug}.approved`
- **Expiração:** Aprovações expiram após 24h (timestamp do .md); `consecutive_expired` incrementa; **pausa automática após 3 expirations consecutivas**
- **Notificações:** Enviadas via Telegram para grupo `-5242314072` via `accountId: livy-chat`
- **Log:** Eventos de expiração registrados em `experiments.jsonl`

## Agent Override (claude-mem)

| Agente | userId | Status |
|---|---|---|
| `livy-evo` | `lincoln` | ✅ configurado |

## Cross-references

- [livy-memory-agent.md](livy-memory-agent.md) — ambos são agentes Living com cron jobs
- [forge-platform.md](forge-platform.md) — plataforma pode usar análise evo
- `docs/superpowers/specs/2026-03-22-livy-evo-design.md` — design document

---

## Status

**ativo** — 2026-04-01

- ✅ Em produção desde 2026-03-22
- ✅ Cron jobs executando corretamente
- ✅ Watchdog com pausa automática (3 expirations consecutivas)
- ✅ Napkins documentando specs e decisões

---

## Decisões

### 2026-03-22 — Sistema de Auto-Evolução em Produção

**Decisão:** Colocar o sistema de evolução automática em produção com ciclo de 6 fases.

**MOTIVO:** A operação Living precisa evoluir continuamente sem intervenção manual para cada mudança. O ciclo de 6 fases (investigar → planejar → implementar → validar → documentar → promover) padroniza como mudanças são propostas, avaliadas e implementadas. Tiers de risco garantem que mudanças de alto impacto requieran aprovação explícita.

### 2026-03-22 — Tier-based Risk Classification

**Decisão:** Classificar experiments por tier de risco (1-6), com aprovação obrigatória para tiers mais altos.

**MOTIVO:** Nem toda mudança pode ser automatizada. Tiers permitem que mudanças triviais (Tier 1) sejam implementadas automaticamente enquanto mudanças de alto risco (Tier 6) são revisadas por humanos antes de aplicar. Isso equilibra velocidade e segurança.

### 2026-03-22 — Watchdog com Auto-pause

**Decisão:** Implementar watchdog que pausa automaticamente após 3 expirations consecutivas de aprovação.

**MOTIVO:** Se aprovações expiram repetidamente sem ação, significa que o workflow está parado por algum motivo (equipe ocupada, processo quebrado, etc.). Pausar automaticamente evita que o sistema continue gerando experimentos que ninguém aprova — reduz ruído e desperdício de recursos.

### 2026-03-22 — Napkins como Artefatos de Decisão

**Decisão:** Usar "napkins" (specs ligeras em markdown) como formato de documentação de evoluções.

**MOTIVO:** Specs pesadas criam atrito. Napkins são documentos leves e iterativos que capturam o suficiente para tomar decisões sem o overhead de um processo formal. O formato é consistente com a cultura da Living de simplicidade prática.

### 2026-03-28 — Modelo M2.7 para Watchdog

**Decisão:** Usar `minimax-portal/MiniMax-M2.7` para o watchdog e `github-copilot/gpt-5-mini` para evo-analyze.

**MOTIVO:** Watchdog executa análise mais complexa (ler múltiplos arquivos, avaliar estado, decidir se pausa ou não). gpt-5-mini é suficiente para analyze (tarefas de script). Separar modelos otimiza custo e performance — watchdog precisa de reasoning mais sofisticado.

---

## Pendências

- [ ] Verificar se `memory-agent-feedback` error (mencionado em #1721) foi resolvido
- [ ] Continuar evolução do `livy-evo.md` (arquivo com timeout no último ciclo — obs #1813)
- [ ] Avaliar integração com Forge Platform

---

## Bugs

### Bug histórico — Callback routing quebrado (2026-03-22)

**Sintoma:** `evo-analyze` postava botões via `livy-chat` ( `@livy_chat_bot`), mas callbacks iam para `livy_chat_bot`. `livy-deep` operava via `livingnet_liv_bot` — nunca recebia o callback.

**Root cause:**
```
evo-analyze → postava botões via livy-chat (livy_chat_bot)
Lincoln clica → callback_query vai para livy_chat_bot
livy-deep opera via livingnet_liv_bot → nunca recebe callback
```

**Fix:** Mensagem com botões deve ir direto para Lincoln via `accountId: livy-deep`. Grupo recebe apenas notificação informativa sem botões. Callback volta para `livingnet_liv_bot` → `livy-deep` → skill `evo-callback`.

**Status:** ✅ CORRIGIDO

---

## Regras Aprendidas

- `evo_callback_bot`: botões de callback DEVEM ir pelo mesmo bot que recebe o callback — não misturar accountIds
- `evo_watchdog_pause`: watchdog pausa após 3 expirations consecutivas — não ignorar
- `evo_tier_approval`: tiers altos (5-6) requieren aprovação humana — não automatizar
- `evo_napkin_lightweight`: napkin deve ser leve — se está muito pesado, provavelmente deveria ser um PRD
