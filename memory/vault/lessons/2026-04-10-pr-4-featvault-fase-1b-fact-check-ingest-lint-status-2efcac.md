---
type: lesson
subject: "PR #4 — feat(vault): fase 1B — fact-check, ingest, lint, status"
author: unknown
cycle_time: 4m
tags: [feature, ingestion, testing, observability]

## O que aconteceu
Este PR implementa a Fase 1B do “Memory Vault”, adicionando módulos para ingestão de eventos, lint diário, cache de fact-check e métricas operacionais. Também inclui testes abrangentes e atualizações na documentação.

## Decisão / Solução
Foi decidido criar um pipeline de ingestão que converte eventos em arquivos Markdown, implementando um sistema de cache para fact-check e um lint diário para garantir a qualidade do conteúdo no vault. As métricas operacionais foram adicionadas para melhorar a observabilidade.

## Lessons
- A implementação de testes automatizados (TDD) é crucial para garantir a confiabilidade das novas funcionalidades e facilitar futuras manutenções.
- A validação de permissões e caminhos é essencial ao operar diretamente no filesystem, especialmente em ambientes de CI/produção.
- A abordagem de "upsert" deve ser revisada para permitir atualizações em arquivos existentes, evitando a necessidade de reprocessamento manual.

## Source
https://github.com/living/livy-memory-bot/pull/4
