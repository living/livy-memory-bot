---
name: hydra-flow
description: Hydra-Flow — hub extensível plugin-first para comunicação/mensageria/processos. TypeScript/Fastify/Azure SB. Fase de design/spec.
type: projeto
date: 2026-04-30
project: living/hydra-flow
status: em_design
---

# Hydra-Flow

## O que é

**Hydra-Flow** = hub extensível **plugin-first** para comunicação, mensageria e processos em ambiente **event-driven** e **multi-tenant**.

Diferente de projetos concretos (SVD, BAT), Hydra-Flow é **fase de design/spec** — o repo é predominantemente documental. Código runtime ainda não foi merged.

## Repos

| Repo | Descrição |
|---|---|
| `living/hydra-flow` | Projeto principal (TypeScript, Fastify, Azure SB) |

## Stack

- Runtime: TypeScript (strict mode, sem `any`)
- HTTP: **Fastify** (mudou de NestJS — SPEC 002)
- Broker: **Azure Service Bus** (mudou de RabbitMQ — SPEC 002)
- DB: Cosmos DB v2
- Orquestração: **GitHub Copilot SDK** (mudou de YAML/engine — PR #6)

## Princípios (CONSTITUTION)

| Princípio | Significado |
|---|---|
| Spec-First | Sem Spec aprovada, sem código |
| Request Brokered | Todo request vira job no broker |
| Plugin-First | Core mínimo; regra específica em plugins |
| Type Safety | TypeScript strict, sem `any` |
| Test-Driven | Mudanças acompanhadas de testes |

## Specs

- **CONSTITUTION**: regras do projeto
- **SPEC 001**: Monorepo Foundation + Plugin Registry (estevesm, 2026-04-20)
- **SPEC 002**: Fastify + Azure SB migration (estevesm, 2026-04-20)

## PRs

| # | Título | Autor | Status |
|---|---|---|---|
| #8 | Initial - Core Code and Plugins | estevesm | 🔄 open (2026-04-30) — primeiro código runtime real |
| #6 | Add roadmap Hydra-Flow × Delphos MVP | lincolnqjunior | 🔄 open (2026-01-20) |

## Integração SVD

- SVD SP5 (Hydra Adapter, PR #9 merged) se comunica via webhook com Hydra-Flow
- Hydra-Flow é o hub central de plugins; SVD é um consumer/plugin
- Articulação: "Hydra-Flow × Delphos MVP" (PR #6)

## Decisões Técnicas

- **2026-04-13**: Escolha Hydra-Flow vs Azure Logic Apps — construir próprio
- **2026-04-20**: NestJS → Fastify (SPEC 002)
- **2026-04-20**: RabbitMQ → Azure Service Bus (SPEC 002)
- **2026-04-20**: YAML/engine → Copilot SDK (PR #6)
- **2026-04-20**: Plugin manifest com registry dinâmico (SPEC 001)

## Reuniões

- 2026-04-17: Fundação Hydra — acesso repos, permissões, kickoff
- 2026-04-24: Criação de ambiente/plugin (KABA daily)
- 2026-04-29: Plugin e front-end isolado em desenvolvimento (KABA daily)
