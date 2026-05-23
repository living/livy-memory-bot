---
type: lesson
date: 2026-05-13
subject: "Trello: Otimizar Cerc_func_ResumoOnlineBill [CERC/Billing]"
effort: Not specified
pr_refs: [none]
tags: [trello, cercbilling]
---

## O que aconteceu
A função Cerc_func_ResumoOnlineBill precisa ser otimizada devido à sua chamada na view Cerc_view_NumDocCompartilhado, que lista id_sess de todas as PVs de tarifação sem critérios de filtro, resultando em baixa performance e ocorrências de timeout.

## Decisão / Solução
Foi identificado que o processo de conta é impactado, especialmente quando há mudanças no comentário da conta, levando a timeouts após 600 segundos de espera. A otimização da função é necessária para melhorar a performance e evitar esses problemas.

## Lessons
- A falta de filtros em consultas pode levar a sérios problemas de performance, especialmente em sistemas com grandes volumes de dados.
- É crucial monitorar e otimizar funções que impactam diretamente processos críticos para evitar timeouts e melhorar a eficiência do sistema.

## Source
https://trello.com/c/A4owdC4A
