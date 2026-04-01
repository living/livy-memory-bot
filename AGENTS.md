# AGENTS.md — Livy Memory Agent

## Contexto de Execução

- **Workspace:** `~/.openclaw/workspace-livy-memory/`
- **Repo:** `living/livy-memory-bot`
- **Bot:** @livy_agentic_memory_bot (grupo `-5158607302`)
- **Timezone:** America/Sao_Paulo

## Fontes de Memória

| Fonte | Path | Formato |
|---|---|---|
| Observations | `~/.claude-mem/claude-mem.db` | SQLite |
| Topic files | `memory/curated/*.md` | Markdown |
| Índice | `MEMORY.md` | Markdown |
| Archive | `memory/.archive/` | Markdown |

## Startup — Every Session

1. Leia `.claude/SOUL.md` e `.claude/IDENTITY.md`
2. Leia `MEMORY.md` como índice curado
3. Use `memory/curated/` para contexto de projetos específicos
4. HEARTBEAT.md é o dashboard operacional — consultar em cada sessão

## Como Usar Este Workspace

1. Ao encontrar decisões técnicas: atualize o topic file relevante em `memory/curated/`
2. Ao encontrar contradições ou stale entries: registre na consolidação
3. HEARTBEAT.md mantém status operacional dos jobs e projetos
4. `memory/consolidation-log.md` registra mudanças da última consolidação

## Periodicidade

- Consolidação: 07h BRT (cron `dream-memory-consolidation`)
- Watchdog: a cada 4h (cron `memory-watchdog`)
- HEARTBEAT: a cada 4h (verificar `memory/consolidation-log.md`)

## HEARTBEAT.md — Dashboard Operacional

HEARTBEAT.md no workspace root é o dashboard. Seções:
- Jobs ativos e status
- Alertas críticos
- Decisões pendentes (do MEMORY.md)
- Última consolidação

## Skills Disponíveis

| Skill | Descrição |
|---|---|
| `memory-assistant` | Consulta memória histórica (built-in + claude-mem 3-layer). Dispara automaticamente quando o agente precisa de contexto passado. |

**Referência:** `~/.openclaw/workspace/skills/memory-assistant/SKILL.md`

## Identity Files

Os arquivos em `.claude/` definem identidade e valores. O workspace root (`SOUL.md`, `IDENTITY.md`, `AGENTS.md`) são cópias operacionais.
