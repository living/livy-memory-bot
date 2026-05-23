---
type: lesson
source: github
source_ref: "living/elcano-robo-ocr/pull/43"
date: 2026-05-12
subject: "PR #43 — feat: MongoDB resilience with circuit breaker, watchdog and Sentry"
author: unknown
cycle_time: 3h 20m
tags: [resiliência, observabilidade, MongoDB, Sentry]

## O que aconteceu
Este PR adiciona uma camada de resiliência e observabilidade para o MongoDB e para o pipeline de jobs do Robo OCR, implementando circuit breaker, watchdog, health check mais eficiente e integração real com Sentry. Além disso, novos testes foram incluídos para validar cenários de falha e recuperação do MongoDB.

## Decisão / Solução
Foi decidido criar um `MongoConnectionManager` para gerenciar conexões com o MongoDB, implementando funcionalidades como ping com timeout, retries e circuit breaker. Um serviço de watchdog foi adicionado para monitorar a disponibilidade do MongoDB, e o health check foi otimizado para retornar um status 503 quando o MongoDB estiver indisponível. A integração com Sentry foi aprimorada para capturar erros e breadcrumbs relevantes.

## Lessons
- Implementar circuit breakers e retries pode aumentar significativamente a resiliência de sistemas que dependem de serviços externos, como bancos de dados.
- A observabilidade deve ser uma prioridade, utilizando ferramentas como Sentry para capturar erros e monitorar eventos críticos.
- Testes automatizados são essenciais para garantir que novas funcionalidades não introduzam falhas, especialmente em cenários de erro e recuperação.

## Source
https://github.com/living/elcano-robo-ocr/pull/43
