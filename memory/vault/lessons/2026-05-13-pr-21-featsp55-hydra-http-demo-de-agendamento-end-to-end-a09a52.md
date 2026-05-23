---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/21"
date: 2026-05-13
subject: "PR #21 — feat(sp5.5): Hydra HTTP + demo de agendamento end-to-end"
author: unknown
cycle_time: 1h 44m
tags: [agendamento, integração, performance]

## O que aconteceu
Este PR implementa o fluxo SP5.5 de agendamento end-to-end via Hydra, substituindo a integração anterior com Azure Service Bus por um adapter HTTP e um webhook inbound. Foram adicionados novos endpoints e melhorias na infraestrutura, performance e segurança.

## Decisão / Solução
A decisão foi migrar a integração para HTTP, simplificando a infraestrutura e melhorando a resiliência. Foi criado um novo endpoint para propor agendamentos e um webhook para receber eventos do Hydra, além de ajustes na autenticação e na performance das APIs.

## Lessons
- A migração de integrações para HTTP pode simplificar a infraestrutura e melhorar a resiliência do sistema.
- A validação de dados de entrada, como a exigência de IDs únicos, é crucial para garantir a integridade dos processos de negócio.
- A implementação de idempotência em handlers de eventos é fundamental para evitar reprocessamentos indesejados.

## Source
https://github.com/living/delphos-svd/pull/21
