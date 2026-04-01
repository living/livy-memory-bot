# Signal Cross-Curation — Design

**Versão:** 1.0
**Data:** 2026-04-01
**Status:** Draft

---

## 1. O que estamos construindo

Um sistema de curadoria inteligente que cruza sinais de múltiplas fontes para manter os topic files da memória institucional atualizados e precisos — automaticamente quando fontes concordam, e com flag para o Lincoln quando discordam.

**Problema atual:** O sistema atual treat all changes equally. Tentativas falhadas, evoluções abandonadas, e decisões concretas vivem juntas nos mesmos arquivos sem distinção. Arquivos acumulam ruído e perdem valor.

**Solução:** Hierarquia de sinais + detecção de conflitos + curadoria automática.

---

## 2. Fontes de Sinal

### Hierarquia (do mais ao menos confiável)

| Prioridade | Fonte | O que captura |
|---|---|---|
| **1 — Primária** | TLDV / Robert | Decisões de reunião, direcionamentos, consensos da equipe |
| **2 — Secundária** | Git PRs | Descrições e comentários de PRs merged; estado de PRs abertos |
| **3 — Terciária** | Logs de execução | Sucesso/falha de jobs (BAT, Delphos, crons) |
| **4 — Quartenária** | Feedback Lincoln | 👍/👎 do cron de autoresearch |

### O que cada fonte extrai

**TLDV (primária)**
- `meeting_id`, `date`, `participants`
- `decisions[]` — decisões tomadas na reunião
- `action_items[]` — tarefas designadas + responsável
- `status_changes[]` — mudanças de status de projetos discutidas
- `consensus_topics[]` — temas com consenso da equipe

**Git (secundária)**
- PR: `repo`, `number`, `title`, `description`, `merged_at`, `state`
- PR comments: `author`, `body`, `created_at`
- Commit messages: `sha`, `message`, `files_changed`

**Logs (terciária)**
- `job_name`, `timestamp`, `status` (success/failure/error)
- `error_message` (se failure)
- `duration_seconds`

**Feedback Lincoln (quartenária)**
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
    "source": "tldv" | "github" | "logs" | "feedback",
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
Sinal secundário (Git) ou terciário (logs) diz "X falhou ou foi abandonado"
```

**Exemplos de conflito:**
- Reunião decidiu usar arquitetura X → mas PR merged mostra que foi revertido
- Decisão de migrar para Y → mas logs mostram que jobs Y estão falhando há semanas
- Ação designada para "responsável Z" → mas Z fechou PR sem implementar

**Não é conflito (apenas diferença):**
- Opiniões diferentes sem evidência concreta
- Tendências ainda não materializadas em código/logs
- Correções de feedback (isso é aprendizaje, não conflito)

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
| `tldv_collector.py` | TLDV API | Fetch meetings with Robert as participant since last run |
| `github_collector.py` | GitHub API | Fetch merged PRs since last run, parse descriptions + comments |
| `logs_collector.py` | Job logs | Parse success/failure from existing log files |
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
1. `tldv_collector.py` — extrai decisions + action_items de reuniões com Robert
2. `signal_bus.py` — events normalizados com topic_ref
3. `topic_analyzer.py` + `auto_curator.py` — aplica quando sinais de prioridade 1 convergem
4. `curation_cron.py` — orquestração com output Telegram (sempre mostra o que auto-curou)

### Fase 2 — Riqueza
5. `github_collector.py` — PRs merged como evidência secundária
6. `conflict_detector.py` — detecta conflitos antes de auto-curar
7. Conflict Queue — notifica Lincoln de forma acionável

### Fase 3 — Completude
8. `logs_collector.py` — sucesso/falha de jobs
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

**Mitigação:** Sinal de prioridade 1 (TLDV) raramente conflita com sinal de prioridade 3 (logs). Conflitos reais são incomuns — só ocorrem quando direção de reunião contradiz evidência concreta. Isso é exatamente o caso que precisa de atenção humana.

Se conflicts forem muito frequentes, é sinal de que:
1. Reuniões estão definindo direções sem visão de execução (problema de processo, não de sistema)
2. Logs não estão capturando corretamente (problema técnico)

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
