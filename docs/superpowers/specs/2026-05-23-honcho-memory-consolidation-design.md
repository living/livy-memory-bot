# Spec — Camada de Sabedoria: Vault Lessons + Honcho

**Data:** 2026-05-23
**Revisão:** 4ª — pós segundo review estruturado
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
│  honcho_search_conclusions  ←→  honcho_ask                   │
│       (peer reasoning)         (context injection)           │
├─────────────────────────────────────────────────────────────┤
│                        HONCHO                               │
│  Peer model: owner, agent-main, agent-memory-agent         │
│  Reasoning: extrai conclusões, não só armazena              │
│  Self-hosted: http://100.121.74.111:8000 (Tailscale-only) │
│  Peer refresh: tipicamente < 5 min após nova lesson[^1]        │
├─────────────────────────────────────────────────────────────┤
│                     VAULT (disk)                           │
│  memory/vault/lessons/    ← honcho_capture.py (NOVO)       │
│  memory/vault/claims/     ← research_* (existente)        │
│  memory/vault/decisions/  ← consolidations (existente)     │
├─────────────────────────────────────────────────────────────┤
│                   CLAUDE MEM                               │
│  19,922 obs · 8,610 summaries · 1,838 sessões            │
│  Papel: busca em histórico conversacional (18 anos)         │
│  Mantido como search backup durante maturação do Honcho     │
└─────────────────────────────────────────────────────────────┘

FONTES (ETL existente):
  GitHub ──► research_github ──► memory/vault/claims/
  Trello ──► research_trello  ──► memory/vault/claims/
  TLDV   ──► research_tldv   ──► memory/vault/claims/
              honcho_capture.py (NOVO) ──► memory/vault/lessons/
```

**Path canonical:** Todos os paths do vault são relativos a `memory/vault/`. A arquitectura e diagramas usam `memory/vault/lessons/` — este é o path correcto.

### Pilares da arquitectura (invioláveis)

| Camada | Função | Quem escreve | Storage |
|---|---|---|---|
| **Facts** | Source of truth | `vault/crons/research_*.py` | `memory/vault/claims/`, `memory/vault/decisions/` |
| **Sabedoria** | Lições derivadas | `honcho_capture.py` | `memory/vault/lessons/` |
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

## ⚠️ Risco: SPOF Desktop-Link

**Problema:** Honcho está a correr no desktop Windows, accessed via Tailscale from VPS. Se o desktop dormir ou a ligação Tailscale cair, Honcho fica offline.

**Mitigações:**
- `memory/vault/lessons/` é storage primário — sempre disponível offline
- `honcho_health_check()` valida Honcho antes de usar; se offline, usa fallback disk
- Alerta enviado a Lincoln se Honcho offline por > 15 min

**Não é blocker:** o sistema funciona sem Honcho (lê do vault). Só perde a cache semântica e o reasoning model.

---

## Arquitectura Detalhada

```
FONTES CRUAS              PIPELINE              STORAGE              RETRIEVAL
─────────────             ────────              ───────              ─────────
GitHub API  ────────►  research_*       ───►  vault/claims/ ───► agents
Trello API      (já existente)               vault/decisions/        via honcho_
TLDV/Supabase                            memory/vault/lessons/ search_conclusions
                                         (lessons/ = novo)    ou honcho-query skill
                    honcho_capture.py
                      │
                      ▼
                  HONCHO (cache)
                  peer: agent-memory-agent
                  peer: agent-main
                  peer: owner (7426291192)
```

**Separação RAW / Sabedoria:**
- RAW facts → `memory/vault/claims/`, `memory/vault/decisions/` — source of truth
- Sabedoria/lições → `memory/vault/lessons/` — reasoning derivado
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
- Armazenada em `memory/vault/lessons/` como markdown
- Honcho é cache de leitura rápida — não storage primário

**Regra de ouro:** Facts no Vault. Lições em `memory/vault/lessons/`. Honcho é cache. Se Honcho morrer, lessons continuam no vault.

---

## Estado Actual (2026-05-23)

| Componente | Estado |
|---|---|
| Honcho plugin | ✅ Enabled, self-hosted `http://100.121.74.111:8000` |
| Peers Honcho | ✅ owner, agent-main, agent-memory-agent, 7426291192 |
| honcho_capture.py | ❌ Não existe |
| `memory/vault/lessons/` | ❌ Não existe (Gap 1 — blocker) |
| Cron honcho-lessons-capture | ❌ Não existe (Gap 4) |
| Claude Mem | ✅ 19,922 obs, 8,610 summaries — mantido como backup |
| Skill honcho-query | ❌ Não existe |
| SPOF desktop-link | ⚠️ Documentado com mitigação |

---

## Componentes a Criar

### 1. `vault/insights/honcho_capture.py`

**Responsabilidade:** ETL que lê fontes cruas (não o SSOT), gera lições estruturadas e escreve em `memory/vault/lessons/`.

**Input:** GitHub API (PRs, issues, comments), Trello API (cards, checklists, comments), TLDV/Supabase (transcripts, summaries)

**Output:** Markdown files em `memory/vault/lessons/`.

**Path de cada lesson (idempotência por path):**
```
memory/vault/lessons/YYYY-MM-DD-{slugify(subject)}-{sha256(source_ref)[:6]}.md
```
Path completo: `memory/vault/lessons/2026-05-22-pr24-enriched-claims-rollout-a3f2c1.md`

**Regra:** Se arquivo já existe, skip (idempotência garantida pelo path único).

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
- 1 decision track de reunião → **1 lesson**

**Output do run (JSON summary):**
```json
{"lessons_written": 3, "sources": {"github": 2, "trello": 1}, "skipped": 0, "errors": []}
```
Impresso no stdout no final do run. Usado pelo cron para reportar.

---

### 2. `memory/vault/lessons/` (storage primário de lições)

**Responsabilidade:** Storage primário de lições (Honcho é cache).

**Estrutura:**
```
memory/vault/lessons/
  2026-05-22-pr24-enriched-claims-rollout-a3f2c1.md
  2026-05-22-stale-thresholds-per-entity-9d3e1b.md
  2026-05-22-vault-regex-brackets-fix-c4f8a2.md
  ...
```

**Idempotência:** path do arquivo = `date + slugify(subject) + sha256(source_ref)[:6]`. Se arquivo existe, skip.

---

### 3. Skill `honcho-query` (novo)

**Responsabilidade:** Retrieval de lições com fallback disk.

**Interface:**

```python
# honcho_query(query: str, topK: int = 5) -> List[Lesson]
#   Busca no Honcho (fast path). Se Honcho offline ou vazio,
#   fáilleback para full-text search em memory/vault/lessons/.
#   Retorna lista de lessons com score de relevância.
#
# honcho_health_check() -> bool
#   Verifica se Honcho está disponível. Usado pelo heartbeat
#   antes de invocar honcho_query. Retorna True se Honcho
#   responded within 3s, False caso contrário.
```

**Comportamento de `honcho_query`:**
1. Tenta `honcho_search_conclusions(query, topK)` — fast path
2. Se Honcho offline ou retornou < topK results:
   - Faz full-text search em `memory/vault/lessons/*.md`
   - Usa regex/grep ou Python para buscar por tags, subject, lesson text
3. Retorna results combinados com source attribution (honcho vs disk)

**Invocação pelo agente:**
```
# Query rápida (sem fallback): usa honcho_search_conclusions (built-in tool)
conclusions = honcho_search_conclusions(query=topic, topK=5)

# Query com fallback disk: usa skill honcho-query
conclusions = honcho_query(query=topic, topK=5)
```

**Cenários de uso:**
| Cenário | Tool |
|---|---|
| Startup agent — contexto rápido | `honcho_search_conclusions` (built-in) |
| Heartbeat — briefing com fallback | `honcho-query` skill |
| Query sobre erro específico | `honcho-query` skill (garante results do vault) |

---

### 4. Cron `honcho-lessons-capture`

**Responsabilidade:** Extrair lições diariamente às 07h BRT.

**Configuração:**
```
Schedule:  cron 0 10 * * * (BRT = UTC-3, 07h BRT)
Session:   isolated
Agent:     memory-agent
Model:     fastest
```

**Payload (agentTurn — o agente recebe instrução):**
```json
{
  "kind": "agentTurn",
  "message": "Execute honcho_capture: run --days 1. Validate dates first (QW-0). Write lessons to memory/vault/lessons/. Report JSON summary at end.",
  "model": "fastest"
}
```

**Failure alert:**
```json
{
  "after": 2,
  "channel": "telegram",
  "to": "7426291192",
  "mode": "announce"
}
```
Se o ETL falhar 2 execuções consecutivas, alerta enviado a Lincoln.

**Nota CLI:** Formato `--failureAlert` deve ser verificado com `openclaw cron add --help` antes de criar. Se CLI não aceitar flags aninhadas, usar JSON payload em vez de flags.

**Argumentos do script:**
- `--days N` — janela de extracção (default: 1 dia)
- `--dry-run` — não escreve, só mostra o que seria gerado
- `--source github|trello|tldv` — fonte específica

---

## Retrieval — Como os Agentes Acedem

### Startup (Main agent + Memory agent)

```python
# Ferramentas built-in (Honcho directo — fast path):
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
# Skill honcho-query (com fallback disk):
if not honcho_health_check():
    alert("Honcho offline — using disk fallback")

briefing = honcho_query(
    "briefing dos projectos activos: "
    "o que mudou, o que precisa atenção, lições da semana?",
    topK=10
)
# Envia DM para Lincoln
```

### Pergunta directa

Lincoln pode perguntar "o que a gente já decidiu sobre X?" →
`honcho_search_conclusions(query=X)` → lições relacionadas.

---

## Quick Wins (Execução Ordenada)

### QW-0 — Validar datas das lessons de exemplo (5 min) ⚠️ ANTES DE QW-2
Antes de commitar qualquer lesson de exemplo, validar as datas reais dos eventos:
- Stale thresholds: 2026-05-22 ou 2026-05-21? Confirmar no git log e HEARTBEAT
- JWT TLDV renewal: quando foi? Confirmar no commit history
- Cron disappearing: quando foi detectado? Confirmar no HEARTBEAT
- Azure blob pipeline: quando? Confirmar no commit history
- max_tokens bug: quando foi descoberto?

**Não commitar exemplos com datas erradas.**

### QW-1 — Criar folder `memory/vault/lessons/` + template (5 min)
```bash
mkdir -p memory/vault/lessons
# Criar lessons/TEMPLATE.md com frontmatter correcto
```

### QW-2 — Escrever 3-5 lessons manuais (30 min)
Lições de decisões reais (datas validadas em QW-0):
1. Stale thresholds por entity
2. JWT TLDV renewal via BrowserBox
3. Cron job disappearing → detecção e recovery
4. Azure blob pipeline vs TLDV API split
5. max_tokens=600 bug em insights_json

### QW-3 — Criar `honcho_capture.py` mínimo (2-4h)
Lê GitHub PRs (via `github_client.py` existente), gera lessons, escreve em `memory/vault/lessons/`.
**Modelo:** `fastest` (GPT-5-mini ou equivalente) — lições curtas, não precisa reasoning pesado.

**Output:** JSON summary no stdout:
```json
{"lessons_written": 3, "sources": {"github": 2, "trello": 1}, "skipped": 0, "errors": []}
```

### QW-4 — Criar cron `honcho-lessons-capture` (15 min)
```bash
openclaw cron add \
  --name "honcho-lessons-capture" \
  --schedule "cron 0 10 * * *" \
  --sessionTarget isolated \
  --agentId memory-agent \
  --model fastest \
  --payload.kind agentTurn \
  --payload.message "Execute honcho_capture: run --days 1. Validate dates first (QW-0). Write lessons to memory/vault/lessons/. Report JSON summary at end." \
  --failureAlert.after 2 \
  --failureAlert.channel telegram \
  --failureAlert.to 7426291192 \
  --description "Extrai lições de GitHub/Trello/TLDV e escreve em memory/vault/lessons/"
```

### QW-5 — Criar skill `honcho-query` (1-2h)
Skill que expõe:
```python
honcho_query(query: str, topK: int = 5) -> List[Lesson]
honcho_health_check() -> bool
```
Com fallback disk quando Honcho offline.

### QW-6 — Validar retrieval no Honcho (15 min)
Após QW-2: testar `honcho_search_conclusions` sobre as lessons escritas manualmente.

---

## Decisões de Design (feitas)

| Decisão | Escolha | Rationale |
|---|---|---|
| LLM para extracção | `fastest` (GPT-5-mini) | Lições curtas, não precisa reasoning pesado |
| Granularidade | **Múltiplas se independentes, 1 se mesmo tema** | "Por decisão" é a regra |
| Deduplicação | Path = `date + slugify(subject) + sha256(source_ref)[:6]` | Se arquivo existe, skip — idempotente |
| Retenção | lessons nunca expiram | Relevância avaliada no retrieval |
| `processed` flag | **Removido** | Campo sem consumidor; idempotência por path |
| Fallback Honcho→disk | Skill `honcho-query` separada | honcho_query com fallback disk |
| SPOF desktop-link | Documentado + mitigação | Heartbeat valida; vault/lessons/ sempre disponível |
| Output do ETL | JSON summary no stdout | Legível por cron/agente; report simples |
| Peer refresh TTL | Tipicamente < 5 min (desconhecido) | Fallback disk se Honcho não refletiu ainda |

---

## Progressão

1. **Phase 1 (QW-0 + QW-1 + QW-2):** Validar datas + `memory/vault/lessons/` criado + 5 lessons manuais
2. **Phase 2 (QW-3 + QW-4):** honcho_capture.py ETL mínimo + cron com failureAlert
3. **Phase 3 (QW-5 + QW-6):** Skill honcho-query + validação retrieval
4. **Phase 4:** Trello + TLDV no ETL
5. **Phase 5:** Integração nos heartbeats + agentes
6. **Phase 6:** Avaliar se Honcho pode substituir Claude Mem como source primária

---

## Checklist de Execução

- [ ] **QW-0:** Validar datas das lessons de exemplo antes de QW-2
- [ ] QW-1: Criar `memory/vault/lessons/` + template
- [ ] QW-2: Escrever 3-5 lessons manuais (datas validadas)
- [ ] QW-3: Criar `honcho_capture.py` mínimo (JSON output)
- [ ] QW-4: Criar cron `honcho-lessons-capture` (failureAlert após 2 falhas)
- [ ] QW-5: Criar skill `honcho-query` com fallback disk
- [ ] QW-6: Validar retrieval no Honcho
- [ ] Gap 6: Validar schema de decisões existente

---

_Last updated: 2026-05-23_

[^1]: TTL peer refresh: "< 5 min" é estimativa não verificada instrumentalmente.
Honcho rebuilda peer representations async; o delay real depende da carga.
Fallback disk cobre a incerteza: se Honcho ainda não reflectiu, leitura de
memory/vault/lessons/ retorna o dado correto.
