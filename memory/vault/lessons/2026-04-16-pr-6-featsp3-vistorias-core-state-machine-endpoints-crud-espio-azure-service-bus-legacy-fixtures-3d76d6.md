---
type: lesson
subject: "PR #6 — Vistorias Core — state machine, endpoints CRUD, Espião, Azure Service Bus, legacy fixtures"
author: unknown
date: 2026-04-16
cycle_time: 5h 27m
tags: [backend, arquitetura, Azure, mensageria, testes]

## O que aconteceu
Este PR implementa o **SP3 — Vistorias Core** no backend, adicionando um modelo de domínio completo, novos endpoints CRUD, registro de eventos e reagendamentos, além de um módulo de observação. A dependência de **RabbitMQ** foi substituída pelo **Azure Service Bus Emulator** e uma CLI foi incluída para extrair fixtures do legado.

## Decisão / Solução
A decisão foi integrar uma nova máquina de estados para gerenciar as transições de vistorias e reestruturar a API para suportar novos endpoints e DTOs. A migração para o Azure Service Bus foi feita para melhorar a infraestrutura e a comunicação entre serviços. Além disso, foram implementadas novas ferramentas para facilitar a extração e sanitização de dados legados.

## Lessons
- A migração de mensageria pode impactar significativamente o ambiente de desenvolvimento; é crucial documentar e comunicar essas mudanças para a equipe.
- A implementação de uma máquina de estados ajuda a manter a lógica de transição clara e facilita a manutenção do código.
- A inclusão de testes automatizados e a estabilização do pipeline de CI são essenciais para garantir a qualidade e a confiabilidade do sistema após grandes alterações.

## Source
https://github.com/living/delphos-svd/pull/6
