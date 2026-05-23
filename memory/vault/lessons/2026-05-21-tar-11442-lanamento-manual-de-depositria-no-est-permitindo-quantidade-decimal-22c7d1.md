---
type: lesson
source: trello
source_ref: "trello/6a0f01829b41bf9b3ded2184"
date: 2026-05-21
subject: "Trello: [TAR-11442] Lançamento manual de depositária não está permitindo quantidade decimal [B3/Listados]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3listados]
---

## O que aconteceu
O lançamento manual de depositária não estava permitindo a inserção de quantidades decimais, o que impediu o ajuste de uma cobrança pro rata com uma quantidade de 0,66.

## Decisão / Solução
Foi necessário verificar se existia uma forma de ajustar o sistema para permitir a inserção de quantidades decimais no campo de quantidade, a fim de facilitar o lançamento de valores que não são inteiros.

## Lessons
- A limitação de campos inteiros pode causar problemas em lançamentos financeiros que necessitam de precisão decimal.
- É importante considerar a flexibilidade dos campos em sistemas financeiros para evitar obstáculos em operações comuns.

## Source
https://trello.com/c/TExDlPFA
