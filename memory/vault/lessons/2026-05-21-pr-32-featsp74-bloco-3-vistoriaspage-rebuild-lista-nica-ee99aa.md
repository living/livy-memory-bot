---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/32"
date: 2026-05-21
subject: "PR #32 — feat(SP7.4 Bloco 3): VistoriasPage rebuild (lista única)"
author: unknown
cycle_time: 1d 1h
tags: [frontend, backend, UX, API]

## O que aconteceu
Este PR finaliza o **SP7.4 Bloco 3 — Rebuild da VistoriasPage**, substituindo a listagem antiga por uma tabela única pixel-perfect, com novos filtros e melhorias na experiência do usuário. Além disso, foram feitas alterações no backend para suportar essas novas funcionalidades.

## Decisão / Solução
A decisão foi de reconstruir a interface da VistoriasPage para uma tabela que oferece uma melhor experiência ao usuário, além de implementar novos endpoints no backend para fornecer contagens e filtros adequados. O painel de "Próximas vistorias" também foi ajustado para refletir a fila operacional.

## Lessons
- A implementação de uma tabela em vez de cards pode melhorar significativamente a usabilidade e a eficiência na visualização de dados.
- É crucial garantir que os filtros aplicados no frontend sejam consistentes com os dados retornados pelo backend para evitar confusões.
- A lógica de derivação de estados (como "atrasada") deve ser cuidadosamente considerada, pois pode impactar a performance e a precisão dos dados apresentados.

## Source
https://github.com/living/delphos-svd/pull/32
