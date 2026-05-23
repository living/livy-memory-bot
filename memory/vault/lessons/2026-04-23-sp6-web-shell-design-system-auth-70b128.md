---
type: lesson
date: 2026-04-23
subject: "Trello: SP6 — Web Shell + Design System + Auth [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
A equipe definiu a arquitetura e as tecnologias para a criação da aplicação React 19 com Vite 6, que incluirá um design system brutalista, autenticação via Supabase e um shell de navegação.

## Decisão / Solução
A aplicação será estruturada em `src/SVD.Web/`, utilizando Vite 6 como SPA, com autenticação via JWT do Supabase. A comunicação com a API será feita através de um proxy em desenvolvimento e como arquivos estáticos em produção.

## Lessons
- A escolha de Vite 6 e React 19 proporciona uma base moderna e eficiente para o desenvolvimento da aplicação.
- A implementação do design system desde o início facilita a consistência visual e a reutilização de componentes.

## Source
https://trello.com/c/7WTTPX0K
