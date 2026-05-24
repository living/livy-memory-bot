---
name: vault-consultant
description: Consulta a base de conhecimento da Living (vault). Usar SEMPRE que a pergunta for sobre: decisões passadas, contexto de projetos, histórico de reuniões, pessoas, relacionamentos, ou qualquer coisa que precise de memória de longo prazo. O vault contém decisions/ (QW-2: TLDV+GitHub+Trello), claims/ (Wiki v2), entities/ (meetings+persons), relationships/ (edges).
---

# Vault Consultant Skill

## Quando Usar

Use **ANTES** de responder a perguntas sobre:
- Decisões passadas da Living
- Contexto de projetos (BAT, Delphos, Forge, TLDV)
- Histórico de reuniões ou participantes
- Relacionamentos entre pessoas e projetos
- Anything que precise de memória de longo prazo

## Como Consultar

1. **Ler o índice**: `memory/vault/decisions/` + `memory/vault/VAULT.md`
2. **Buscar decisões**: usar padrão grep/ripgrep por projeto ou data
3. **Seguir relacionamentos**: `memory/vault/relationships/`
4. **Criar síntese**: se a query gerar insight novo, criar página em `memory/vault/decisions/`

## Estrutura do Vault

```
memory/vault/
├── VAULT.md              # Documentação técnica completa
├── decisions/            # Topic files por projeto (QW-2)
│   ├── livy-memory-agent.md
│   ├── bat-conectabot-observability.md
│   └── delphos-video-vistoria.md
├── claims/               # Blobs de claims individuais (Wiki v2)
├── entities/             # Meetings + Persons
│   ├── meetings/
│   └── persons/
└── relationships/        # Edges entre entidades
```

## Regra de Ouro

> **Se não sabes, consulta o vault primeiro.** O vault é a memória de longo prazo da Living. Não invente contexto — busque-o.
