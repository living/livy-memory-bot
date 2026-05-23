---
type: lesson
source: github
source_ref: "living/RetailAuditProcessFunc/pull/26"
date: 2026-04-09
subject: "PR #26 — Correção de late binding closure"
author: unknown
cycle_time: 2m
tags: [bugfix, azure, python]

## O que aconteceu
Este PR ajusta o registro dinâmico de triggers do Azure Functions para evitar o problema de closure / late binding ao criar funções dentro de loops. Cada trigger agora possui uma função isolada e corretamente vinculada ao seu tópico ou fila correspondente.

## Decisão / Solução
Foi implementada a criação de factories para garantir que cada trigger tenha seu próprio wrapper com parâmetros fixos, evitando que todos os triggers executem com o mesmo tópico ou fila.

## Lessons
- Sempre que criar funções dentro de loops, utilize factories para evitar problemas de late binding.
- Mantenha a organização do código ao expor funções via `globals()`, garantindo que o runtime do Azure Functions funcione corretamente.
- Valide alterações de texto em mensagens de log para evitar introdução de typos que possam causar confusão.

## Source
https://github.com/living/RetailAuditProcessFunc/pull/26
