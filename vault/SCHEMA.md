---
name: vault-ingest-schema
description: README técnico do pipeline de ingest e crosslink do vault.
---

# SCHEMA.md — Vault Ingest Pipeline

## Visão Geral

Este documento descreve o pipeline técnico de ingest do vault, seus estágios, arquivos principais e execução manual.

Pipeline completo (alto nível):

1. coleta de fontes
2. parsing/normalização
3. extração de entidades
4. upsert de entidades
5. geração de relacionamentos base
6. resolução de identidade/projeto
7. enriquecimento de arestas
8. deduplicação/finalização e persistência

## Stages 1–8 (overview)

### Stage 1 — Source Fetch
Coleta dados brutos das fontes suportadas (meetings, PRs, cards, eventos).

### Stage 2 — Normalize
Normaliza campos (ids, nomes, timestamps, slugs, links).

### Stage 3 — Entity Extract
Extrai entidades candidatas (person, project, meeting, pr, card).

### Stage 4 — Entity Upsert
Cria/atualiza páginas e registros canônicos de entidade no vault.

### Stage 5 — Edge Build
Monta arestas iniciais entre entidades com base em evidências de origem.

### Stage 6 — Resolve
Resolve identidade e projeto via cache + mapas + heurísticas.

### Stage 7 — Enrich
Enriquece arestas com metadados (confidence, origem, contexto).

### Stage 8 — Dedup & Finalize
Deduplica por chave canônica, preserva proveniência e grava saídas idempotentes.

## Arquivos principais e responsabilidades

### Schemas de mapeamento
- `memory/vault/schema/trello-member-map.yaml` — member id Trello → pessoa
- `memory/vault/schema/github-login-map.yaml` — login GitHub → pessoa
- `memory/vault/schema/repo-project-map.yaml` — repo GitHub → projeto
- `memory/vault/schema/board-project-map.yaml` — board Trello → projeto

### Documentação operacional
- `memory/vault/schema/AGENTS.md` — regras de operação e segurança do vault
- `memory/vault/schema/CROSSLINK.md` — detalhes do pipeline de crosslink

### Saídas do vault
- `memory/vault/index.md` — índice navegável do vault
- `memory/vault/log.md` — histórico append-only de runs
- relationship files (`card-person`, `card-project`, `pr-person`, `pr-project`) — camada de grafo

## Como rodar o pipeline manualmente

> Ajuste os comandos para os scripts reais do repositório quando necessário.

Fluxo recomendado:

1. Rodar crosslink:

```bash
./scripts/vault-crosslink.sh
```

2. Rodar ingest:

```bash
./scripts/vault-ingest.sh
```

3. Rodar lint:

```bash
./scripts/vault-lint.sh
```

Validação rápida pós-run:

- conferir `memory/vault/log.md`
- conferir contagens em `memory/vault/index.md`
- validar arestas no relacionamento (`pr-person`, `pr-project`, `card-person`, `card-project`)

## Testes

Conjunto esperado de verificação:

- testes de schema/load de mapas (YAML)
- testes de identity resolution (cache/API/login-map/frontmatter/fuzzy/draft)
- testes de bot filtering
- testes de dedup/idempotência (Stage 8)
- testes de regressão do `crosslink_builder` e `crosslink_resolver`

Execução (exemplo):

```bash
pytest -q
```

Ou focado em crosslink:

```bash
pytest -q -k crosslink
```

## Cron de referência

- `vault-crosslink` — 01:00 BRT
- `vault-ingest` — sequência operacional após crosslink
- `vault-lint` — validação de consistência do vault

## Notas

- Identity resolution robusta depende da manutenção contínua dos arquivos de mapa.
- Ambiguidades devem cair em `draft` em vez de gerar arestas erradas.
- Stage 8 é a proteção final contra duplicidade e inconsistência.
