---
type: lesson
date: 2026-05-19
subject: "Trello: SP 7.3 Ajustes Pós Demo [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
Este cartão representa a necessidade de endereçar lacunas de UX identificadas durante a demonstração de 2026-05-15 e a entrega de um simulador para o SINDelphos que não depende da integração real com o Engedelphos.

## Decisão / Solução
Foi decidido implementar três blocos independentes em commits separados: (1) um simulador SINDelphos com endpoints protegidos por feature-flag e guardas de cross-tenant, (2) melhorias rápidas na interface do usuário nos componentes `AppHeader`, `VistoriaCard` e painel, e (3) um novo componente `DateTimeChip` com fuso horário fixo em `America/Sao_Paulo`, além da remoção do legado `Periodo` e publicação de três DTOs/eventos via `IHydraEventPublisher`.

## Lessons
- A implementação de feature-flags permite testar novas funcionalidades sem impactar todos os usuários, facilitando a identificação de problemas de UX antes do lançamento completo.
- A divisão de tarefas em blocos independentes ajuda a organizar o trabalho e a facilitar a revisão de código, além de permitir entregas incrementais.

## Source
https://trello.com/c/EBmFrHXI
