# Audit — Honcho Memory Consolidation
**Data:** 2026-05-23
**Autor:** Livy
**Status:** Levantamento completo

---

## 1. Estado Atual — O Que Já Existe

### 1.1 Honcho Plugin (OpenClaw)
- **Plugin:** `openclaw-honcho` instalado em `~/.openclaw/extensions/openclaw-honcho`
- **Config:** `baseUrl: http://100.121.74.111:8000`, `workspaceId: openclaw`, sem API key (self-hosted, Tailscale-only)
- **Gateway:** reiniciado e operacional
- **Peers no workspace `openclaw`:**

| Peer ID | Tipo | Observação |
|---|---|---|
| `owner` | system | Auto-criado pelo plugin |
| `agent-main` | agent | Main agent — ✅ |
| `agent-memory-agent` | agent | Memory agent — ✅ |
| `7426291192` | user | Lincoln (auto-seeded) |

**Veredicto:** Honcho plugin funcional. Todos os agentes relevantes já têm peer.

---

### 1.2 Estrutura de Memória Existente (Vault)

```
memory/vault/
├── claims/              # Claims brutas de fontes
├── concepts/            # Conceitos de domínio
├── decisions/           # Decisões (1 arquivo exemplo: 2026-04-10)
├── entities/            # Pessoas, reuniões, cards
├── evidence/            # Evidências brutas
├── insights/            # ⚠️ PENDENTE — ver nota abaixo
├── lint-reports/        # Relatórios de lint do vault
├── quality-review/      # Reviews de qualidade
├── relationships/       # Arestas entre entidades
└── schema/              # Schemas de validação

vault/
├── insights/            # Scripts Python de geração de insights
│   ├── claim_inspector.py
│   ├── owner_por_tema.py
│   ├── risco_projetos.py
│   ├── resumo_semanal.py
│   ├── temas_recorrentes.py
│   ├── envia_resumo.py
│   └── no_decisions.py
├── capture/             # (vazio ou com conteúdo legacy)
├── crons/               # Crons específicos do vault
├── enrich_github.py     # ETL GitHub
└── SCHEMA.md
```

**Insights existentes em `memory/vault/insights/`:**
- `living-insights-2026-04-19.html` — relatório semanal
- `owner-por-tema.md` — ownership por tema
- `resumo-semanal.md` — resumo consolidado
- `risco-projetos.md` — risk tracker
- `temas-recorrentes.md` — temas recorrentes
- `no-decisions.md` — reuniões sem decisão explícita (10 de 27)

---

### 1.3 Skill vault-query
- **Local:** `skills/vault-query/SKILL.md`
- **Capacidades:** entity lookup, concept trace, decision history, provenance, cross-reference, gap analysis
- **Funciona via:** leitura direta dos arquivos markdown (não passa pelo Honcho)
- **Fallback:** SE Honcho offline → lê diretamente de `memory/vault/` — promessa no spec, mas **não implementado no SKILL.md atual**

---

### 1.4 Crons Existentes (relevant)
| Cron | Schedule | Status |
|---|---|---|
| `vault-ingest` | 0 10,14,20 * * * | ✅ ok |
| `research-trello` | 0 0,6,12,18 * * * | ✅ ok |
| `research-github` | 0 0,6,12,18 * * * | ✅ ok |
| `research-tldv` | 0 0,6,12,18 * * * | ✅ ok |
| `research-consolidation` | 0 7 * * * | ✅ ok |
| `vault-lint` | 0 21 * * * | ✅ ok |
| `vault-crosslink` | 0 1 * * * | ✅ ok |
| `vault-insights-weekly-generate` | 0 7 * * 1 | ✅ ok |
| **`honcho-lessons-capture`** | — | ❌ **NÃO EXISTE** |

---

## 2. Gaps Reais — O Que Está Faltando

### Gap 1 — `lessons/` folder não existe
**Impacto:** blocker absoluto para qualquer extração de lições
**Onde deveria estar:** `memory/vault/lessons/`
**Formato planejado:** `.md` com frontmatter (`type`, `source`, `what_happened`, `lesson`, `confidence`, `tags`)
**Ação:** criar o folder e o template base

### Gap 2 — Pipeline `honcho_capture.py` não existe
**Impacto:** sem ETL, não há extração automática de lições
**Dependências:** precisa de `lessons/` (Gap 1) + modelo LLM para extração
**Ação:** criar script em `vault/insights/honcho_capture.py`
**Modelo sugerido:** `fastest` (GPT-5-mini ou equivalente) — rationale de lições é curta, não precisa reasoning pesado

### Gap 3 — `claude-mem` e `honcho` rodando em paralelo
**Impacto:** mesma interação salva em duas camadas distintas
**Estado atual:**
- Slot: `openclaw-honcho` ✅
- Worker `claude-mem` na porta 37777: ainda subindo (mesmo com slot diferente)
- `observationFeed` do `claude-mem`: ativo, publicando no Telegram
**Ação:** avaliar se mantém `claude-mem` como backup ou desativa

### Gap 4 — Cron `honcho-lessons-capture` não existe
**Impacto:** pipeline de extração de lições não existe como job agendado
**Ação:** criar cron "0 10 * * *" (BRT 07h) pointing to `vault/insights/honcho_capture.py run --days 1`

### Gap 5 — Vault-query não tem fallback Honcho→disk
**Impacto:** skill promete fallback mas não implementa
**Ação:** adicionar lógica no SKILL.md: se Honcho API falha, ler de `memory/vault/lessons/`

### Gap 6 — Decisões esparsas, sem padronização
**Estado:** 1 decisão em `decisions/` (exemplo de 2026-04-10, com confidence `low`)
**Problema:** schema de decisão existe mas não é seguido consistentemente
**Ação:** validar consistência antes de escalar extração

---

## 3. Quick Wins — O Que Fazer Primeiro

### QW-1 — Criar folder `lessons/` (5 min)
```bash
mkdir -p memory/vault/lessons
# Criar template lessons/template.md
```

### QW-2 — Escrever 3-5 lessons manuais (30 min)
Lições de decisões reais já tomadas:
1. Stale thresholds por entity (pattern de 2026-05-21)
2. JWT TLDV renewal via BrowserBox (pattern recorrente)
3. Cron job disappearing → detecção e recovery (2026-05-21)
4. Azure blob pipeline vs TLDV API split (2026-05-22)
5. Descoberta de 64 meetings com insights_json=null (max_tokens=600 bug)

### QW-3 — Criar `honcho_capture.py` mínimo (2-4h)
Lê GitHub PRs (via `research_github_cron.py` existing), gera lessons, escreve em `lessons/`.

### QW-4 — Criar cron `honcho-lessons-capture` (15 min)
```bash
openclaw cron add \
  --name "honcho-lessons-capture" \
  --schedule "cron 0 10 * * *" \
  --sessionTarget isolated \
  --agentId memory-agent \
  --model fastest \
  --payload.kind agentTurn \
  --payload.message "vault/insights/honcho_capture.py run --days 1" \
  --description "Extrai lições de GitHub/Trello/TLDV e escreve em memory/vault/lessons/"
```

### QW-5 — Validar retrieval no Honcho (15 min)
Após QW-2: testar `honcho_search_conclusions` sobre as lessons escritas manualmente.

---

## 4. Arquitectura Proposta (Atualizada do Draft)

```
FONTES              PIPELINE              STORAGE              RETRIEVAL
───────             ────────              ───────              ─────────
GitHub API  ───►  research_*       ───►  vault/claims/   ──► agents
Trello API       (já existente)         vault/decisions/     via honcho_
TLDV/Supabase                           vault/lessons/        search/ask
                     honcho_capture.py  (lessons/ = novo)
                       │
                       ▼
                   HONCHO (cache)
                   peer: agent-memory-agent
                   peer: agent-main
```

**Separação RAW / Sabedoria (mantida):**
- RAW facts → `vault/claims/`, `vault/decisions/`
- Sabedoria/lições → `vault/lessons/`
- Honcho = cache de leitura rápida

---

## 5. Decisões de Design — Abertas vs Recomendadas

| Decisão | Status | Recomendação |
|---|---|---|
| LLM para extração | Aberta | `fastest` (GPT-5-mini) — lições curtas |
| Granularidade | Aberta | **Por decisão** (não por PR) — mais granular, menos ruído |
| Deduplicação | Aberta | Hash de `what_happened + subject` → ID único |
| Retenção | Aberta | lessons nunca expiram; relevância avaliada no retrieval |
| claude-mem backup? | Aberta | Manter por 30 dias como fallback, depois avaliar |

---

## 6. Checklist de Execução

- [ ] QW-1: Criar `memory/vault/lessons/` + template
- [ ] QW-2: Escrever 3-5 lessons manuais
- [ ] QW-3: Criar `honcho_capture.py` mínimo
- [ ] QW-4: Criar cron `honcho-lessons-capture`
- [ ] QW-5: Validar retrieval no Honcho
- [ ] Gap 3: Decidir destino do `claude-mem` (manter ou desativar)
- [ ] Gap 5: Implementar fallback Honcho→disk na skill vault-query
- [ ] Gap 6: Validar schema de decisões (1 arquivo existente)

---

## 7. Nota sobre Spec Original

A spec `2026-05-23-honcho-memory-consolidation-design.md` diz "Honcho currently disabled" — **está desatualizada**. O plugin foi habilitado manualmente em 2026-05-23. O spec precisa ser atualizado com o estado real.

---

_Livy · 2026-05-23_
