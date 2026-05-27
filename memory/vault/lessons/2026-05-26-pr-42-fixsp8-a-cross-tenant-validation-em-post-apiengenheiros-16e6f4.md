---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/42"
date: 2026-05-26
subject: "PR #42 — fix(SP8-A): cross-tenant validation em POST /api/engenheiros"
author: unknown
cycle_time: 2m
tags: [segurança, validação, testes]

## O que aconteceu
Este PR corrige uma falha de segurança no endpoint `POST /api/engenheiros`, onde um admin não super_admin conseguia criar um engenheiro associado a múltiplos tenants, desde que um deles fosse o seu próprio tenant. A validação foi endurecida para exigir que todos os tenants informados pertençam ao admin.

## Decisão / Solução
Foi decidido mudar a validação de `Any()` para `All()`, garantindo que todos os tenants solicitados sejam do próprio admin. Além disso, foi adicionado um novo teste de integração para cobrir o cenário de combinação de tenants.

## Lessons
- Sempre valide se todos os elementos de uma lista atendem a uma condição específica ao invés de apenas um, para evitar falhas de segurança.
- Testes de integração são essenciais para garantir que cenários críticos sejam cobertos e que mudanças não introduzam regressões.
- Documentar mudanças de comportamento em endpoints é crucial para manter a clareza sobre como as permissões e validações funcionam.

## Source
https://github.com/living/delphos-svd/pull/42
