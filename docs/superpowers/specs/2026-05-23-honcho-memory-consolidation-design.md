# Spec — Camada de Sabedoria: Vault Lessons + Honcho

**Data:** 2026-05-23
**Revisão:** 3ª — pós review estruturado
**Autor:** Lincoln + Livy Memory
**Status:** Approved

---

## Contexto

A pipeline actual ingere dados de TLDV, GitHub e Trello → SSOT (state.json com 2221 claims). Decisões técnicas, links entre entities e estado de projectos estão documentados. Mas há uma lacuna:

- **Facts** estão no SSOT (decisões, claims, relationships)
- **Sabedoria** (lições aprendidas, contexto de bugs, rationale de decisões) não existe como camada separada
- Agentes não se "lembram" de padrões — cada sessão é effectively um fresh start
- Não há como perguntar "já vimos este erro antes?" ou "o que aprendemos sobre quality guardrails?"

**Necessidade:** Uma camada de sabedoria derivada das fontes cruas, pesquisável semanticamente, que alimente os agentes (main + memory) e heartbeats com contexto acumulado.

---

## Arquitectura — 4 Camadas (Decidida)

```
┌─────────────────────────────────────────────────────────────┐
│                     AGENTE (main / memory)                   │
│                                                             │
│  honcho_search_conclusions  ←→  honcho_ask                  │
│       (peer reasoning)          (context injection)          │
├─────────────────────────────────────────────────────────────┤
│                        HONCHO                               │
│  Peer model: owner, agent-main, agent-memory-agent         │
│  Reasoning: extrai conclusões, não só armazena              │
│  Self-hosted: http://100.121.74.111:8000 (Tailscale-only) │
├─────────────────────────────────────────────────────────────┤
│                     VAULT (disk)                           │
│  lessons/         ← honcho_capture.py (NOVO)                │
│  claims/          ← research_* (existente)                │
│  decisions/       ← consolidations (existente)             │
├─────────────────────────────────────────────────────────────┤
│                   CLAUDE MEM                               │
│  19,922 obs · 8,610 summaries · 1,838 sessões             │
│  Papel: busca em histórico conversacional (18 anos)        │
│  Mantido como search backup durante maturação do Honcho    │
└─────────────────────────────────────────────────────────────┘

FONTES (ETL existente):
  GitHub ──► research_github ──► vault/claims/
  Trello ──► research_trello  ──► vault/claims/
  TLDV   ──► research_tldv   ──► vault/claims/
              honcho_capture.py (NOVO) ──► lessons/
```

### Pilares da arquitectura (invioláveis)

| Camada | Função | Quem escreve | Storage |
|---|---|---|---|
| **Facts** | Source of truth | `vault/crons/research_*.py` | `vault/claims/`, `vault/decisions/` |
| **Sabedoria** | Lições derivadas | `honcho_capture.py` | `vault/lessons/` |
| **Cache semântica** | Retrieval rápido | `honcho_capture` (lê lessons) | Honcho (peer memory) |
| **Histórico** | Busca em conversa | OpenClaw auto | Claude Mem (SQLite) |

### Decisões arquitecturais (feitas, não abrir)

1. **Claude Mem + Honcho não se mergeiam.** Paradigmas ortogonais.
   - Claude Mem = motor de **busca** sobre histórico (encontra "onde discutimos X")
   - Honcho = motor de **raciocínio** sobre pessoas/projectos/decisões
   - Melhor ter os dois com papéis claros do que forçar integração desnecessária

2. **Honcho é cache, não storage primário.** Se Honcho morrer, lessons continuam no vault.

3. **ObservationFeed mantém.** Não corrompe o modelo de peer.

4. **Claude Mem desligado:** Só após Honcho ter 6 meses de peer memory maduro.

5. **RAW facts não são modificados por conclusions.** Separação estrita.

---

## ⚠️ Risco: SPOF Desktop-Link (QW-X)

**Problema:** Honcho está a correr no desktop Windows, accessed via Tailscale from VPS. Se o desktop dormir ou a ligação Tailscale cair, Honcho fica offline.

**Mitigações:**
- `vault/lessons/` é storage primário — sempre disponível offline
- Heartbeat valida Honcho antes de usar; se offline, usa `honcho-query` em modo disk-only
- Alerta enviado a Lincoln se Honcho offline por >15 min

**Não é blockers:** o sistema funciona sem Honcho (lê do vault). Só perde a cache semântica e o reasoning model.

---

## Arquitectura Detalhada

```
FONTES CRUAS              PIPELINE              STORAGE              RETRIEVAL
─────────────             ────────              ───────              ─────────
GitHub API  ────────►  research_*       ───►  vault/claims/  ───► agents
Trello API      (já existente)              vault/decisions/       via honcho_
TLDV/Supabase                            vault/lessons/      search/ask
                                        (lessons/ = novo)
                    honcho_capture.py
                      │
                      ▼
                  HONCHO (cache)
                  peer: agent-memory-agent
                  peer: agent-main
                  peer: owner (7426291192)
```

**Separação RAW / Sabedoria:**
- RAW facts → `vault/claims/`, `vault/decisions/` — source of truth
- Sabedoria/lições → `vault/lessons/` — reasoning derivado
- Honcho = cache de leitura rápida — lê do vault, não escreve no vault

---

## Princípio Fundamental: Separação RAW / Sabedoria

**RAW (Vault claims/decisions):**
- Source of truth para facts
- Escrito **só** por `vault/crons/research_*.py`
- Schema rigoroso: `Claim`, `Evidence`, `SourceRef`
- Nunca modificado por conclusions ou lições

**Sabedoria (Lessons):**
- Derivada — não é source of truth
- Escrita **só** por `honcho_capture.py`
- Lê fontes cruas (não o SSOT) para permitir reprocessamento por período
- Armazenada em `vault/lessons/` como markdown
- Honcho é cache de leitura rápida — não storage primário

**Regra de ouro:** Facts no Vault. Lições no vault/lessons. Honcho é cache. Se Honcho morrer, lessons continuam no vault.

---

## Estado Actual (2026-05-23)

| Componente | Estado |
|---|---|
| Honcho plugin | ✅ Enabled, self-hosted `http://100.121.74.111:8000` |
| Peers Honcho | ✅ owner, agent-main, agent-memory-agent, 7426291192 |
| honcho_capture.py | ❌ Não existe |
| `vault/lessons/` | ❌ Não existe (Gap 1 — blocker) |
| Cron honcho-lessons-capture | ❌ Não existe (Gap 4) |
| Claude Mem | ✅ 19,922 obs, 8,610 summaries — mantido como backup |
| honcho-query skill | ❌ Não existe (skill vault-query não cobre lessons) |
| SPOF desktop-link | ⚠️ Não documentado — risco activo |

---

## Componentes a Criar

### 1. `vault/insights/honcho_capture.py`

**Responsabilidade:** ETL que lê fontes cruas (não o SSOT), gera lições estruturadas e escreve em `vault/lessons/`.

**Input:** GitHub API (PRs, issues, comments), Trello API (cards, checklists, comments), TLDV/Supabase (transcripts, summaries)

**Output:** Markdown files em `vault/lessons/` com frontmatter.

**Formato de cada lesson:**
```yaml
---
type: lesson
source: github          # github | trello | tldv
source_ref: "living/livy-memory-bot/pull/24"
date: 2026-05-22
subject: "PR #24 — Enriched Claims Rollout"
what_happened: "..."
why_it_matters: "..."
lesson: "..."
tags: [vault, quality-guardrail, enriched-claims]
confidence: HIGH        # HIGH | MEDIUM | LOW
oai_model: fastest     # LLM used to generate
---
```

**Nota:** Campo `processed` removido — idempotência garantida por path do arquivo (date + source_ref = ID único). Se o arquivo já existe, não re-escreve.

**Gatilhos de extracção:**
| Gatilho | Fonte | Tipo de lição |
|---|---|---|
| PR merged com body/decisões | GitHub | Fact + rationale |
| Comment em PR com decisão | GitHub | Decisão tática |
| Card movido / checklist | Trello | Decisão de produto |
| Decisão em transcript TLDV | TLDV | Decisão de reunião |
| Bug fix commit | GitHub | Lição técnica |
| Quality guardrail alert | vault | Detecção de drift |
| Stale recovery | vault | Mudança de threshold |

**Granularidade (regra):**
- 1 PR com múltiplas decisões independentes → **múltiplas lessons** (ex: architecture + naming + rollback = 3 arquivos com tags partilhadas)
- Decisões do mesmo PR sobre o mesmo tema → **1 lesson** (evita ruído)
- 1 decision track de reunión → **1 lesson**

### 2. `vault/lessons/` (storage primário de lições)

**Responsabilidade:** Storage primário de lições (Honcho é cache).

**Estrutura:**
```
memory/vault/lessons/
  2026-05-22-pr24-quality-guardrail.md
  2026-05-22-vault-regex-brackets-fix.md
  2026-05-22-stale-thresholds-per-entity.md
  ...
```

**Idempotência:** path do arquivo = hash de `date + source_ref`. Se arquivo existe, skip.

### 3. Skill `honcho-query` (novo)

**Responsabilidade:** Retrieval de lições. Lê tanto do Honcho (fast path) quanto de `vault/lessons/` (fallback).

**Operações:**
- `honcho_query(query, topK=5)` — busca no Honcho
- Se Honcho offline → lê de `vault/lessons/` via full-text search
- Se Ambas falham → retorna empty com mensagem

**Nota:** Skill `vault-query` não é alterada — cobre entities/concepts/decisions. `honcho-query` é skill separada para lessons.

### 4. Cron `honcho-lessons-capture`

**Responsabilidade:** Extrair lições diariamente às 07h BRT.

```
# Cron: 0 10 * * * (BRT = UTC-3, 07h BRT)
# Session target: isolated (agent memory-agent)
# O agente recebe instrução, não comando shell directo
```

**Payload (correcto):**
```json
{
  "kind": "agentTurn",
  "message": "Execute honcho_capture: run --days 1. Validate dates first (QW-0). Write lessons to vault/lessons/. Report results.",
  "model": "fastest"
}
```

**Argumentos do script:**
- `--days N` — janela de extracção (default: 1 dia)
- `--dry-run` — não escreve, só mostra o que seria gerado
- `--source github|trello|tldv` — fonte específica

---

## Retrieval — Como os Agentes Acedem

### Startup (Main agent + Memory agent)

```python
# No início de cada sessão:
conclusions = honcho_search_conclusions(
    query=session_topic,  # o tema da sessão
    topK=5
)
briefing = honcho_ask(
    "qual o estado actual de {topic}? lições recentes?",
    depth="quick"
)
# Injeta no contexto do agente
```

### Heartbeat (diário 07h BRT)

```python
briefing = honcho_ask(
    "briefing dos projectos activos: "
    "o que mudou, o que precisa atenção, lições da semana?",
    depth="thorough"
)
# Envia DM para Lincoln
# Se Honcho offline: alerta + leitura directa de vault/lessons/
```

### Pergunta directa

Lincoln pode perguntar "o que a gente já decidiu sobre X?" →
`honcho_search_conclusions(query=X)` → lições relacionadas.

### Fallback (Honcho offline)

Agentes usam `honcho-query` skill — lê directamente de `vault/lessons/` se Honcho offline.

---

## Quick Wins (Execução Ordenada)

### QW-0 — Validar datas das lessons de exemplo (5 min) ⚠️ ANTES DE QW-2
Antes de commitar qualquer lesson de exemplo, validar as datas reais dos eventos:
- Stale thresholds: 2026-05-22 ou 2026-05-21? Confirmar no git log e HEARTBEAT
- JWT TLDV renewal: quando foi? Confirmar no commit history
- Cron disappearing: quando foi detectado? Confirmar no HEARTBEAT
- Azure blob pipeline: quando? Confirmar no commit history
- max_tokens bug: quando foi descubierto?

**Não commitar exemplos com datas erradas.**

### QW-1 — Criar folder `vault/lessons/` + template (5 min)
```bash
mkdir -p memory/vault/lessons
# Criar lessons/template.md com frontmatter correcto (sem processed)
```

### QW-2 — Escrever 3-5 lessons manuais (30 min)
Lições de decisões reais ( datas validadas em QW-0):
1. Stale thresholds por entity
2. JWT TLDV renewal via BrowserBox
3. Cron job disappearing → detecção e recovery
4. Azure blob pipeline vs TLDV API split
5. max_tokens=600 bug em insights_json

### QW-3 — Criar `honcho_capture.py` mínimo (2-4h)
Lê GitHub PRs (via `github_client.py` existente), gera lessons, escreve em `vault/lessons/`.
**Modelo:** `fastest` (GPT-5-mini ou equivalente) — lições curtas, não precisa reasoning pesado.

### QW-4 — Criar cron `honcho-lessons-capture` (15 min)
```bash
openclaw cron add \
  --name "honcho-lessons-capture" \
  --schedule "cron 0 10 * * *" \
  --sessionTarget isolated \
  --agentId memory-agent \
  --model fastest \
  --payload.kind agentTurn \
  --payload.message "Execute honcho_capture: run --days 1. Validate dates first (QW-0). Write lessons to vault/lessons/. Report results." \
  --description "Extrai lições de GitHub/Trello/TLDV e escreve em vault/lessons/"
```

### QW-5 — Criar skill `honcho-query` (1-2h)
Skill que lê de Honcho E de vault/lessons/ com fallback.
Inclui validação de disponibilidade Honcho no heartbeat.

### QW-6 — Validar retrieval no Honcho (15 min)
Após QW-2: testar `honcho_search_conclusions` sobre as lessons escritas manualmente.

---

## Decisões de Design (feitas)

| Decisão | Escolha | Rationale |
|---|---|---|
| LLM para extracção | `fastest` (GPT-5-mini) | Lições curtas, não precisa reasoning pesado |
| Granularidade | **Múltiplas se independentes, 1 se mesmo tema** | "Por decisão" é a regra; se PR tem 3 decisões sobre o mesmo tema = 1 lesson |
| Deduplicação | Path = hash(date + source_ref) | Se arquivo existe, skip — idempotência sem campo extra |
| Retenção | lessons nunca expiram | Relevância avaliada no retrieval |
| `processed` flag | **Removido** | Campo sem consumidor; idempotência por path |
| Fallback Honcho→disk | Skill `honcho-query` separada | vault-query não é alterada; nova skill cobre lessons |
| SPOF desktop-link | Documentado + mitigação | Heartbeat valida; vault/lessons/ sempre disponível |

---

## Progressão

1. **Phase 1 (QW-0 + QW-1 + QW-2):** Validar datas + vault/lessons/ criado + 5 lessons manuais
2. **Phase 2 (QW-3 + QW-4):** honcho_capture.py ETL mínimo + cron
3. **Phase 3 (QW-5 + QW-6):** Skill honcho-query + validação retrieval
4. **Phase 4:** Trello + TLDV no ETL
5. **Phase 5:** Integração nos heartbeats + agentes
6. **Phase 6:** Avaliar se Honcho pode substituir Claude Mem como source primária

---

## Checklist de Execução

- [ ] **QW-0:** Validar datas das lessons de exemplo antes de QW-2
- [ ] QW-1: Criar `vault/lessons/` + template (sem `processed`)
- [ ] QW-2: Escrever 3-5 lessons manuais (datas validadas)
- [ ] QW-3: Criar `honcho_capture.py` mínimo
- [ ] QW-4: Criar cron `honcho-lessons-capture` (payload agentTurn correcto)
- [ ] QW-5: Criar skill `honcho-query` com fallback
- [ ] QW-6: Validar retrieval no Honcho
- [ ] Gap 6: Validar schema de decisões existente

---

_Last updated: 2026-05-23_
