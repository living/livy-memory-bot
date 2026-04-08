---
name: robert-super-memory-proposal
description: Documenta a iniciativa do Robert de expandir a memória agentica atual (que engloba TLDV, GitHub, Telegram e WhatsApp) para o ecossistema Google Workspace usando RAG multimodal (RAG-Anything)
type: project
date: 2026-04-03
---

# Projeto: Super Memória Corporativa (Robert)

**Fato/Decisão:** Robert propôs (via áudio) na tarde de 2026-04-03 a criação de uma "Super Memória Corporativa" que unifique toda a comunicação digital da Living. O sistema deve englobar: E-mails corporativos (Gmail), Google Drive/Docs, WhatsApp e Atas de Reunião (TLDV). A meta é ter um grande banco central pesquisável por todos os funcionários e que o projeto seja apresentado a parceiros/sócios em um evento na 4D em Petrópolis na próxima semana.

**Why:** A empresa tem uma grande perda de informações espalhadas em silos (Google Drive vs WhatsApp vs Reuniões no TLDV). O Robert percebeu que a pipeline do Livy Memory Agent (que já captura WhatsApp, Telegram e usa a base do TLDV) poderia ser o núcleo ("cérebro agêntico") para conectar todo o resto.

**How to apply:** Ao sugerir novas integrações na arquitetura de memória, lembre-se que o roadmap primário da diretoria agora envolve conectar o Google Workspace. Se for alterar a ingestão do TLDV, lembre-se que ele é a primeira perna multimodal desse ecossistema maior.

## Análise de Integração com o Ecossistema Atual

### O Estado Atual (O que já temos)
O projeto não parte do zero. A arquitetura atual de memória (`workspace-livy-memory`) possui forte sinergia com o `livy-tldv-jobs`:
1. **`ingest_worker` (TLDV)**: Possui jobs como `discover.py` e `enrich.py` rodando assíncronos que pegam reuniões brutas da API do gw.tldv.io e geram resumos consolidados no Supabase.
2. **`archive_videos.py`**: Já roda via ffmpeg subindo vídeos das reuniões (HLS) para o Azure Blob, garantindo backup do MP4 oficial.
3. **`Signal Cross-Curation` (Memory Agent)**: Roda a cada 4 horas (`curation_cron.py`), puxando as decisões (Priority 1) do Supabase do TLDV, cruzando com PRs no GitHub e mensagens no Telegram/WhatsApp. O TLDV fornece o contexto semântico das decisões, a mensageria e o código confirmam o estado.

### A Lacuna (Onde a Ideia do Robert Entra)
A arquitetura atual ignora tudo que acontece em e-mails formais institucionais e documentos estáticos (PPT, planilhas) armazenados no Google Drive. Se a Livy precisa cruzar uma decisão da ata da reunião com o e-mail formal que disparou a alteração do contrato, hoje ela não consegue.

### A Proposta Técnica: RAG-Anything
Para plugar os silos do Google Workspace, o projeto propõe o uso do **RAG-Anything**:
- **Framework Multimodal**: Ao invés de plugar uma pipeline customizada que quebre para cada tipo de documento, o RAG-Anything resolve a Ingestão Universal.
- Ele usa OCR profundo via MinerU e LibreOffice, extraindo não só texto, mas tabelas de relatórios financeiros e analisando imagens de slides de apresentação.
- Gera um *Knowledge Graph* multimodal, permitindo que a busca híbrida cruze e-mails com as transcrições de reuniões do TLDV de forma relacional, respondendo: "Que e-mail foi enviado após a decisão da reunião de ontem?".

### Desafios Técnicos Identificados
1. **Google Auth**: Necessidade de criar um Google Cloud Project interno para usar *Domain-wide Delegation* sem auditoria externa.
2. **Identity Resolution**: O `ingest_worker` do TLDV atualmente puxa participantes, mas precisamos cruzar que o ID da pessoa na reunião do TLDV é a mesma que enviou a mensagem no Telegram e responde pelo e-mail "andre@livingnet.com.br". Essa tabela de identidades corporativas unificada ainda não existe de forma global.
3. **Poder Computacional**: O uso do Whisper local causava instabilidade na VPS; logo, rodar frameworks OCR multimodais pesados como o MinerU/RAG-Anything localmente exigirá cuidados de performance no servidor Hostinger (provavelmente rodar em containers separados ou delegar carga para API).

---

## Cruzamento Detalhado com `livy-tldv-jobs`

O repo `living/livy-tldv-jobs` é a peça central que já resolve a ingestão de reuniões. Abaixo o mapeamento de como cada componente existente se conecta (ou precisa ser estendido) para a Super Memória.

### Componentes Reaproveitáveis (já prontos)

| Componente | Path | O que faz hoje | Papel na Super Memória |
|---|---|---|---|
| `discover.py` | `ingest_worker/jobs/` | Polling na API tl;dv, cria `enrichment_jobs` no Supabase | Continua como está — fonte primária de reuniões |
| `enrich.py` | `ingest_worker/jobs/` | State machine `pending→enriched`, orquestra download+transcrição+resumo | O orquestrador central pode ser generalizado para aceitar novos tipos de job (ex: `source=gdrive`, `source=gmail`) |
| `summarizer.py` | `ingest_worker/lib/` | Gera resumos AI via OpenRouter (minimax-m2.7) | Reutilizável para resumir e-mails longos e documentos do Drive |
| `github_client.py` | `ingest_worker/lib/` | Coleta PRs e issues para enriquecer reuniões | Já alimenta o Signal Cross-Curation; sem alteração |
| `whisper_client.py` | `ingest_worker/lib/` | Transcrição via API OpenAI Whisper | Reutilizável para transcrever áudios do WhatsApp e voicemails (usar `OPENAI_WHISPER_KEY`, NUNCA whisper local) |
| `video_archiver.py` | `ingest_worker/lib/` | HLS→MP4 via ffmpeg + upload Azure Blob | Pode arquivar gravações do Google Meet se integrado |
| `living_memory_client.py` | `ingest_worker/lib/` | Envia observações para claude-mem (memória de longo prazo) | Ponto de saída para a camada 1 (observations) — qualquer novo coletor já tem o caminho pronto |
| `circuit_breaker.py` | `ingest_worker/lib/` | Circuit breaker HTTP para APIs externas | Essencial para Google APIs (rate limits agressivos) |

### Componentes que Precisam de Extensão

| Componente | Extensão Necessária | Complexidade |
|---|---|---|
| `supabase_client.py` | Novas tabelas: `gmail_messages`, `drive_documents`, `identity_map` | Média — schema migrations + upsert functions |
| `enrich.py` | Novo branch no state machine para `source=gdrive` e `source=gmail` (hoje só aceita `source=tldv` e `source=azure-native`) | Média — pattern já existe, é adicionar steps |
| `meetings_denormalized` (view) | Expandir para incluir cross-references com docs do Drive citados em reuniões | Baixa — SQL view rebuild |
| Web SPA (`web/`) | Nova aba "Documentos" e "E-mails" na interface, filtros cross-modal | Alta — frontend novo, mas stack (Vite+React+Tailwind) está sólida |

### Componentes Totalmente Novos (a criar)

| Componente | Descrição | Onde vive |
|---|---|---|
| `google_auth.py` | OAuth2 service account com Domain-wide Delegation, token refresh | `ingest_worker/lib/` |
| `gmail_collector.py` | Polling Gmail API (ou push via Pub/Sub), extrai corpo+anexos de e-mails oficiais | `ingest_worker/lib/` |
| `gdrive_collector.py` | Varredura incremental do Drive compartilhado, detecta novos/modificados docs | `ingest_worker/lib/` |
| `document_parser.py` | Wrapper do RAG-Anything para parsing multimodal (DOCX, XLSX, PPTX, PDF) | `ingest_worker/lib/` |
| `identity_resolver.py` | Mapeia `{email, tldv_participant_id, telegram_id, whatsapp_id}` → pessoa única | `ingest_worker/lib/` |
| `jobs/discover_google.py` | Job de discovery para Gmail + Drive (análogo ao `discover.py` do TLDV) | `ingest_worker/jobs/` |

### Fluxo de Dados Proposto (End-to-End)

```
┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   tl;dv API  │  │  Gmail API   │  │ Google Drive  │  │  WhatsApp/TG │
│  (reuniões)  │  │  (e-mails)   │  │   (docs)      │  │ (mensagens)  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                  │
       ▼                 ▼                 ▼                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    enrich.py (state machine)                         │
│  source=tldv │ source=gmail │ source=gdrive │ source=openclaw       │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        summarizer    whisper_client  document_parser
        (resumos AI)  (áudio→texto)   (RAG-Anything)
              │            │            │
              └────────────┼────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   Supabase (projeto fbnelbwsjfjnkiexxtom)            │
│  meetings │ gmail_messages │ drive_documents │ identity_map          │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     Signal Cross-    ChromaDB      Web SPA
     Curation         (vetorial)    (consulta)
     (curation_cron)  (busca RAG)   (interface)
              │            │            │
              └────────────┼────────────┘
                           ▼
                    MEMORY (curated/)
                    topic files atualizados
```

### Supabase: Schema Existente vs Necessário

**Já existe** (projeto `fbnelbwsjfjnkiexxtom`):
- `meetings` (id, title, date, duration, video_url, hls_url, blob_path)
- `summaries` (meeting_id, content JSONB — decisions[], topics[])
- `meeting_transcript_segments` (meeting_id, speaker, text, start_time, end_time)
- `enrichment_jobs` (id, meeting_id, status, source, hls_url, blob_path)
- `meeting_prs`, `meeting_cards` (enriquecimento GitHub/Trello)
- `meeting_feedback` (thumbs up/down por insight)

**Precisa criar:**
- `gmail_messages` (id, thread_id, from_identity, to_identities[], subject, body_text, attachments[], date, labels[])
- `drive_documents` (id, name, mime_type, parent_folder, content_text, content_embedding, last_modified, owner_identity)
- `identity_map` (id, person_name, email, tldv_participant_id, telegram_id, whatsapp_id, github_username)
- `enrichment_jobs.source` enum expandido: `tldv | azure-native | gmail | gdrive`

### Crons: Atual vs Proposto

| Cron Atual | Schedule | Papel |
|---|---|---|
| `enrich-discover` | hourly :00 | Descobre reuniões TLDV |
| `enrich-process` | 30min :30 | Processa jobs pendentes |
| `tldv-archive-videos` | 03:00 BRT | Arquiva vídeos no Azure |
| `signal-curation` | 4h | Cruza sinais TLDV+GitHub+Logs |

| Cron Novo (proposto) | Schedule | Papel |
|---|---|---|
| `google-discover-gmail` | hourly :15 | Varredura incremental Gmail |
| `google-discover-drive` | 2h :45 | Varredura incremental Drive |
| `identity-sync` | daily 02:00 | Reconcilia identity_map |

### Riscos e Dependências Externas

| Risco | Mitigação |
|---|---|
| tl;dv JWT expira (~1 semana) | Já conhecido; renovação manual via browser cookie |
| Google OAuth scope approval | Usar Internal app type (sem auditoria externa) |
| Rate limits Gmail API (250 quota units/s) | `circuit_breaker.py` já existe; aplicar ao google_auth |
| VPS sem RAM para RAG-Anything (MinerU+LibreOffice) | Opção A: container Docker isolado; Opção B: delegar parsing para API externa (ex: LlamaParse) |
| `meeting_participants` vazia no Supabase | Impede identity resolution automática; necessário popular via tl;dv API ou manualmente |