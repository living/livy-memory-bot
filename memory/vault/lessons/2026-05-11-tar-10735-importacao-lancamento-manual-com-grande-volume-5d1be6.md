---
type: lesson
date: 2026-05-11
subject: "Trello: [TAR-10735] Importacao lancamento manual com grande volume [B3/Balcão]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3balco]
---

## O que aconteceu
Uma planilha com 9MB e um pouco mais de 263mil registros gerou erro de OutOfMemory na importacao de lancamento manual de Operacoes.

## Decisão / Solução
Foi necessário revisar o processo de importação para lidar com grandes volumes de dados, evitando erros de memória.

## Lessons
- A necessidade de otimizar a importação de grandes volumes de dados para prevenir erros de memória.
- A importância de testar a importação com diferentes tamanhos de arquivo para identificar limitações do sistema.

## Source
https://trello.com/c/O4JjW9Zn
