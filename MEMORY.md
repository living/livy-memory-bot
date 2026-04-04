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
| TLDV Pipeline | `memory/curated/tldv-pipeline-state.md` | ativo_com_bugs (whisper migrado) |
| Super Memória Corporativa | `memory/curated/projeto-super-memoria-robert.md` | proposta (Robert, 2026-04-03) |
| livy-evo | `memory/curated/livy-evo.md` | conforme cronograma |

### Agentes & Tools

| Assunto | Topic File | Status |
|---|---|---|
| Livy Memory Agent | `memory/curated/livy-memory-agent.md` | ativo |
| OpenClaw Gateway | `memory/curated/openclaw-gateway.md` | ativo |
| claude-mem | `memory/curated/claude-mem-observations.md` | ativo |

---

## 🗂️ Decisões Registradas

### 2026-04-03 — Whisper Migration: faster-whisper → OmniRoute API-first

`whisper_client.py` reescrito para usar OmniRoute API (groq/whisper) como backend primário. faster-whisper agora opcional. Resolve OOMKilled no VPS.
Topic file: `memory/curated/tldv-pipeline-state.md`

### 2026-04-03 — OmniRoute upgrade 3.4.4 → 3.4.9

Claude Code compatibility. Cascade com 7 modelos em PremiumFirst combo. Config cleanup: minimax-portal removido, PremiumFirst para todos os agentes.
Topic file: `memory/curated/openclaw-gateway.md`

### 2026-04-03 — LLM Rerank + Moderation Guardrails

Design aprovado para reranker via LLM e moderation como pré-hook no `step_enrich`. Implementation plan commitado.
Topic file: `memory/curated/tldv-pipeline-state.md`

### 2026-04-03 — VPS → Living network via Tailscale Node Sharing

Nó `ts-dmz-2.potoroo-ladon.ts.net` (100.92.23.115) conecta VPS à rede Living.
Topic file: `memory/curated/openclaw-gateway.md`

### 2026-04-03 — Super Memória Corporativa (Proposta Robert)

Robert propôs via áudio expandir a memória agêntica para cobrir todo o ecossistema digital da Living: Gmail institucional, Google Drive/Docs, WhatsApp e TLDV.
Análise: infra base (TLDV pipeline + Signal Cross-Curation + ChromaDB) já resolve ~60% do escopo.
Gaps: Google Auth (Domain-wide Delegation), RAG multimodal (RAG-Anything para DOCX/XLSX/PDF), Identity Resolution (cruzar e-mail↔telegram↔tldv).
Topic file: `memory/curated/projeto-super-memoria-robert.md`

### 2026-03-31 — Sistema de Memória como Infraestrutura de Decisão

Decisão: criar agente `@livy_agentic_memory_bot` com memória agêntica de 3 camadas.
Repo: `living/livy-memory-bot`
Arquitetura: claude-mem SQLite (observations) → MEMORY.md + topic files (curated) → HEARTBEAT.md (operational)
Cron: `dream-memory-consolidation` (07h BRT), `memory-watchdog` (a cada 4h)

### 2026-03-30 — TLDV Pipeline — gw.tldv.io 502 (não é token)

gw.tldv.io retorna 502 Bad Gateway. Token JWT válido até 2026-04-29 (~25 dias). Problema é endpoint de unarchive.
Workaround: `video_archiver.py` diretamente.

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

_Last updated: 2026-04-03_
