# MEMORY.md — Livy Memory Agent Curated Index

> **Index de contexto curado.** Este arquivo é a memória de longo prazo do agente Livy Memory.
> Decisões técnicas, contexto de projetos, padrões operacionais.

---

## 🏗️ Arquitetura de Memória Living

| Camada | Fonte | Path |
|---|---|---|
| 1 — Observations | claude-mem SQLite | `~/.claude-mem/claude-mem.db` |
| 2 — Curated | Topic files | `memory/curated/*.md` |
| 3 — Operational | HEARTBEAT + logs | `HEARTBEAT.md`, `memory/consolidation-log.md` |

---

## 📁 Topic Files

### Projetos

| Projeto | Topic File | Status |
|---|---|---|
| Forge Platform | `memory/curated/forge-platform.md` | em progresso |
| BAT Observability | `memory/curated/bat-conectabot-observability.md` | monitorando |
| Delphos Video Vistoria | `memory/curated/delphos-video-vistoria.md` | OK |
| TLDV Pipeline | `memory/curated/tldv-pipeline-state.md` | aguardando token |
| livy-evo | `memory/curated/livy-evo.md` | conforme cronograma |

### Agentes & Tools

| Assunto | Topic File | Status |
|---|---|---|
| Livy Memory Agent | `memory/curated/livy-memory-agent.md` | ativo |
| OpenClaw Gateway | `memory/curated/openclaw-gateway.md` | ativo |
| claude-mem | `memory/curated/claude-mem-observations.md` | ativo |

---

## 🗂️ Decisões Registradas

### 2026-03-31 — Sistema de Memória como Infraestrutura de Decisão

Decisão: criar agente `@livy_agentic_memory_bot` com memória agêntica de 3 camadas.
Repo: `living/livy-memory-bot`
Arquitetura: claude-mem SQLite (observations) → MEMORY.md + topic files (curated) → HEARTBEAT.md (operational)
Cron: `dream-memory-consolidation` (07h BRT), `memory-watchdog` (a cada 4h)

### 2026-03-30 — TLDV Pipeline Token Expirado

gw.tldv.io retorna 502 Bad Gateway. Token JWT do tl;dv precisa ser renovado.
Impacto: meetings com blobs expirados no Azure travam em UNARCHIVE_REQUESTED.
Ação pendente: renovação do token.

### 2026-03-30 — BAT Sev2 Elevado

ConectaBot com 2200 erros Sev2 a cada 6h. Causa: webhook do ConectaBot (comportamento esperado).
Monitorando — não é bug, mas volume elevado.

---

## 🧠 Notas de Consolidação

- Consolidação executada: 2026-03-31 15:01 BRT
- 6 arquivos marcados para monitoramento (30-60d, stale entries)
- 0 arquivos arquivados (>60d threshold)
- Log: `memory/consolidation-log.md`

---

## 📌 Regras Operacionais

1. **LEIA este arquivo primeiro** em cada sessão (memória de longo prazo)
2. **Topic files em `memory/curated/`** contêm contexto detalhado por projeto
3. **Consolidation log** em `memory/consolidation-log.md` — registra mudanças
4. **HEARTBEAT.md** no workspace root — dashboard operacional
5. **Topic files nunca expiram** — se um projeto está ativo, o topic file permanece

---

_Last updated: 2026-03-31_
