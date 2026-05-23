---
type: lesson
subject: "PR #2 — feat(reconciliation): add structured memory reconciliation with causal observability"
author: unknown
tags: [reconciliação, memória, desenvolvimento, segurança]
date: 2026-04-07

## O que aconteceu
Este PR introduz um pipeline de reconciliação de memória para tópicos curados, inicialmente como piloto para `tldv-pipeline-state.md`, com execução em shadow mode e possibilidade de promover para write mode. Inclui um ledger append-only para decisões e um relatório de execução, além de ajustes no parsing da fila de conflitos e expansão dos testes de segurança e funcionais.

## Decisão / Solução
Foi decidido implementar um novo pipeline de reconciliação que organiza o fluxo de eventos, permitindo a geração de um ledger de decisões e um relatório de execução. O modo de escrita foi protegido por uma flag para evitar alterações indesejadas, e novos módulos foram criados para normalização e agrupamento de evidências, além de ajustes na persistência e testes abrangentes para garantir a funcionalidade e segurança.

## Lessons
- Sempre proteja modos que alteram dados permanentes com flags de segurança para evitar mudanças indesejadas.
- A normalização de dados deve ser consistente entre diferentes componentes para evitar falsos positivos/negativos.
- Testes abrangentes, incluindo testes funcionais e de segurança, são essenciais ao introduzir novas funcionalidades que podem impactar o comportamento do sistema.

## Source
https://github.com/living/livy-memory-bot/pull/2
