---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/7"
date: 2026-04-10
subject: "PR #7 — feat(vault): Wave B entity model (person/project/repo)"
author: unknown
cycle_time: 4m
tags: [arquitetura, rastreabilidade, segurança]

## O que aconteceu
Este PR evolui o **Memory Vault** para um modelo **domain-first** (Wave B), adicionando e documentando o contrato de entidades canônicas e reforçando a rastreabilidade e segurança na resolução de identidade. Foram introduzidos novos módulos e regras que garantem maior auditabilidade e qualidade.

## Decisão / Solução
A decisão foi padronizar o Vault em entidades canônicas e tornar a rastreabilidade obrigatória nos validadores, além de implementar guardrails para a resolução de identidade. Isso visa garantir que apenas entidades com evidências suficientes possam ser mescladas, aumentando a segurança e a qualidade do sistema.

## Lessons
- A implementação de requisitos obrigatórios, como o lineage, pode aumentar significativamente a auditabilidade e a consistência dos dados.
- A introdução de guardrails na resolução de identidade ajuda a prevenir merges indesejados, mas pode aumentar o número de casos que precisam de revisão manual.
- A documentação clara e acessível sobre as mudanças é essencial para garantir que todos os membros da equipe compreendam as novas regras e padrões.

## Source
https://github.com/living/livy-memory-bot/pull/7
