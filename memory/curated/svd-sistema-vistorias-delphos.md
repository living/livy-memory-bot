---
name: svd-sistema-vistorias-delphos
description: SVD = Sistema de Vistorias Delphos — evolução do svr-delphos (legado JS) para C#/.NET 10
type: projeto
date: 2026-04-30
project: living/delphos-svd
status: em_desenvolvimento
---

# SVD — Sistema de Vistorias Delphos

## O que é

**SVD = Sistema de Vistorias Delphos**. Evolui o sistema `svr-delphos` (JavaScript, 2025) para arquitetura moderna. Cliente: Delphos (vistorias remotas por vídeo).

**Contexto importante:** O acompanhamento do SVD acontece nas **reuniões diárias de KABA/BAT/BOT** — não há cadência dedicada. Isso significa que o progresso do SVD está entrelaçado com o cadência do KABA.

## Stack

- Backend: C# (.NET 10), Entity Framework Core
- Auth: Supabase JWT, RBAC (3 perfis)
- Banco: Supabase (PostgreSQL)
- Video: Vonage/OpenTok (sessão, tokens, archive)
- Mensageria: Azure Service Bus
- Frontend: PWA VideoCall, Web Shell + Design System
- Adapter IA: Hydra (comandos bidirecionais + session-events webhook)
- Infra: Docker-in-Docker (produção)

## Repos

| Repo | Descrição |
|---|---|
| `living/delphos-svd` | Projeto principal (C# .NET 10) |
| `living/svr-delphos` | Legado JavaScript (2025) |
| `living/livy-delphos-jobs` | Reports Vonage (Python, operacional) |

## PRs (cronologia)

| SP | PR | Data | Conteúdo | Linhas |
|---|---|---|---|---|
| SP1 | #2 | 2026-04-14 | Infra Core (.NET 10, EF Core, Docker) | +1.058 |
| SP2 | #4 | 2026-04-15 | Auth & RBAC (Supabase JWT, 3 perfis) | +3.196 |
| SP3 | #6 | 2026-04-17 | Vistorias Core (state machine, CRUD, Azure SB) | +13.024 |
| SP4 | #8 | 2026-04-20 | Video Vonage (sessão, tokens, archive, PWA) | +11.285 |
| SP5 | #9 | 2026-04-23 | Hydra Adapter (bidirecional + webhook) | +1.168 |
| SP6 | #12 | 2026-04-23 | Web Shell + Design System | +6.770 |
| SP6.5 | #13 | 2026-04-29 | Local Dev (Supabase, pgTAP, Playwright) | +41.595 |
| Deploy | #15 | open | DinD, nginx, compose | +352 |

## Decisões Técnicas

- **2026-04-17**: Hydra como adapter de IA — arquitetura de comandos bidirecionais
- **2026-04-20**: Vonage como provedor de video — mantém integração com pipeline existente
- **2026-04-22**: SP3 e SP4 com acompanhamento paralelo de bugs (BPA Email, Adapter Pipeline)

## Reuniões-chave

- **2026-04-17**: Fundação Hydra — acesso repos, permissões, kickoff SVD
- **2026-04-20**: Status Delphos — status geral
- **2026-04-29**: Status Kaba/BAT/BOT — SVD em deploy/produção

## Pendências

- PR #15 (Deploy DinD) open
- SVD em produção — colocar no ar
- Plugin e front-end isolado em desenvolvimento

## Referências

- Consolidação: `memory/consolidation/SVD-evolucao-completa.md`
- Trello: cards de estimative e priorização em DONE ✅
