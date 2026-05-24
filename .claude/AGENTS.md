# AGENTS.md — Livy Memory Agent

## Contexto de Execução

- **Workspace:** `~/.openclaw/workspace-livy-memory/`
- **Repo:** `living/livy-memory-bot`
- **Grupo:** `-5158607302` (@livy_agentic_memory_bot)
- **Timezone:** America/Sao_Paulo

## Como Usar Este Workspace

1. Leia `.claude/SOUL.md` e `.claude/IDENTITY.md` no startup
2. Leia `memory/MEMORY.md` como índice curado
3. Use `memory/curated/` para contexto de projetos específicos
4. Ao encontrar decisões técnicas: atualize o topic file relevante
5. Ao encontrar contradições ou stale entries: registre na consolidação

## Skills Disponíveis

| Skill | Quando usar |
|---|---|
| `vault-consultant` | Consultar base de conhecimento vault (decisões, projetos, pessoas, reuniões) |
| `vault-query` | Query estruturada a entities/claims/relationships do vault |
| `memory-assistant` | Memória agêntica de 3 camadas (claude-mem → curated → operational) |
| `meetings-tldv` | Buscar reuniões e decisões no TLDV |

## Base de Conhecimento — Vault

```
memory/vault/
├── VAULT.md              # Documentação técnica
├── decisions/            # Topic files (QW-2: TLDV+GitHub+Trello → markdown)
│   ├── livy-memory-agent.md
│   ├── bat-conectabot-observability.md
│   └── delphos-video-vistoria.md
├── claims/               # Claims individuais (Wiki v2)
├── entities/             # Meetings + Persons
└── relationships/        # Edges entre entidades
```

**Regra: Antes de responder perguntas sobre contexto/decisões da Living, consulte o vault.**

## Fontes de Memória

| Fonte | Path | Formato |
|---|---|---|
| Observations | `~/.claude-mem/claude-mem.db` | SQLite |
| Topic files | `memory/curated/*.md` | Markdown |
| Índice | `memory/MEMORY.md` | Markdown |
| Archive | `memory/.archive/` | Markdown |

## Periodicidade

- Consolidação: 07h BRT (cron `dream-memory-consolidation`)
- HEARTBEAT: a cada 4h
