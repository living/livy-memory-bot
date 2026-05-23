---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/2"
date: 2026-04-14
subject: "PR #2 — Infra Core — .NET 10, EF Core, Serilog, Health Checks, Dockerfile"
author: unknown
cycle_time: 6m
tags: [backend, .NET, Docker, EF Core, observabilidade]

## O que aconteceu
Este PR cria o esqueleto inicial do backend do SVD em .NET 10, incluindo a estrutura de projetos, configuração de persistência com PostgreSQL, uma API mínima com endpoints básicos e logging com Serilog.

## Decisão / Solução
Foi decidido criar uma solução com múltiplos projetos, configurar o EF Core para usar um schema padrão no PostgreSQL, e implementar uma infraestrutura local utilizando Docker para facilitar o desenvolvimento e testes.

## Lessons
- A padronização de schemas no banco de dados deve ser bem documentada para evitar confusões futuras, especialmente em relação à tabela de histórico de migrations.
- É importante garantir que as credenciais e segredos estejam adequadamente gerenciados em ambientes de produção e CI, evitando o uso de valores padrão.
- A implementação de health checks deve ser testada para garantir que não haja bloqueios síncronos que possam impactar a performance da aplicação durante o startup.

## Source
https://github.com/living/delphos-svd/pull/2
