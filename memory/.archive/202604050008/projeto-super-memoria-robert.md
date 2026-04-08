---
name: robert-super-memory-proposal
description: Expansão da memória agêntica da Living para o ecossistema Google Workspace usando ingestão multimodal, identity resolution e RAG sobre Gmail, Drive, WhatsApp e TLDV
type: project
date: 2026-04-05
project: livy-memory-bot
status: ativo
---

# Projeto: Super Memória Corporativa (Robert)

## Status

**ativo** — 2026-04-05

- ✅ Proposta registrada e analisada a partir do áudio do Robert (2026-04-03)
- ✅ Infra base existente já cobre ~60% do escopo via TLDV pipeline + Signal Cross-Curation + claude-mem/curated memory. Source: MEMORY.md#L62-L66
- ✅ Mapeamento técnico inicial pronto: componentes reaproveitáveis, extensões necessárias, novos coletores, schema e crons propostos
- 🟡 Projeto ainda está em fase de arquitetura/proposta — sem implementação dedicada no repositório até aqui
- 🟡 TLDV continua sendo a perna multimodal mais madura e o núcleo técnico mais reaproveitável
- 🔴 Gaps principais seguem abertos: Google Auth (Domain-wide Delegation), identity resolution global e custo/infra para parsing multimodal

## Contexto

Robert propôs (via áudio) na tarde de 2026-04-03 a criação de uma **Super Memória Corporativa** que unifique toda a comunicação digital da Living. O sistema deve englobar:

- E-mails corporativos (Gmail)
- Google Drive / Docs / anexos
- WhatsApp
- Atas e transcrições de reunião (TLDV)

Meta declarada: ter um grande banco central pesquisável por funcionários e material demonstrável para parceiros/sócios no evento da 4D em Petrópolis.

## Motivação

A proposta nasce da perda de contexto em silos separados:

- decisões em reuniões ficam no TLDV,
- confirmação formal fica em e-mail,
- execução operacional fica em WhatsApp/Telegram,
- documentos e planilhas vivem no Drive.

A visão do Robert é usar o stack atual da Livy Memory como **núcleo agêntico** e expandi-lo para o restante do ecossistema institucional.

## Estado Atual (o que já existe)

O projeto não parte do zero. A arquitetura atual de memória (`workspace-livy-memory`) possui forte sinergia com o `livy-tldv-jobs` e com a stack de memória institucional já operacional.

### Infra reaproveitável já existente

1. **TLDV ingest pipeline**
   - `discover.py` + `enrich.py` já fazem descoberta, orquestração e resumo de reuniões.
   - O state machine do TLDV já é o embrião natural para receber novos `source=` além de `tldv`.

2. **Archive / multimídia**
   - `archive_videos.py` já arquiva material bruto de reuniões.
   - `whisper_client.py` já foi migrado para API-first, evitando repetir o erro de Whisper local/OOM no VPS.

3. **Signal Cross-Curation / memória agêntica**
   - O agente de memória já cruza sinais de reuniões, GitHub, Telegram/WhatsApp e curated memory.
   - A arquitetura de 3 camadas já existe: observations → curated → operational.

4. **Observability / Gateway / Skills**
   - Há infraestrutura de cron, gateway, plugin claude-mem, skills e docs para suportar expansão incremental. Source: observation #3510.

## Análise de Integração com o Ecossistema Atual

### A lacuna que a proposta tenta fechar

A arquitetura atual ainda ignora grande parte da comunicação formal e documental da empresa:

- e-mails institucionais;
- documentos estáticos do Drive (DOCX, XLSX, PPTX, PDF);
- anexos e artefatos ligados a decisões;
- identidade unificada da mesma pessoa em múltiplos sistemas.

Hoje, se a Livy precisa responder algo como _"qual e-mail formal confirmou a decisão tomada naquela reunião e quem executou depois no WhatsApp?"_, o sistema ainda não consegue responder de forma consistente.

### Proposta técnica-base: ingestão multimodal + RAG

O conceito proposto usa **RAG-Anything** como mecanismo de ingestão multimodal para reduzir o custo de criar pipelines diferentes por tipo de documento.

Capacidades desejadas:
- OCR/extração para documentos e imagens;
- parsing de tabelas/planilhas/relatórios;
- indexação relacional cruzando Gmail, Drive, WhatsApp e TLDV;
- busca híbrida por evento, pessoa, documento e decisão.

## Cruzamento Detalhado com `livy-tldv-jobs`

O repo `living/livy-tldv-jobs` é a peça central que já resolve a ingestão de reuniões. Abaixo o mapeamento de como cada componente existente se conecta (ou precisa ser estendido) para a Super Memória.

### Componentes reaproveitáveis (já prontos)

| Componente | Path | O que faz hoje | Papel na Super Memória |
|---|---|---|---|
| `discover.py` | `ingest_worker/jobs/` | Polling na API tl;dv, cria `enrichment_jobs` no Supabase | Continua como fonte primária de reuniões |
| `enrich.py` | `ingest_worker/jobs/` | State machine `pending→enriched`, orquestra download+transcrição+resumo | Pode virar orquestrador central para `source=gmail` e `source=gdrive` |
| `summarizer.py` | `ingest_worker/lib/` | Gera resumos AI | Reutilizável para e-mails longos e documentos |
| `github_client.py` | `ingest_worker/lib/` | Coleta PRs/issues para contexto | Continua alimentando cross-curation |
| `whisper_client.py` | `ingest_worker/lib/` | Transcrição API-first | Reutilizável para áudios WhatsApp/voicemails |
| `video_archiver.py` | `ingest_worker/lib/` | HLS→MP4 + Azure Blob | Pode arquivar Google Meet, se integrado |
| `living_memory_client.py` | `ingest_worker/lib/` | Envia observações para claude-mem | Continua como saída para memória de longo prazo |
| `circuit_breaker.py` | `ingest_worker/lib/` | Proteção para APIs externas | Essencial para Google APIs e quotas |

### Componentes que precisam de extensão

| Componente | Extensão Necessária | Complexidade |
|---|---|---|
| `supabase_client.py` | Novas tabelas: `gmail_messages`, `drive_documents`, `identity_map` | Média |
| `enrich.py` | Novos branches para `source=gdrive` e `source=gmail` | Média |
| `meetings_denormalized` | Incluir cross-references com docs/e-mails | Baixa |
| Web SPA (`web/`) | Abas “Documentos” e “E-mails”, filtros cross-modal | Alta |

### Componentes totalmente novos (a criar)

| Componente | Descrição | Onde vive |
|---|---|---|
| `google_auth.py` | OAuth2 service account + Domain-wide Delegation | `ingest_worker/lib/` |
| `gmail_collector.py` | Polling/push Gmail API, corpo + anexos | `ingest_worker/lib/` |
| `gdrive_collector.py` | Varredura incremental do Drive | `ingest_worker/lib/` |
| `document_parser.py` | Wrapper do RAG-Anything para DOCX/XLSX/PPTX/PDF | `ingest_worker/lib/` |
| `identity_resolver.py` | Reconcilia email / telegram / whatsapp / tldv / github | `ingest_worker/lib/` |
| `jobs/discover_google.py` | Discovery para Gmail + Drive | `ingest_worker/jobs/` |

## Fluxo de Dados Proposto (End-to-End)

```text
TLDV API / Gmail API / Google Drive / WhatsApp-Telegram
            ↓
      enrich.py (state machine multi-source)
            ↓
 summarizer / whisper_client / document_parser
            ↓
      Supabase + identity_map
            ↓
 Signal Cross-Curation / busca vetorial / Web SPA
            ↓
   MEMORY (curated) + observations + dashboards
```

## Schema Existente vs Necessário

### Já existe (base TLDV / memória)

- `meetings`
- `summaries`
- `meeting_transcript_segments`
- `enrichment_jobs`
- `meeting_prs`
- `meeting_cards`
- `meeting_feedback`

### Precisa criar

- `gmail_messages`
- `drive_documents`
- `identity_map`
- expansão de `enrichment_jobs.source` para `gmail | gdrive`

## Crons: atual vs proposto

### Crons atuais reaproveitáveis

| Cron Atual | Schedule | Papel |
|---|---|---|
| `enrich-discover` | hourly :00 | Descobre reuniões TLDV |
| `enrich-process` | hourly :30 | Processa jobs pendentes |
| `tldv-archive-videos` | 03:00 BRT | Arquiva vídeos |
| `signal-curation` | 4h | Cruza sinais TLDV + GitHub + logs |

### Crons novos propostos

| Cron Novo | Schedule | Papel |
|---|---|---|
| `google-discover-gmail` | hourly :15 | Varredura incremental Gmail |
| `google-discover-drive` | 2h :45 | Varredura incremental Drive |
| `identity-sync` | daily 02:00 | Reconcilia `identity_map` |

---

## Decisões

### 2026-04-03 — Super Memória Corporativa como expansão do núcleo já existente

**Decisão:** Tratar a proposta do Robert como expansão da arquitetura atual da Livy Memory, não como um sistema totalmente novo.

**MOTIVO:** A infra base já cobre parte relevante do problema: TLDV pipeline, signal cross-curation, claude-mem, curated memory e gateway já existem. Reaproveitar o núcleo atual reduz risco, acelera prova de valor e evita reconstruir ingestão, memória e observability do zero. Source: MEMORY.md#L62-L66.

### 2026-04-03 — TLDV como primeira perna multimodal do projeto

**Decisão:** Manter o `livy-tldv-jobs` como base técnica da expansão multimodal.

**MOTIVO:** O TLDV já possui discovery, enrichment, summarization, state machine, archiving e integração com memória institucional. Ele é a parte mais madura da stack para ingestão de conteúdo semi-estruturado e já resolve o eixo “reuniões”, que é o backbone natural para cruzar depois com e-mail e documentos.

### 2026-04-03 — Google Workspace entra como novos sources do orchestrator

**Decisão:** Expandir o orquestrador atual para aceitar `source=gmail` e `source=gdrive`, em vez de criar pipelines completamente separados.

**MOTIVO:** O pattern de `discover → enrich → summarize → persist` já existe e foi validado no TLDV. Reutilizar o mesmo state machine reduz complexidade operacional, facilita observability e concentra retry/circuit breaker em um fluxo conhecido.

### 2026-04-03 — Identity resolution é requisito estrutural, não melhoria opcional

**Decisão:** Criar uma tabela/serviço global de identidade corporativa (`identity_map`) como parte central do projeto.

**MOTIVO:** Sem reconciliar e-mail, participante do TLDV, Telegram, WhatsApp e GitHub para a mesma pessoa, a memória corporativa vira um conjunto de silos paralelos apenas indexados. O valor do projeto depende justamente do cruzamento entre atores, documentos, reuniões e execução.

### 2026-04-03 — Parsing multimodal pesado não deve nascer acoplado ao VPS principal

**Decisão:** Tratar RAG-Anything / MinerU / LibreOffice como carga potencialmente separada do host principal.

**MOTIVO:** O histórico recente do TLDV mostrou que processamento local pesado (ex.: Whisper local) degrada a VPS. Repetir esse padrão com OCR multimodal pode comprometer a operação. A proposta correta é isolar em container dedicado ou delegar parsing para API externa quando necessário.

---

## Pendências

- [ ] Validar com Robert o escopo exato do MVP para o evento da 4D (demo vs produto interno)
- [ ] Definir se a primeira entrega prioriza Gmail, Drive ou identity resolution
- [ ] Criar Google Cloud Project interno com strategy para Domain-wide Delegation
- [ ] Modelar schema inicial de `gmail_messages`, `drive_documents` e `identity_map`
- [ ] Decidir se o parsing multimodal roda em container isolado ou API externa
- [ ] Popular/normalizar identidades de participantes do TLDV para viabilizar reconciliação com e-mail e mensageria
- [ ] Rever dependência mencionada de ChromaDB à luz da arquitetura mais recente do TLDV, que já substituiu pgvector por OpenClaw subprocess + claude-mem HTTP em partes da stack

## Bugs

### Não há bugs de implementação registrados ainda

O projeto ainda está em fase de proposta/arquitetura. Os riscos atuais são de desenho e infraestrutura, não bugs de código do próprio projeto.

### Riscos técnicos já identificados

| Risco | Impacto | Mitigação |
|---|---|---|
| Google OAuth / scopes | Bloqueia acesso institucional ao Workspace | Usar app interno + Domain-wide Delegation |
| Rate limit / quotas do Gmail | Discovery inconsistente ou lento | Aplicar `circuit_breaker.py` e backoff |
| Carga de OCR multimodal no VPS | Instabilidade / OOM / degradação geral | Isolar em container ou usar API externa |
| `meeting_participants` insuficiente | Identity resolution falha | Popular dados via TLDV API ou reconciliação manual inicial |
| Cron/enum/schema novos | Aumento de complexidade operacional | Expandir gradualmente sobre o orchestrator existente |

## Cross-references

- [livy-memory-agent.md](livy-memory-agent.md) — núcleo da memória institucional e curadoria
- [tldv-pipeline-state.md](tldv-pipeline-state.md) — base técnica mais próxima para expansão multimodal
- [claude-mem-observations.md](claude-mem-observations.md) — camada 1 da memória observacional
- [openclaw-gateway.md](openclaw-gateway.md) — infraestrutura de cron, canais e integração

## Notas operacionais

- Ao alterar a ingestão do TLDV, tratar esse projeto como dependente do roadmap maior de memória corporativa.
- A proposta é institucional e transversal — não pertence só ao agente de memória, mas o agente de memória é o núcleo técnico mais próximo do problema.
- O arquivo original foi preservado conceitualmente: o conteúdo de análise, componentes reaproveitáveis, schema, crons e riscos foi reestruturado, não descartado.

## Regras aprendidas

- `super-memory-reuse-core`: não propor greenfield quando o TLDV + memory stack já resolvem grande parte do problema
- `identity-first`: sem identity resolution global, “memória corporativa” vira apenas indexação dispersa
- `multimodal-heavy-workloads`: OCR/parsing pesado não deve estrear acoplado ao host principal
- `google-as-source`: Gmail e Drive devem entrar como novos `source=` do orquestrador, não como pipelines paralelos isolados
- `event-demo-scope`: proposta para evento precisa de MVP explícito — não assumir escopo total como entrega imediata
