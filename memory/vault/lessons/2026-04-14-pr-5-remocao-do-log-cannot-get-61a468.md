---
type: lesson
source: github
source_ref: "living/Multilogger/pull/5"
date: 2026-04-14
subject: "PR #5 — Remoção do log Cannot GET"
author: unknown
cycle_time: 0m
tags: [logging, error-handling]

## O que aconteceu
Este PR ajusta o comportamento de logging de erros para ignorar erros do tipo "Cannot GET /...", que são comuns em rotas não encontradas, evitando a poluição nos logs de erro. Também foi feito um ajuste de formatação em uma constante de configuração.

## Decisão / Solução
Foi decidido implementar um filtro que ignora mensagens de erro que contenham "Cannot GET /", redirecionando essas mensagens para um `console.log` em vez de seguir o fluxo padrão de erro. Isso melhora a observabilidade e a triagem de incidentes.

## Lessons
- Implementar filtros de log pode reduzir o ruído e melhorar a eficácia na identificação de erros reais.
- Sempre que possível, documentar mudanças de comportamento para evitar confusões futuras na equipe.
- Testar alterações de logging em diferentes cenários é essencial para garantir que erros legítimos não sejam descartados.

## Source
https://github.com/living/Multilogger/pull/5
