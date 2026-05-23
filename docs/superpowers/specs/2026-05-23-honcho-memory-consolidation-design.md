# Spec — Camada de Sabedoria: Vault Lessons + Honcho

**Data:** 2026-05-23
**Autor:** Lincoln + Livy Memory
**Status:** Draft

---

## Contexto

A pipeline actual ingere dados de TLDV, GitHub e Trello → SSOT (state.json com 2221 claims). Decisões técnicas, links entre entities e estado de projetos estão documentados. Mas há uma lacuna:

- **Facts** estão no SSOT (decisões, claims, relationships)
- **Sabedoria** (lições aprendidas, contexto de bugs, rationale de decisões) não existe como camada separada
- Agentes não se "lembram" de padrões — cada sessão é effectively um fresh start sem memória semanticamente pesquisável
- Não há como perguntar "já vimos este erro antes?" ou "o que aprendemos sobre quality guardrails?"

**Necessidade:** Uma camada de sabedoria derivada das fontes cruas, pesquisável semanticamente, que alimente os agentes (main + memory) e heartbeats com contexto acumulado.

---

## Arquitectura — 3 Camadas

```
FONTES CRUAS                 CAMADA FACTS         CAMADA SABEDORIA
─────────────               ─────────────        ─────────────────
GitHub API                   vault/crons/         vault/insights/
Trello API    (ETL) ──────►  SSOT (state.json)   lessons/*.md
TLDV / Supabase               facts/claims           │
                                  │              honcho_capture
                                  │                 │
                                  ▼                 ▼
                             research-         HONCHO
                             pipeline           (cache semântica)
```

### Camadas

| Camada | Fonte | Quem escreve | Quem lê |
|---|---|---|---|
| **Facts (RAW)** | GitHub, Trello, TLDV | `vault/crons/research_*.py` | SSOT consumers |
| **Lessons (Sabedoria)** | Lessons extraídas das fontes | `vault/insights/honcho_capture.py` | Agentes, heartbeats |
| **Honcho (Cache)** | Lessons do vault | `honcho_capture` (lê lessons) | Retrieval rápido |

---

## Princípio Fundamental: Separação RAW / Sabedoria

**RAW (SSOT):**
- Source of truth para facts
- Escrito **só** por `vault/crons/`
- Schema rigoroso: `Claim`, `Evidence`, `SourceRef`
- Nunca modificado por conclusions

**Sabedoria (Lessons):**
- Derivada — não é source of truth
- Escrita **só** por `honcho_capture.py`
- Lida fontes cruas (não o SSOT) para permitir reprocessamento
- Armazenada em `memory/vault/lessons/` como markdown
- Honcho é cache de leitura rápida — não storage primário

**Regra de ouro:** Facts no SSOT. Lições no vault/lessons. Honcho é cache. Se Honcho morrer, lessons continuam no vault.

---

## Componentes

### 1. `vault/insights/honcho_capture.py`

**Responsabilidade:** ETL que lê fontes cruas (não o SSOT), gera lições estruturadas e escreve em `memory/vault/lessons/`.

**Input:** GitHub API (PRs, issues, comments), Trello API (cards, checklists, comments), TLDV/Supabase (transcripts, summaries)

**Output:** Markdown files em `memory/vault/lessons/` com frontmatter.

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
oai_model: null        # LLM used to generate (null if fact-only)
processed: false
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

### 2. `vault/insights/lessons/` (storage)

**Responsabilidade:** Storage primário de lições.

**Estrutura:**
```
memory/vault/lessons/
  2026-05-22-pr24-quality-guardrail.md
  2026-05-22-vault-regex-brackets-fix.md
  2026-05-22-stale-thresholds-per-entity.md
  ...
```

### 3. Honcho (cache semântica)

**Responsabilidade:** Cache de leitura rápida para retrieval semântico.

**Operações:**
- `honcho_capture.py` → writes lessons to Honcho (via `honcho.observations.create`)
- Agentes → leem via `honcho_search_conclusions`, `honcho_ask`

**Se Honcho offline:** Agentes leem directamente de `vault/insights/lessons/` via skill `vault-query`.

### 4. Cron `honcho-lessons-capture`

**Responsabilidade:** Extrair lições diariamente às 07h BRT.

```bash
# Cron: 0 10 * * * (BRT = UTC-3, 07h BRT)
vault/insights/honcho_capture.py run --days 1
```

**Argumentos:**
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
```

### Pergunta directa

Lincoln pode perguntar "o que a gente já decidiu sobre X?" →
`honcho_search_conclusions(query=X)` → lições relacionadas.

---

## Quick Wins Implementáveis

### Quick Win 1 — Ativar Honcho como cache
- Habilitar plugin `openclaw-honcho` (actualmente disabled)
- Criar `honcho_capture.py` mínimo que lê GitHub PRs
- Alimentar Honcho com PRs dos últimos 30 dias
- Testar retrieval no próximo /new

### Quick Win 2 — Lessons do Vault (markdown)
- Criar `memory/vault/lessons/`
- Escrever 5 lessons manuais das decisões de ontem
- Criar `vault/insights/lesson_template.md`
- Testar `honcho_search_conclusions` sobre lessons

### Quick Win 3 — Integração no Heartbeat
- Modificar `vault-insights-weekly-generate` para usar `honcho_ask`
- Adicionar campo "lições da semana" no resumo

---

## Decisões de Design Abertas

1. **LLM para extracção de rationale:** Usar qual modelo? (OmniRoute? OpenAI? MiniMax?)
2. **Granularidade das lessons:** Uma lesson por PR? Por decisão? Por tema?
3. **Deduplicação:** Se o mesmo erro acontece em dois PRs, é uma lesson ou duas?
4. **Retenção:** Lessons expiram? Threshold temporal?

---

## Progressão

1. **Phase 1 (Quick Win 1+2):** Honcho enabled + lessons em markdown + retrieval básico
2. **Phase 2:** `honcho_capture.py` ETL mínimo → GitHub PRs → lessons
3. **Phase 3:** Trello + TLDV no ETL
4. **Phase 4:** Integração nos heartbeats + agentes
