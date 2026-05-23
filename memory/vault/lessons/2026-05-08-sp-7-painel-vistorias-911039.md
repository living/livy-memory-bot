---
type: lesson
date: 2026-05-08
subject: "Trello: SP 7 - Painel Vistorias [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
Foi criado um painel operacional para vistorias que inclui funcionalidades de busca, contadores de fase e cards de vistoria com ações de Entrar e Espiar.

## Decisão / Solução
A arquitetura escolhida para o painel é uma SPA utilizando React 19 e Vite 6, com integração do TanStack Query para gerenciamento de dados. A aplicação realiza fetch completo no lado do cliente e implementa filtros client-side, permitindo buscas complexas. O backend é construído com .NET 10, utilizando Minimal APIs para suporte a buscas multi-campo com `ILike`.

## Lessons
- A escolha de uma SPA com React e Vite permite um desenvolvimento mais ágil e uma experiência de usuário mais fluida.
- A implementação de polling a cada 30 segundos, exceto para itens em andamento, garante que os dados sejam atualizados frequentemente sem sobrecarregar o servidor.

## Source
https://trello.com/c/FDJiAmLs
