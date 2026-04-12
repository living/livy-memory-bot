---
name: crosslink-pipeline
description: Documentação técnica do pipeline de crosslink do Memory Vault.
---

# CROSSLINK.md — Pipeline de Relacionamentos do Vault

## Visão Geral

O pipeline de crosslink gera e mantém arestas entre entidades do vault (pessoas, projetos, PRs e cards), consolidando relacionamentos para navegação e análise.

Fluxo principal:

`crosslink_builder → crosslink_resolver → crosslink_enrichment → crosslink_dedup`

## Arquitetura

### 1) `crosslink_builder`

Responsável por montar candidatos de arestas a partir das fontes de entrada:
- Meetings enriquecidas
- PRs do GitHub
- Cards do Trello

Gera payload base com `source`, `target`, `relation_type`, `origin`, `evidence`.

### 2) `crosslink_resolver`

Resolve identidade e entidades canônicas (principalmente pessoas e projetos):
- aplica cache de resolução
- consulta schemas de mapeamento
- tenta frontmatter/aliases
- aplica fuzzy match conservador
- envia casos ambíguos para draft

### 3) `crosslink_enrichment`

Enriquece as arestas com metadados operacionais:
- timestamps
- confidence
- origem (meeting/pr/card)
- contexto (repo, board, tags, etc.)

### 4) `crosslink_dedup`

Deduplica e consolida arestas finais:
- remove duplicatas por chave canônica
- mantém a melhor confiança
- preserva proveniência
- garante escrita idempotente

## Relationship Files (saída)

O pipeline mantém quatro arquivos de relacionamento no vault:

1. `card-person.json`
2. `card-project.json`
3. `pr-person.json`
4. `pr-project.json`

Esses arquivos são a base da camada de grafos de relacionamento.

## Schema Files (entrada de mapeamento)

Arquivos de schema usados na resolução:

- `memory/vault/schema/trello-member-map.yaml`
- `memory/vault/schema/github-login-map.yaml`
- `memory/vault/schema/repo-project-map.yaml`
- `memory/vault/schema/board-project-map.yaml`

Papéis:
- `trello-member-map`: member id Trello → pessoa canônica
- `github-login-map`: login GitHub → pessoa canônica
- `repo-project-map`: repositório → projeto
- `board-project-map`: board Trello → projeto

## Batch PR Author Cache Flow

Para PRs, a resolução de autores segue fluxo em lote para reduzir chamadas e inconsistência:

1. carrega cache local de autores resolvidos
2. busca PRs por repositório na janela configurada
3. resolve autores por prioridade:
   - cache
   - API
   - `github-login-map.yaml`
   - frontmatter aliases
   - fuzzy
   - draft
4. atualiza cache ao fim do lote
5. grava arestas `pr-person` e `pr-project`

Benefícios:
- menor custo de API
- resolução estável entre execuções
- menos ruído de nomes variantes

## Cron de Produção

Job: `vault-crosslink`

- **Schedule:** 01:00 BRT
- **Objetivo:** recalcular e consolidar relações do grafo do vault antes do ingest/lint subsequente

## Métricas atuais (produção)

Estado observado:

- Meetings: **36**
- Persons: **15**
- Projects: **13**
- Edges: **729**

> Observação: números podem variar por janela de ingest e qualidade de resolução de identidade.

## Operação e troubleshooting rápido

- Se `pr-person` estiver com muitos autores `?`, revisar `github-login-map.yaml`.
- Se projeto não resolver em PR/card, revisar `repo-project-map.yaml` e `board-project-map.yaml`.
- Se volume de arestas cair abruptamente, validar filtros de bot e stage de dedup.
