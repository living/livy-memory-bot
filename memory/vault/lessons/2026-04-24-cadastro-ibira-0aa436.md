---
type: lesson
date: 2026-04-24
subject: "Trello: Cadastro - IBIRA [B3/BancoB3]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3bancob3]
---

## O que aconteceu
Temos um cliente que saiu no final do ano passado e voltou agora. Sempre que o cliente sai, alteramos o estado da conta para “fechado”. Não conseguimos alterar o estado do “cliente” para ativo, mas conseguimos com a “carteira”. Abrimos um novo cadastro e migramos as “carteira”.

## Decisão / Solução
Notamos que, ao calcular a tarifação, o valor foi lançado duas vezes, aparentemente um para cada cliente. Além disso, os dados bancários no arquivo de débito vieram com o ID do cliente inativado. Precisamos ajustar esses pontos para evitar duplicidade e garantir que os dados corretos sejam utilizados.

## Lessons
- É importante revisar o processo de reativação de clientes para garantir que os estados das contas e carteiras sejam atualizados corretamente.
- A validação dos dados bancários deve ser feita para evitar que informações de clientes inativados sejam utilizadas.

## Source
https://trello.com/c/iftrQHqM
