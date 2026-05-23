---
type: lesson
subject: "PR #7 — Feat/v2 docs migration"
author: unknown
date: 2026-04-22
cycle_time: 1d 21h
tags: [documentação, arquitetura, monorepo]

## O que aconteceu
Este PR consolidou a fundação do monorepo utilizando pnpm e TypeScript em modo estrito, além de atualizar a documentação para refletir o pivô arquitetural da versão 2, que inclui a migração de RabbitMQ para Azure Service Bus e de PostgreSQL para Cosmos DB, mantendo o PostgreSQL para Core/Identity. Também foi adicionada a especificação do EventEnvelope e a documentação da versão 1 foi arquivada.

## Decisão / Solução
A decisão foi formalizar o pivô arquitetural para a versão 2, atualizando a documentação e a estrutura do monorepo. Foram implementadas mudanças significativas na persistência de dados e na comunicação entre serviços, além de um novo contrato para o EventEnvelope. A documentação da versão anterior foi arquivada para referência futura.

## Lessons
- A migração de serviços e a atualização da documentação devem ser feitas de forma coordenada para garantir que todos os membros da equipe estejam alinhados com as mudanças arquiteturais.
- É importante considerar a segurança de arquivos de configuração sensíveis, evitando que sejam versionados no repositório.
- A introdução de novas dependências, como o Azure Service Bus, deve ser acompanhada de uma avaliação dos impactos no ambiente de execução e na compatibilidade do código.

## Source
https://github.com/living/hydra-flow/pull/7
