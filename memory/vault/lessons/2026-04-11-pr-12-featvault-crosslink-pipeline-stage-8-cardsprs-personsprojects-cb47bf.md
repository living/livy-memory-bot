---
type: lesson
subject: "PR #12 — feat(vault): Crosslink Pipeline — Stage 8 (Cards/PRs → Persons/Projects)"
author: unknown
date: 2026-04-11
cycle_time: 2h 7m
tags: [pipeline, integração, enriquecimento]

## O que aconteceu
Este PR implementa o Stage 8 do Crosslink Pipeline no vault, criando um grafo de relacionamentos que conecta Cards (Trello) e PRs (GitHub) a Pessoas e Projetos. A mudança foi feita para melhorar a rastreabilidade e o contexto das reuniões, além de incluir várias melhorias no sistema.

## Decisão / Solução
Foi decidido implementar um novo estágio que conecta itens de trabalho a "hubs" (pessoas e projetos), utilizando arquivos JSON para persistir relacionamentos e YAML para configuração. A arquitetura foi documentada e diversas melhorias foram feitas no processo de ingestão e enriquecimento de dados.

## Lessons
- A utilização de arquivos JSON para persistir relacionamentos permite uma melhor organização e acesso aos dados, facilitando a rastreabilidade.
- A configuração via YAML proporciona flexibilidade e facilita a manutenção dos mapeamentos necessários para o funcionamento do sistema.
- A implementação de um sistema de deduplicação e merge de "draft persons" ajuda a manter a integridade dos dados e evita a criação de entradas duplicadas.

## Source
https://github.com/living/livy-memory-bot/pull/12
