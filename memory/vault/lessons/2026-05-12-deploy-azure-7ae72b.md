---
type: lesson
date: 2026-05-12
subject: "Trello: Deploy - Azure [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
O cartão representa o processo de implantação da aplicação SVD (API + frontend) no ambiente de teste Docker-in-Docker da Living, utilizando um banco de dados na nuvem Supabase.

## Decisão / Solução
A arquitetura foi definida com Nginx como ponto de entrada único, servindo a aplicação React SPA e fazendo proxy para a API .NET 10. A orquestração foi realizada com `docker compose`, utilizando arquivos múltiplos e sobreposições para produção. Um script de migração aplicou o esquema e os dados iniciais ao Supabase, utilizando um container do PostgreSQL para evitar a instalação local do psql.

## Lessons
- A utilização de Nginx como proxy reverso simplificou a gestão de rotas entre o frontend e a API, melhorando a performance e a segurança.
- A abordagem de usar `docker run` para executar o PostgreSQL durante a migração evitou dependências locais, facilitando o processo de implantação em diferentes ambientes.

## Source
https://trello.com/c/Ssafmrdu
