---
type: lesson
source: trello
source_ref: "trello/6a0f01829b41bf9b3ded2184"
date: 2026-05-26
subject: "Trello: [TAR-11442] Lançamento manual de depositária não está permitindo quantidade decimal [B3/Listados]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3listados]
---

## O que aconteceu
O lançamento manual de depositária não estava permitindo a inserção de quantidades decimais. Ao tentar isentar uma cobrança pro rata com uma quantidade de 0,66, não foi possível realizar o ajuste devido à restrição do campo que aceita apenas valores inteiros.

## Decisão / Solução
Foi necessário investigar se havia uma forma de ajustar o sistema para permitir a inserção de quantidades decimais, a fim de facilitar o lançamento manual e evitar problemas em situações que exigem valores fracionários.

## Lessons
- A importância de permitir valores decimais em campos que podem requerer precisão, como em lançamentos financeiros.
- Necessidade de revisar e atualizar as restrições de campos em sistemas para atender a requisitos de negócios em evolução.

## Source
https://trello.com/c/TExDlPFA
