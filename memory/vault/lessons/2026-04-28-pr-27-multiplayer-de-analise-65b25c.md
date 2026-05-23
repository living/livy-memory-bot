---
type: lesson
source: github
source_ref: "living/RetailAuditProcessFunc/pull/27"
date: 2026-04-28
subject: "PR #27 — Multiplayer de analise"
author: unknown
cycle_time: 1d 5h
tags: [CI/CD, Azure, DLQ, desenvolvimento]

## O que aconteceu
Este PR ajusta o pipeline de CI/CD para publicar uma Azure Function App de homologação/local e corrige a rotina de reconciliação da DLQ para apontar para subscriptions dinâmicas por parceiro, em vez de uma subscription fixa. Também remove a dependência `azure-functions-durable` do `requirements.txt`.

## Decisão / Solução
Foi decidido separar o workflow de deploy para homologação, renomeando-o e ajustando as configurações necessárias. A lógica de reconciliação da DLQ foi alterada para utilizar subscriptions dinâmicas baseadas no nome do tópico, e a dependência `azure-functions-durable` foi removida para evitar problemas futuros.

## Lessons
- Sempre valide a convenção de nomenclatura dos tópicos para evitar falhas na lógica de parsing.
- Utilize interpolação de strings corretamente em logs para garantir que as informações sejam exibidas corretamente.
- Revise as dependências do projeto periodicamente para evitar que dependências não utilizadas causem problemas de runtime.

## Source
https://github.com/living/RetailAuditProcessFunc/pull/27
