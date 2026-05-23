---
type: lesson
subject: "PR #18 — Implementação de clientes de pipeline de pesquisa em lote com cadência"
author: unknown
date: 2026-04-18
cycle_time: 25m
tags: [pipeline, cadência, GitHub, TLDV, testes]

## O que aconteceu
Este PR introduziu um controle de cadência global para o pipeline de pesquisa, implementando clientes reais para polling do GitHub e TLDV, além de ajustar os crons para uma execução em lotes de 4 vezes ao dia. A cadência agora é adaptativa, aumentando o intervalo após alta volumetria e retornando ao normal após execuções saudáveis. Também foram adicionados testes robustos para garantir o comportamento do sistema.

## Decisão / Solução
Foi decidido implementar uma cadência global adaptativa que controla a frequência de execução do pipeline com base na volumetria de eventos. A implementação dos clientes do GitHub e TLDV foi feita para garantir a normalização dos eventos e a integração com o sistema. Os crons foram atualizados para refletir a nova cadência, e uma bateria de testes foi criada para validar as alterações.

## Lessons
- A cadência global pode simplificar o gerenciamento, mas deve ser monitorada para evitar que uma fonte barulhenta desacelere todo o sistema.
- A heurística de budget baseada em volume pode precisar de ajustes finos, pois não mede o custo real de tokens/API.
- É importante garantir que a documentação e os logs reflitam corretamente as mudanças na cadência para evitar confusões futuras.

## Source
https://github.com/living/livy-memory-bot/pull/18
