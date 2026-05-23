# SVD — Evolução Completa (Consolidação 2026-04-30)

> Consolidação cross-source: GitHub PRs + Trello Cards + TLDV Meetings + SSOT Claims
> Atualizado: 2026-04-30 com contexto dos meetings KABA/BAT

---

## O que é o SVD

**SVD = Sistema de Vistorias Delphos**

Cliente: **Delphos** (empresa de vistorias remotas/vídeo). O SVD é a evolução dos sistemas SVR/SOR da Delphos. O projeto substitui o legado `svr-delphos` (JavaScript, 2025) por uma arquitetura moderna em **C# (.NET 10)**.

**Contexto importante:** As **reuniões diárias de KABA/BAT/BOT** são usadas também para acompanhar o progresso do SVD — não há uma daily exclusiva do SVD. O time usa o cadência KABA para alinhar SVD junto com os outros projetos.

**Stack:**
- Backend: C# (.NET 10), Entity Framework Core
- Auth: Supabase JWT, RBAC com 3 perfis
- Banco: Supabase (PostgreSQL)
- Video: Vonage/OpenTok (sessão, tokens, archive)
- Mensageria: Azure Service Bus
- Frontend: PWA VideoCall, Web Shell com Design System
- IA Adapter: Hydra (comandos bidirecionais via webhook)
- Infra: Docker-in-Docker (deploy em produção)

**Repos:**
| Repo | Stack | Status |
|---|---|---|
| `living/delphos-svd` | C# (.NET 10) | Em desenvolvimento |
| `living/svr-delphos` | JavaScript | Legado (维护) |
| `living/livy-delphos-jobs` | Python/HTML | Operacional (reports Vonage) |

---

## Cronologia — PRs do delphos-svd

### SP1 — 2026-04-14 ✅
**Infra Core — .NET 10, EF Core, Serilog, Health Checks, Dockerfile**
- PR #2 | +1.058 −2 | autor: lincolnqjunior
- Setup inicial: .NET 10, Entity Framework Core, Serilog, Health Checks, container

### SP2 — 2026-04-15 ✅
**Auth & RBAC — Supabase JWT, CurrentTenant, 3 perfis, /auth/me**
- PR #4 | +3.196 −66 | autor: lincolnqjunior
- JWT via Supabase, CurrentTenant, 3 perfis de acesso

### SP3 — 2026-04-17 ✅
**Vistorias Core — state machine, endpoints CRUD, Espião/Ajudante, Azure Service Bus**
- PR #6 | +13.024 −56 | autor: lincolnqjunior
- Core da aplicação: state machine de vistorias, CRUD completo, módulos Espião e Ajudante

### SP4 — 2026-04-20 ✅
**Video Vonage — sessão, tokens, archive, PWA VideoCall**
- PR #8 | +11.285 −7 | autor: lincolnqjunior
- Integração Vonage: criação de sessão, tokens, archive, PWA VideoCall

### SP5 — 2026-04-23 ✅
**Hydra Adapter — bidirectional commands + session-events webhook**
- PR #9 | +1.168 −125 | autor: lincolnqjunior
- Adapter Hydra para comunicação bidirecional com session-events via webhook

### SP6 — 2026-04-23 ✅
**Web Shell + Design System + Auth**
- PR #12 | +6.770 −0 | autor: lincolnqjunior
- Shell web + design system + autenticação

### SP6.5 — 2026-04-29 ✅
**Local Dev Supabase + Seed Mascarado + pgTAP + Playwright Auth Real**
- PR #13 | +41.595 −113 | autor: lincolnqjunior
- Ambiente local: Supabase, seed mascarado, testes pgTAP, Playwright com autenticação real

### Deploy — 2026-04-30 🔄 (open)
**SVD DinD deployment — production config, Dockerfile, nginx, compose, scripts**
- PR #15 | +352 | autor: lincolnqjunior
- Docker-in-Docker, nginx, docker-compose para produção

---

## Cronologia — Reuniões (TLDV)

### 2026-04-17 — Fundação Hydra
- ID: `69e235dcf55c8200142fb060`
- **Marco zero do SVD** — alinhamento sobre acesso aos repos GitHub Hydra e SVD, permissões, criação de back-end
- Topics: acesso repositórios, permissões (Verciel/BS), criação de back-end
- Tags: `svd`, `hydra`

### 2026-04-20 — Status Delphos
- ID: `69e68e93f3efa5001387e5e0`
- Status geral Delphos
- Tags: `delphos`, `svd`

### 2026-04-22 — Status Geral
- Topics: SP4 Video Vonage, SP3 Vistorias Core + Espião/Ajudante, BPA de Envio de Email, Adapter Automação Pipeline
- **Indica que SP3 e SP4 estavam em paralelo com acompanhamento de bugs**

### 2026-04-29 — Status Kaba/BAT/BOT
- Topics: incidente de domínio não renovado, **status operacional de SVD sendo colocado no ar**, desenvolvimento de plugin e front-end isolado, discussão fila com Bruno Esteves
- **SVD em deploy/produção** — está sendo colocádo no ar

---

## Trello — Cards relacionados

| Card | Board | Lista | Status |
|---|---|---|---|
| Estimativa Evolução SVR - SOR | 6964f88... | DONE | ✅ Entregue |
| POC Delphos | — | Concluído 🎉 | ✅ Entregue |
| Reuniao Delphos | — | Concluído 🎉 | ✅ Entregue |
| Svr / Sor - Priorização de requisitos | 6964f88... | DONE | ✅ Entregue |

---

## Análise

### Velocidade
- **6 SPs em 9 dias** (SP1→SP6: 2026-04-14 a 2026-04-23)
- SP6.5 em mais 6 dias (até 2026-04-29)
- PR #15 (Deploy) open desde 2026-04-30
- Todas PRs por **lincolnqjunior** (único desenvolvedor)

### Arquitetura (inferida dos PRs + meetings)
```
delphos-svd (C# / .NET 10)
├── SP1: Infra Core (EF Core, Serilog, Docker)
├── SP2: Auth & RBAC (Supabase JWT, 3 perfis)
├── SP3: Vistorias Core (state machine, CRUD, Azure Service Bus)
├──     └── Espião / Ajudante (módulos de suporte)
├── SP4: Video Vonage (sessão, tokens, archive, PWA VideoCall)
├── SP5: Hydra Adapter (comandos bidirecionais, session-events webhook)
├── SP6: Web Shell + Design System
├── SP6.5: Local Dev (Supabase, pgTAP, Playwright)
└── Deploy: DinD, nginx, compose (open)
```

### Contexto operacional
- **Reuniões KABA/BAT como vehicle de acompanhamento SVD** — não há daily dedicada, o projeto é discutido no cadência do KABA
- SP3 e SP4 tiveram acompanha-mento paralelo com bugs (BPA Email, Adapter Pipeline)
- Deploy iniciado em 2026-04-30 com incidente de domínio expirado

---

## Pendências

- [ ] PR #15 (Deploy DinD) — open, aguardando merge
- [ ] SVD em produção — colocar no ar
- [ ] Plugin e front-end isolado — desenvolvimento em curso

---

_Last updated: 2026-04-30 21:31 UTC_
