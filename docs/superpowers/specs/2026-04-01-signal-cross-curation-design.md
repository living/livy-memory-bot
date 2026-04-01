# Signal Cross-Curation — Design

**Versão:** 1.1
**Data:** 2026-04-01
**Status:** Ready for approval

---

## 1. O que estamos construindo

Um sistema de curadoria inteligente que cruza sinais de múltiplas fontes para manter os topic files da memória institucional atualizados e precisos — automaticamente quando fontes concordam, e com flag para o Lincoln quando discordam.

**Problema atual:** O sistema atual treat all changes equally. Tentativas falhadas, evoluções abandonadas, e decisões concretas vivem juntas nos mesmos arquivos sem distinção. Arquivos acumulam ruído e perdem valor.

**Solução:** Hierarquia de sinais + detecção de conflitos + curadoria automática.

---

## 2. Fontes de Sinal

### Hierarquia (do mais ao menos confiável)

| Prioridade | Fonte | O que captura | Peso em conflitos |
|---|---|---|---|
| **1 — Primária** | TLDV / Robert | Direcionamentos, decisões, consensos de reunião | Vence se logs confirmam |
| **2 — Secundária** | Logs | Sucesso/falha concreto de jobs, crons, deploys | Vence sobre Git |
| **3 — Terciária** | Git PRs | Descrições e comentários de PRs merged; estado de PRs abertos | Evidência secundária |
| **4 — Quartenária** | Feedback Lincoln | 👍/👎 do cron de autoresearch | Aprendizado apenas |

**Nota:** TLDV é a fonte de **direção**. Logs são a fonte de **verificação concreta**. Se TLDV diz "vamos fazer X" mas logs mostram "X falhou 3x", há conflito — e logs pesam mais que PRs na evidência.

### O que cada fonte extrai

**TLDV (primária — direção)**
- Fonte: Supabase (`meetings`, `summaries` tables)
- `decisions[]` — decisões tomadas na reunião
- `action_items[]` — tarefas designadas + responsável
- `status_changes[]` — mudanças de status de projetos discutidas
- `consensus_topics[]` — temas com consenso da equipe
- Robert como participante = direcionamento explícito

**Logs (secundária — verificação)**
- `job_name`, `timestamp`, `status` (success/failure/error)
- `error_message` (se failure)
- `duration_seconds`
- Jobs: BAT, Delphos, crons, enrichments

**Git (terciária — evidência)**
- PR: `repo`, `number`, `title`, `description`, `merged_at`, `state`
- PR comments: `author`, `body`, `created_at`
- Commit messages: `sha`, `message`, `files_changed`

**Feedback Lincoln (quartenária — aprendizado)**
- `file`, `action`, `thumbs_up` / `thumbs_down`, `timestamp`
- Feedback textual (callback_data)

---

## 3. Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│  SIGNAL COLLECTORS                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ TLDV API │  │ GitHub   │  │ Job logs │  │Feedack │ │
│  │ (Robert) │  │ PRs     │  │ (BAT,    │  │Lincoln │ │
│  └────┬─────┘  └────┬─────┘  │Delphos)  │  │        │ │
│       │             │        └────┬─────┘  └────┬────┘ │
│       └─────────────┴──────────────┴────────────┘       │
│                           │                             │
│                    ┌──────▼──────┐                     │
│                    │ SIGNAL BUS   │                     │
│                    │ (unified     │                     │
│                    │  events)     │                     │
│                    └──────┬──────┘                     │
│                           │                             │
│         ┌─────────────────┼─────────────────┐         │
│         │                 │                 │         │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  │
│  │ TOPIC FILE  │  │ CONFLICT    │  │ AUTO        │  │
│  │ ANALYZER    │  │ DETECTOR    │  │ CURATOR     │  │
│  │              │  │             │  │             │  │
│  │ • diff with │  │ • signal    │  │ • apply when│  │
│  │   current   │  │   conflict?  │  │   1°+2°     │  │
│  │ • candidate │  │ • escalate  │  │   agree     │  │
│  │   changes   │  │   to queue  │  │ • log       │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│                           │                             │
│                    ┌──────▼──────┐                     │
│                    │ CONFLICT    │                     │
│                    │ QUEUE       │                     │
│                    │ (Lincoln    │                     │
│                    │  reviews)   │                     │
│                    └─────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Signal Bus — Eventos Normalizados

Cada collector emite eventos normalizados para o signal bus:

```python
SignalEvent = {
    "source": "tldv" | "logs" | "github" | "feedback",
    "priority": 1 | 2 | 3 | 4,          # 1 = mais confiavel
    "timestamp": ISO8601,
    "topic_ref": str | None,             # qual topic file refere
    "signal_type": "decision" | "status_change" | "action_item" | "success" | "failure" | "correction",
    "payload": {
        "description": str,
        "evidence": str | None,           # link, log excerpt, etc
        "confidence": float,              # 0-1
    },
    "origin_id": str,                    # meeting_id, pr_number, job_name, etc
}
```

**Topic reference:** o sistema infere qual topic file um sinal refere via:
1. Matching de projeto/assunto no título ou description
2. Menção explícita em comments ou decisions
3. Contexto da reunião (participant = Robert → direcionamentos)

---

## 5. Conflito — Quando Occorre

Um **conflito** existe quando:

```
Sinal primário (TLDV/Robert) diz "X é o caminho"
MAS
Sinal secundário (logs) ou terciário (Git) diz "X falhou, foi revertido, ou nunca saiu do papel"
```

**Ordem de peso na evidência:** `logs > Git PRs > TLDV`

**Exemplos de conflito:**
- Reunião decidiu usar arquitetura X → mas logs mostram que jobs X falharam 3x esta semana
- Decisão de migrar para Y → mas PR merged mostra que Y foi revertido
- Ação designada para "responsável Z" → mas Z fechou PR sem implementar e logs confirmam

**Não é conflito (apenas diferença):**
- Opiniões diferentes sem evidência concreta
- Tendências ainda não materializadas em código/logs
- Correções de feedback (isso é aprendizado, não conflito)

---

## 6. Fluxo de Auto-Curação

### Condições para auto-update (todas devem ser verdadeiras)

1. **Sinais convergentes:** 2+ fontes de prioridade 1 ou 2 concordam na mesma direção
2. **Sem conflito:** nenhuma fonte de prioridade 3 ou 4 contradiz
3. **Evidência concreta:** pelo menos uma fonte tem `evidence` (link, log, PR)
4. **Confiança > 0.7**

### O que o Auto-Curator faz

Para cada Topic File candidato a update:

1. **Lê o estado atual** do topic file
2. **Gera candidate changes:**
   - `add_entry`: novo item (decision, action_item, status)
   - `update_entry`: muda status de existente
   - `deprecate_entry`: marca como abandonado/evoluido
   - `archive_entry`: move para .archive com nota de evolução
3. **Aplica mudanças** (se todas condições acima)
4. **Log:** registra no `curation-log.md` o que mudou, por quê, e qual fonte justificou

### Log de curadoria (`memory/curation-log.md`)

```markdown
## 2026-04-01 09:15 BRT

**topic:** forge-platform.md
**auto:** Yes
**signal:** tldv (Robert, 2026-04-01 daily) + github (PR #47 merged)

### Mudanças
- ADD decision: "Forge usa Postgres com Neon (não Mongo)" — evidência: tldv meeting #123 + PR #47

**topic:** delphos-video-vistoria.md
**auto:** No (CONFLICT)
**signal:** tldv diz "migrar para Vonage" + logs mostram "Vonage job falhando há 3 dias"

### Conflito flaggado
- [ ] Lincoln: review needed — reconciliar direção vs evidência
```

---

## 7. Fluxo de Conflito

### Quando um conflito é detectado

1. Signal Analyzer detecta divergência entre fontes
2. Conflict Detector classifica como `conflict` e cria entrada no **Conflict Queue**
3. Lincoln recebe notificação (Telegram ou no resumo do cron) com:
   - Resumo do conflito
   - Sinais em confronto
   - Evidências de cada lado
   - Proposta de resolução (baseada no sinal de maior prioridade)

### Conflict Queue (arquivo)

```markdown
# Conflict Queue — 2026-04-01

## CONFLITO-001 · forge-platform.md
**Detectado:** 2026-04-01 09:00 BRT
**Sinal primário:** tldv — Robert disse "vamos usar Postgres"
**Sinal conflitante:** logs — bat-postgres job falhou 3x esta semana
**Evidências:**
  - tldv: reunião 2026-04-01 #1234
  - logs: job=bat-postgres, failures=[2026-03-29, 2026-03-31, 2026-04-01]
**Proposta:** Manter Postgres como direção, mas investigar falhas antes de fechar topic
**Status:** AWAITING_REVIEW
**Resolução Lincoln:** ___________________________
```

### Como Lincoln resolve

- **Aceita proposta:** sistema aplica a resolução automaticamente
- **Corrige:** Lincoln edita o topic file diretamente com a resolução correta
- **Rejeita:** marca como "não é conflito, contexto diferente" → sistema aprende

---

## 8. Componentes a Implementar

### 8.1 Signal Collectors (novo)

| Collector | Source | Method |
|---|---|---|
| `tldv_collector.py` | Supabase | Fetch meetings with Robert since last run — read from `meetings` + `summaries` tables |
| `logs_collector.py` | Job logs | Parse success/failure from BAT, Delphos, crons log files |
| `github_collector.py` | GitHub API | Fetch merged PRs since last run, parse descriptions + comments |
| `feedback_collector.py` | Existing | Reuse `feedback-log.jsonl` + learned-rules |

### 8.2 Signal Bus (novo)

`signal_bus.py` — unified event queue, in-memory with persistence to `signal_events.jsonl`

### 8.3 Topic File Analyzer (novo)

`topic_analyzer.py` — given a topic file + new signals, compute candidate changes

### 8.4 Conflict Detector (novo)

`conflict_detector.py` — given new signals + current topic state, detect conflicts

### 8.5 Auto-Curator (novo)

`auto_curator.py` — apply candidate changes when conditions met

### 8.6 Conflict Queue Manager (novo)

`conflict_queue.py` — CRUD for conflicts, format for Lincoln review

### 8.7 Cron principal (substitui/adapta `autoresearch_cron.py`)

`curation_cron.py` — orchestrates: collect → analyze → detect conflicts → auto-curate → report

---

## 9. Prioridade de Implementação

### Fase 1 — Foundation (imediatamente útil)
1. `tldv_collector.py` — extrai decisions + action_items de reuniões com Robert (Supabase)
2. `signal_bus.py` — events normalizados com topic_ref
3. `topic_analyzer.py` + `auto_curator.py` — aplica quando sinais de prioridade 1 convergem
4. `curation_cron.py` — orquestração com output Telegram (sempre mostra o que auto-curou)

### Fase 2 — Riqueza
5. `logs_collector.py` — sucesso/falha de jobs (BAT, Delphos, crons)
6. `conflict_detector.py` — detecta conflitos antes de auto-curar (logs > Git na evidência)
7. Conflict Queue — notifica Lincoln de forma acionável

### Fase 3 — Completude
8. `github_collector.py` — PRs merged como evidência terciária
9. `feedback_collector.py` — integra com learned-rules existente
10. Aprendizado: sistema aprende de resoluções do Lincoln para refinar detecção

---

## 10. Integração com Sistema Atual

O sistema **não substitui** o `autoresearch_cron.py` existente — ele cresce ao lado:

- `autoresearch_cron.py` continua rodando (métricas, enriquecimento, feedback buttons)
- `curation_cron.py` roda em paralelo (curadoria inteligente por sinais)
- Ambos escrevem no `consolidation-log.md` e `curation-log.md`
- `learned-rules.md` é consumido por ambos

### Arquivos novos gerados

```
memory/
├── curation-log.md           # log de curadorias aplicadas
├── signal-events.jsonl       # eventos normalizados (signal bus)
├── conflict-queue.md         # fila de conflitos pendentes
├── signals/
│   ├── tldv/
│   ├── github/
│   └── logs/
```

---

## 11. Métricas de Sucesso

| Métrica | Como mede |
|---|---|
| Sinais cruzados | N° de topic files atualizados com evidência de 2+ fontes vs 1 fonte |
| Conflitos resolvidos | % de conflitos com resolução do Lincoln em < 24h |
| Falsos positivos | N° de auto-curations que Lincoln rejeitou |
| Ruído reduzido | Tamanho dos topic files antes vs depois (deve diminuir) |
| Decisões obsoletas | N° de entries marcadas como deprecated/archived por mês |

---

## 12. Risco: Lincoln fica sobrecarregado de conflicts

**Mitigação:** Com logs em prioridade 2 (acima de Git), TLDV e logs vão conflitar mais do que TLDV e Git. Isso é intencional — conflitar é o trabalho. A frequência de conflitos é um **sinal de processo**, não um bug:

- Conflitos frequentes = reuniões definem direções sem visão de execução real
- Conflitos raros = sistema está funcionando como filtro de ruído

Se conflicts > 5/semana, considerar filtrar por tipo de topic (só conflitar em topics de projeto ativo).

---

## 13. Self-Correction do Sistema

O sistema aprende com as resoluções do Lincoln:

```python
# Quando Lincoln resolve um conflito
resolution = {
    "conflict_id": "CONFLITO-001",
    "resolution": "accepted_proposal" | "corrected" | "rejected",
    "lincoln_note": str | None,
    "timestamp": ISO8601,
}

# O sistema registra: qual fonte estava certa?
# → atualiza weight de fontes para esse tipo de topic
# → se Lincoln frequentemente corrige sinais primários, talvez Robert esteja desconectado da execução
```
