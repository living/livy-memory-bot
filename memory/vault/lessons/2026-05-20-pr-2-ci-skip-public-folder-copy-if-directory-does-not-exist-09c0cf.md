---
type: lesson
source: github
source_ref: "living/insight-funds/pull/2"
date: 2026-05-20
subject: "PR #2 — ci: skip public folder copy if directory does not exist"
author: unknown
cycle_time: 0m
tags: [ci, deploy, resiliente]

## O que aconteceu
Ajuste nos workflows de deploy para evitar falha quando a pasta `dashboard-ui/public` não existe. O step de cópia do `public` agora é condicional, tornando o pipeline mais resiliente.

## Decisão / Solução
Foi decidido que o pipeline de deploy deve verificar se a pasta `public` existe antes de tentar copiá-la, evitando falhas em cenários onde o diretório não está presente.

## Lessons
- Implementar verificações condicionais em scripts de CI/CD pode aumentar a resiliência do pipeline e evitar falhas desnecessárias.
- Manter consistência nas alterações entre ambientes de homologação e produção é crucial para evitar comportamentos inesperados.
- Sempre documentar as mudanças feitas em workflows para facilitar a compreensão e manutenção futura.

## Source
https://github.com/living/insight-funds/pull/2
