# Wiki v2 - Living Memory Agent - Especificação de Design

> **Versão:** 1.0
> **Data:** 2026-04-19
> **Status:** Para revisão
> **Autor:** Livy Memory Agent
> **Repo:** `living/livy-memory-bot`

---

## 1. Visão Geral

A Wiki v2 é o sistema de memória institucional da Living Consultoria construido sobre um núcleo de dados semântico multi-fonte. diferente da wiki tradicional (páginas editáveis por humanos), a Wiki v2 é um **sistema de memória curada e auto-atualizável**: agentes leem dados brutos de fontes externas, extraem утверждения (claims), cruzam por assunto/pessoa/projeto e projetam o resultado em páginas wiki com trilha de auditoria completa.

**Objetivo de maturidade:** v2 completa com automação total.

**Critério principal de sucesso:** qualidade de resposta (não governança/confiabilidade como prioridade primária).

**Latência:** sem limite rígido - prioriza qualidade máxima.

**Princípio orientador:** design primeiro, implementação depois, com fact-checking e fail-proofing.

---

## 2. Arquitetura do Sistema

### 2.1 Camadas (4 camadas com contratos explícitos)

```
┌─────────────────────────────────────────────────────────┐
│  KNOWLEDGE INTERFACES                                   │
│  Query híbrida (texto + semântica + grafo)              │
│  Projeção wiki (markdown + citação rastreável)          │
├─────────────────────────────────────────────────────────┤
│  MEMORY CORE (NÚCLEO REESCRITO)                        │
│  confidence · supersession · contradiction              │
│  retention · audit trail · invariantes obrigatórias     │
├─────────────────────────────────────────────────────────┤
│  FUSION ENGINE                                          │
│  Reconciliação de claims multi-fonte por tópico         │
│  Detecção de contradição · Ajuste de confiança          │
├─────────────────────────────────────────────────────────┤
│  CAPTURE LAYER                                          │
│  Hooks OpenClaw + claude-mem (eventos + evidências)    │
│  Fontes: Trello · GitHub · TLDV · Gmail · Calendar    │
├─────────────────────────────────────────────────────────┤
│  EXTERNAL SOURCES                                       │
│  Trello · GitHub · TLDV (Azure Blob) · Gmail · Cal     │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Divisão de Responsabilidade entre Agentes

| Agente | Escopo |
|--------|--------|
| **Livy Memory** | Memória institucional/shared - wiki curada multi-fonte |
| **Livy Deep** | Agente pessoal (Escritório de Memória Privado) |
| **Evo** | Autoresearch e evolução automática de processos |

### 2.3 Política de Privacidade

**Abordagem:** híbrido (blocklist + LLM judge para edge cases).

- Blocklist de topics/entidades (ex.:薪资, dados pessoais de clientes)
- LLM judge para decisões em fronteira (dados parcialmente sensíveis)
- filter de conteúdo antes da projeção wiki
- Auditoria de todas as decisões de filter
- **Arquivo e ownership da blocklist:** `~/.openclaw/secrets/privacy-blocklist.yaml` (owner: Lincoln; manutenção operacional: Livy Memory)
- **Fluxo de decisão de privacidade:**
  1. Blocklist hit ⇒ bloqueia publicação wiki + registra `privacy_decision=blocked`
  2. Edge case ⇒ LLM judge (`allow|redact|block`) + racional
  3. `block` ⇒ exige revisão humana; `allow/redact` segue pipeline com auditoria
- **Processo de manutenção da blocklist:** revisão trimestral (Q1/Q2/Q3/Q4) + notificação automática ao owner a cada hit crítico

---

## 3. Modelo de Dados Canônico (SSOT)

### 3.1 Entidades de Primeira Classe

| Entidade | Anchor canônico | Fontes |
|----------|----------------|--------|
| `Person` | Email Living (`@livingnet.com.br` / `@livingconsultoria.com.br`) | Gmail, Calendar, GitHub, Trello, TLDV |
| `Project` | Trello board/card | Trello, GitHub (via plugin), PRs |
| `Repository` | GitHub repo | GitHub |
| `PullRequest` | GitHub PR number + repo | GitHub, Trello (GitHub plugin) |
| `Commit` | SHA + repo | GitHub |
| `Meeting` | TLDV meeting ID | TLDV (Azure Blob) |
| `Topic` | Nome canônico (deduplicado) | TLDV, PR, Card, Email |
| `Decision` | Topic + reunião | TLDV, PR, Card |
| `EmailThread` | Gmail thread ID | Gmail |

### 3.2 Relacionamentos Obrigatórios

```
Person → Project        (owner | contributor | stakeholder)
Project → Repository
PR → Repository
PR → Project
PR → Person            (author | reviewer | approver | commenter)
Commit → PR             (quando mapeável)
Commit → Person
Meeting → Project
Meeting → Topic/Decision
Topic/Decision → PR | Card | Email | Meeting  (proveniência cruzada)
EmailThread → Person    (sender | receiver)
```

### 3.3 Evidência Bruta (Raw Evidence)

### 3.4 Claim Schema (obrigatório)

Todo parser de fonte deve produzir `Claim` nesse contrato único:

```json
{
  "claim_id": "uuid",
  "entity_type": "person|project|repository|pull_request|meeting|topic|decision|email_thread",
  "entity_id": "canonical-id",
  "topic_id": "topic-canonical-id",
  "claim_type": "status|decision|action_item|risk|ownership|timeline_event|linkage",
  "text": "afirmação normalizada",
  "source": "trello|github|tldv|gmail|gcal",
  "source_ref": {
    "source_id": "id original",
    "url": "https://...",
    "blob_path": "meetings/<id>.transcript.json"
  },
  "evidence_ids": ["uuid-1", "uuid-2"],
  "author": "email/login/id",
  "event_timestamp": "2026-04-19T12:00:00Z",
  "ingested_at": "2026-04-19T12:01:00Z",
  "confidence": 0.0,
  "privacy_level": "public|internal|restricted",
  "superseded_by": null,
  "audit_trail": {
    "model_used": "omniroute/fastest",
    "parser_version": "v1",
    "trace_id": "uuid"
  }
}
```

#### Exemplos por fonte

- **Trello (card):** `claim_type=status`, `text="Card X movido para Done"`, `source_ref.url=<card_url>`
- **GitHub (PR):** `claim_type=decision`, `text="PR #19 aprovado por @alice e mergeado"`, `source_ref.url=<pr_url>`
- **TLDV (meeting):** `claim_type=decision`, `text="Decidido migrar transcripts para Azure-first"`, `source_ref.blob_path=<transcript_path>`
- **Gmail (thread):** `claim_type=action_item`, `text="Cliente abriu chamado Sev2 no sistema BAT"`, `source_ref.url=<gmail_thread_url>`
- **Calendar (evento):** `claim_type=timeline_event`, `text="Reunião de incidente BAT com participantes X,Y,Z"`, `source_ref.source_id=<event_id>`

Cada peça de dado capturada de fonte externa é registrada como evidência imutável:

```json
{
  "evidence_id": "uuid",
  "source": "trello | github | tldv | gmail | gcal",
  "source_id": "id externo original",
  "raw_ref": "url ou referência ao dado bruto",
  "event_timestamp": "2026-04-19T11:51:00Z",
  "author": "person_id ou email",
  "privacy_level": "public | internal | restricted",
  "content_hash": "sha256 do conteúdo original",
  "blob_path": "caminho no Azure (se aplicável)"
}
```

**Invariantes duras:**
- `claim` sem `evidence_id` é rejeitado pelo núcleo
- `write` sem `audit_trail` é rejeitado
- `supersession` sem motivo/version é rejeitado

---

## 4. Inventário Completo de Fontes de Dados

### 4.1 Fontes Obrigatórias (MVP)

| Fonte | O que capturar | Status atual | Via |
|--------|---------------|--------------|-----|
| **Trello** | Cards, listas, boards, membros, labels, checklists, GitHub plugin links, horas lançadas | `research-trello` (parcial) | Reescrever como `CaptureConnectors` |
| **GitHub** | Repos, PRs (body/comments/reviews/approvers), commits, contributors | `research-github` (parcial) | Reescrever como `CaptureConnectors` |
| **TLDV/Meetings** | Transcripts, decisions, topics, participants | `research-tldv` (parcial) | Azure Blob (fonte primária) |
| **Gmail** | Threads decisórias, aberturas de chamado, notificações infra | ❌ novo | OAuth Desktop Client |
| **Calendar** | Eventos, participantes, horário | ❌ novo | OAuth Desktop Client |
| **Infra emails** | Alertas, deploys, incidentes | ❌ novo | OAuth Desktop Client (mesma caixa) |

### 4.2 Trello - Plugins a Integrar

- **GitHub plugin:** vincula PRs do repo a cards - evita lookup manual Project↔PR
- **Plugin de horas:** time tracking por card - usado para enriquecer project metrics

### 4.3 Azure Blob como Fonte Primária de Transcripts

**Stack de storage (já implementado em `livy-tldv-jobs`):**

| Blob path | Conteúdo | Producer |
|-----------|----------|----------|
| `meetings/{id}.transcript.tldv.json` | Original tl;dv | `archive_videos.py` |
| `meetings/{id}.transcript.json` | Consolidado/enriquecido | `azure_transcript_store.py` |
| `meetings/{id}.mp4` | Vídeo MP4 (SAS 2 anos) | `video_archiver.py` |

**API de acesso (reaproveitar de `personal-data-connectors`):**
```python
from connectors.azure_blob import AzureBlobConnector

azure = AzureBlobConnector()
data = azure.download_json(f"meetings/{meeting_id}.transcript.json")
segments = data if isinstance(data, list) else data.get("segments", [data])
```

**Supabase:** permanece como catálogo/índice operacional (ids, names, timestamps, participants, `transcript_blob_path`), **não** como storage de conteúdo.

### 4.4 Autenticação - Gmail/Calendar

**Contas:** `lincoln@livingnet.com.br`, `livy@livingnet.com.br`

**Método:** OAuth Desktop Client com consentimento manual 1× por conta no host.

- Credenciais: `secrets/credentials.json` (OAuth Desktop App)
- Tokens: `secrets/token_{account}.json` (separados por conta)
- Secret manager: `personal-data-connectors/connectors/google_auth.py` (reescrever para credenciais em `~/.openclaw/secrets/`)

**Reaproveitar de `personal-data-connectors`:**
- `connectors/google_auth.py` - `build_google_service()` com scopes configuráveis
- `connectors/gmail.py` - `GmailConnector.get_recent_messages()`
- `connectors/gcal.py` - `GoogleCalendarConnector.get_events()`

---

## 5. Motor de Fusão (Fusion Engine)

> **Definição para evitar ambiguidade:**
> - **Fusion Engine** = componente lógico (biblioteca/regras) que reconcilia claims, calcula confiança, detecta contradição e aplica supersession.
> - **research-consolidation** = job/orquestrador que invoca o Fusion Engine em lote, executa dedupe global, roda cross-source linker e publica resultados.
> - Em resumo: **Fusion Engine é o "motor"; research-consolidation é o "driver" operacional**.

### 5.1 Responsabilidades

1. **Reconciliação** de claims de fontes diferentes sobre o mesmo Topic/Person/Project
2. **Detecção de contradição** (mesmo Topic, claims diferentes, fontes diferentes)
3. **Ajuste de confiança** (por proveniência, recência, número de fontes convergentes)
4. **Supersession** (claim mais recente substitui anterior com motivo documentado)
5. **Retenção** (decay de claims não reforçados por fonte; arquivamento após threshold)

### 5.2 Fluxo de Write

```
Evidência bruta
    ↓
Parser (extrai claims da fonte específica)
    ↓
Normalizador (mapeia para entidade canônica)
    ↓
Fusion Engine
    ├── Verifica contradição ( sesama Topic + fontes diferentes?)
    ├── Calcula confidence (recência + proveniência + convergência)
    ├── Aplica supersession se necessário
    └── Persiste com audit_trail
    ↓
Memory Core (estado do SSOT)
```

### 5.3 Detecção de Contradição

```
IF topic_A has claim_X (source=S, confidence=0.9)
AND claim_Y about topic_A exists (source=T, confidence=0.8)
AND claim_X.content ≠ claim_Y.content
THEN flag = contradiction
AND emit alert via OpenClaw `message` tool
AND do NOT auto-supersede - human review required
```

**Contrato do alerta de contradição (obrigatório):**

- **Canal:** `telegram`
- **Destino:** `7426291192`
- **Origem:** `research-consolidation` (ou `research-{source}` quando detectado inline)
- **Formato (JSON payload antes de render):**

```json
{
  "type": "wiki_v2_contradiction",
  "severity": "high",
  "topic_id": "topic-uuid",
  "topic_name": "BAT Sev2 webhook ConectaBot",
  "claim_a": {"id": "c1", "source": "github", "text": "...", "confidence": 0.91},
  "claim_b": {"id": "c2", "source": "meeting", "text": "...", "confidence": 0.78},
  "detected_at": "2026-04-19T11:51:00Z",
  "requires_human_review": true,
  "review_url": "wiki://contradictions/topic-uuid"
}
```

- **Mensagem renderizada mínima:**
  - título: `⚠️ Contradição detectada: {topic_name}`
  - resumo: fonte A vs fonte B + confidence
  - ação: `Revisar agora` (link para página de contradição)
- **Canal de saída oficial:** Telegram recebe **markdown renderizado** via `message` tool.
- **Destino do JSON:** payload estruturado é persistido no `audit_log`/estado interno para rastreabilidade e replay.
- **Política de execução:** pipeline marca `status=pending_human_review` para o tópico contraditório, mas **não pausa** ingestão global.
```

### 5.4 Ajuste de Confiança

```
base_confidence = 0.5
+ source_reliability_score (github: +0.2, tldv: +0.2, gmail: +0.15, trello: +0.1)
+ recency_score (last_evidence < 7d: +0.2, < 30d: +0.1, < 90d: 0, > 90d: -0.2)
+ convergence_score (n_sources agreeing: +0.1 per source, max +0.3)
- contradiction_penalty (contradiction detected: -0.3)
final_confidence = clamp(base + adjustments, 0.0, 1.0)
```

---

## 6. Knowledge Interface (Projeção Wiki)

### 6.1 Formato das Páginas Wiki

Cada página wiki representa uma **entidade canônica** com:

```markdown
# {EntityType}: {CanonicalName}

**ID:** `{entity_id}`
**Fontes:** [Trello] · [GitHub] · [TLDV] · [Gmail] · [Calendar]
**Última atualização:** `{timestamp}`
**Confiança:** `{confidence_score}`

---

## Evidências

- [{source}] {claim} - `{author}`, `{date}`
- [{source}] {claim} - `{author}`, `{date}`

---

## Decisões

- [{meeting_id}] {decision_text} - decidido em {date}

---

## Timeline

- `{date}`: {event_description}

---

## Relacionamentos

- [Person] @{github_login} - contributor em {project}
- [PR #{number}] {title} - merged {date}

---

## Auditoria

- `{timestamp}`: Claim added (source: {source}, confidence: {conf})
- `{timestamp}`: Superseded by {new_claim_id} (reason: {reason})
```

### 6.2 Tipos de Página Wiki

| Tipo | Conteúdo |
|------|----------|
| `Person` | Perfil Living, atividades, contribuições, decisões tomadas |
| `Project` | Cards Trello, PRs, repos, timeline, métricas de horas |
| `Repository` | PRs, commits, contributors, health metrics |
| `PullRequest` | Descrição, reviews, approvers, comments, vínculo Trello |
| `Meeting` | Transcript, decisions, topics, participants, ações |
| `Topic` | Claims de todas as fontes, contradições, confiança atual |

---

## 7. Research Pipeline v2 (Ingestão de Dados)

### 7.1 Arquitetura de Polling

> **Compatibilidade com spec anterior (batch 6h):**
> Esta seção descreve a **intenção-alvo da Wiki v2** (cadências menores para near-real-time).
> A implementação deve preservar compatibilidade com o desenho batch existente (6h) durante transição.
> **Regra de migração:** iniciar em modo compatível (batch) e reduzir gradualmente os intervalos por feature flag e validação de custo/qualidade.

```
research-{source}  (cron com lock)
    ↓
CaptureConnectors ({source}_client.py)
    ↓
State Derived Cache (.research/{source}/state.json)
    ↓
Fusion Engine
    ↓
SSOT Update (state/identity-graph/state.json)
    ↓
Alerting (se contradição / nova decisão)
```

**Jobs de research (mantidos e evoluídos):**

| Job | Schedule | Responsabilidade |
|-----|----------|-----------------|
| `research-trello` | a cada 20 min | Cards, boards, GitHub plugin links, horas |
| `research-github` | a cada 10 min | PRs, reviews, contributors |
| `research-tldv` | a cada 15 min | Meetings, transcripts (via Azure Blob) |
| `research-gmail` | a cada 15 min (`*/15 * * * *`) | Threads, decisões, chamados |
| `research-calendar` | a cada 30 min (`*/30 * * * *`) | Eventos, participantes |
| `research-consolidation` | 07h BRT | Orquestra Fusion Engine em lote, dedupe global, cross-source linker, supersession |

### 7.2 Cross-Source Linker

Responsável por conectar entidades descubertas em uma fonte com entidades de outras fontes.

**Quando roda (timing oficial):**
1. **Inline leve** em cada `research-{source}` (links diretos óbvios, ex.: PR URL dentro do card Trello)
2. **Reconciliação completa** no `research-consolidation` após ingestões da janela
3. **On-demand** para debugging/replay manual

- `Trello card GitHub plugin link` → `PullRequest`
- `PR author email` → `Person` (via GitHub login + email map)
- `Meeting participant email` → `Person`
- `Calendar attendee email` → `Person`
- `Email sender/receiver` → `Person`
- `PR review request` → `Person`

**Arquivo de mapa:** `state/identity-graph/github-login-map.yaml` (já existe, evoluir)

---

## 8. Estratégia de Rollout - 3 Fases com Gates

### Fase 1 - Fundação do Núcleo (Governança + Azure-first)

**Duração estimada:** 2-3 semanas
**Gate:** Shadow run compara saída atual vs nova; diff aprovado por Lincoln

**Entregas:**
- [ ] Memory Core reescrito com invariantes (claim sem evidence_id = rejected)
- [ ] Fusion Engine v1 (reconciliação + confidence + supersession)
- [ ] CaptureConnectors para Trello (com GitHub plugin links + horas)
- [ ] CaptureConnectors para GitHub (PR completo com reviews/approvers)
- [ ] Azure Blob como fonte primária de transcripts (com fallback Supabase)
- [ ] Shadow run: validação de output contra pipeline atual
- [ ] Rollback em 1 comando (feature flag)

### Fase 2 — Integração de Fontes (Gmail + Calendar + Infra)

**Duração estimada:** 2–3 semanas
**Gate:** Quality of response satisfatória para queries de prueba

> **⚠️ Gate explícito — OAuth Desktop App no VPS:** antes de iniciar qualquer código da Fase 2, executar teste de conexão OAuth Desktop Client no ambiente de produção (VPS). Se falhar, não prosseguir — acionar fallback Service Account Account antes de planejar desenvolvimento.

**Entregas:**
- [ ] OAuth Desktop Client para `lincoln@livingnet` e `livy@livingnet`
- [ ] CaptureConnectors para Gmail (threads, decisões, chamados)
- [ ] CaptureConnectors para Calendar (eventos + participantes)
- [ ] Cross-linker estendido (email↔person, calendar↔person, calendar↔meeting)
- [ ] Privacy filter v1 (blocklist + LLM judge)
- [ ] Teste de qualidade de resposta (golden queries set)
- [ ] Cron `research-gmail` (`*/15 * * * *`) e `research-calendar` (`*/30 * * * *`) operacionais
- [ ] Definição oficial de filtro Gmail aplicada no connector e testada em shadow run

### Fase 3 - Wiki Completa e Automação Total

**Duração estimada:** 3-4 semanas
**Gate:** Avaliação de qualidade por Lincoln + validação de domain experts

**Entregas:**
- [ ] Projeção wiki para todos os tipos de entidade (Person, Project, PR, Meeting, Topic)
- [ ] Query interface (híbrida texto + semântica + grafo)
- [ ] Autoresearch (Evo) integrado ao fluxo de consolidação
- [ ] Detecção de contradição com alerta humano
- [ ] Dashboard operacional (HEARTBEAT estendido com métricas de wiki)
- [ ] SLOs documentados e monitors
- [ ] Runbook de rollback e recuperação

---

## 9. Fail-Proofing Obrigatório

### 9.1 Invariantes Hardcoded

```python
class CorruptStateError(Exception):
    pass

# Em qualquer write para o Memory Core:
if claim.evidence_id is None:
    raise CorruptStateError("Claim sem proveniência")
if claim.audit_trail is None:
    raise CorruptStateError("Write sem auditoria")
if is_superseding and not claim.supersession_reason:
    raise CorruptStateError("Supersession sem motivo")
```

> **Regra:** não usar `assert` para invariantes de produção.

### 9.2 Idempotência

- Chave de idempotência: `{source}:{source_id}:{content_hash}`
- Cron jobs verificam chave antes de processar; ignoram se duplicado
- Retry com backoff exponencial (max 3 tentativas)

### 9.3 Shadow Run + Diff

Antes de ativar nova lógica em produção:
1. Executar nova implementação com mesmos dados de input
2. Comparar output com implementação atual
3. Se diff > threshold (ex.: 5% de divergência em claims), bloquear e alertar
4. Diff report enviado para `7426291192` antes de decisão humana

### 9.4 Rollback

```bash
# Rollback de feature para versão anterior (1 comando)
openclaw config patch --json '{"features": {"wiki_v2": {"enabled": false}}}'
```

### 9.5 Replay Determinístico

- Events stroados com todas as informações necessárias para replay
- `replay_pipeline.py --since=2026-04-19T00:00:00Z` regenera estado a partir de raw events
- Usado para recuperação após falha catastrophica ou rebuild de ambiente

---

## 10. Infraestrutura e Autenticação

### 10.1 Secrets (OAuth Desktop Client)

```
~/.openclaw/secrets/
├── credentials.json          # OAuth Desktop App credentials (Google)
├── token_lincoln.json        # Token OAuth para lincoln@livingnet
└── token_livy.json           # Token OAuth para livy@livingnet
```

### 10.2 Variáveis de Ambiente

```bash
# Azure Blob Storage
AZURE_STORAGE_ACCOUNT_NAME=livingmeetings
AZURE_STORAGE_ACCOUNT_KEY=<key>
AZURE_STORAGE_CONTAINER_NAME=meetings

# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=<id>
GOOGLE_OAUTH_CLIENT_SECRET=<secret>

# Trello
TRELLO_API_KEY=<key>
TRELLO_TOKEN=<token>
TRELLO_USERNAME=lincoln250

# Supabase (índice operacional)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<key>

# GitHub
GITHUB_PERSONAL_ACCESS_TOKEN=<token>

# TLDV
TLDV_JWT_TOKEN=<token>
```

### 10.3 Reaproveitar de `personal-data-connectors`

| Módulo | Reutilizar | Ação necessária |
|--------|-----------|-----------------|
| `connectors/google_auth.py` | Sim | Copiar para `capture/google_auth.py`, adaptar paths para `~/.openclaw/secrets/` |
| `connectors/gmail.py` | Sim | Copiar para `capture/gmail_client.py` |
| `connectors/gcal.py` | Sim | Copiar para `capture/calendar_client.py` |
| `connectors/azure_blob.py` | Sim | Copiar para `capture/azure_blob_client.py`, já existe em `livy-tldv-jobs` |
| `pipeline/meeting_pipeline.py` | Sim | Copiar lógica de normalização de segmentos |
| `connectors/trello.py` | Parcial | Adaptar extração de GitHub links e horas |
| `connectors/github.py` | Parcial | Verificar cobertura de PR reviews/approvers |

### 10.4 Política de Roteamento de Modelos (OmniRouter)

**Decisão oficial:**
- Tarefas com raciocínio, síntese complexa, reconciliação de fontes e decisões ambíguas usam **`omniroute/PremiumFirst`**.
- Tarefas simples, frequentes e operacionais usam **`omniroute/fastest`**.

#### Classificação operacional

| Classe de tarefa | Modelo padrão | Exemplos |
|---|---|---|
| **Complexa (reasoning-heavy)** | `omniroute/PremiumFirst` | detecção de contradições, fusão multi-fonte, decisão de supersession, sumarização executiva com trade-offs, revisão de spec/arquitetura |
| **Simples (throughput-heavy)** | `omniroute/fastest` | polling de APIs, normalização mecânica, dedupe por hash, atualização de estado derivado, notificações padrão |

#### Regra de execução no pipeline

```text
if task.requires_reasoning == true:
    model = "omniroute/PremiumFirst"
else:
    model = "omniroute/fastest"
```

#### Aplicação recomendada por job

- `research-consolidation`: **PremiumFirst** (fusão, contradição, priorização)
- `research-github|trello|tldv|gmail|calendar`: **fastest** no ingest/normalize; **PremiumFirst** apenas no estágio de síntese inferencial
- **Privacy judge (edge cases): PremiumFirst**
- Alertas e mensagens padronizadas: **fastest**

#### Guardrails de custo/qualidade

- Evitar PremiumFirst para etapas puramente ETL.
- Promover para PremiumFirst apenas quando houver ambiguidade semântica ou decisão irreversível.
- Registrar no `audit_trail` o modelo aplicado por etapa crítica (`model_used`).

---

## 11. Critérios de Sucesso por Fase

| Fase | Gate | Métrica |
|------|------|---------|
| **Fase 1** | Shadow run approved | Diff < 5% entre output atual e novo |
| **Fase 1** | Rollback testado | `enabled:false` restaura comportamento anterior em < 1min |
| **Fase 2** | Quality benchmark | Golden queries: > 80% de relevância nas top-5 respostas |
| **Fase 2** | Cross-source links | > 90% de pessoas resolvidas para email canônico Living |
| **Fase 3** | User acceptance | Lincoln valida 10 queries típicas com resposta satisfatória |
| **Fase 3** | Operational stability | 0 incidentes de integridade de dados em 7 dias |

---

## 12. Dependências Externas

| Dependência | Status | Ação |
|-------------|--------|------|
| claude-mem (worker :37777) | ✅ Ativo | Monitorar; não quebrar hooks existentes |
| OpenClaw Gateway | ✅ Ativo | Manter configuração; não alterar plugins.allow sem motivo |
| Azure Blob Storage | ✅ Configurado | `livy-tldv-jobs` já escreve; ler apenas |
| Supabase | ✅ Ativo | Índice; não dependender para conteúdo de transcript |
| Trello API | ✅ API key disponível | TRELLO_API_KEY + TRELLO_TOKEN |
| GitHub API | ✅ `gh` CLI autenticado | Manter token com scopes `repo`, `read:user` |
| Google OAuth | ❌ Não configurado | Setup via Desktop Client flow para as 2 contas |
| TLDV API | ✅ JWT válido até ~2026-04-29 | Usar só para metadata; conteúdo vem do Azure |

### 12.1 Ação operacional obrigatória (data fixa)

- **Ação:** Renovar `TLDV_JWT_TOKEN`
- **Owner:** Lincoln
- **Prazo:** **2026-04-26** (3 dias antes da expiração estimada)
- **Critério de aceite:** token novo validado com chamada real `watch-page` e cron `research-tldv` em status `ok` no run seguinte.

---

## 13. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Google OAuth Desktop App não funciona no VPS | Média | Alto | Testar antes; fallback para Service Account se necessário |
| Trello GitHub plugin data é incompleta | Alta | Médio | Fallback explícito: GitHub API direta (`gh api`) com lookup por repo/PR extraído do card/board; se não houver link, correlacionar por `project↔repo` mapping |
| Contradições geram demasiado ruído | Média | Médio | Threshold configurável para alertas; LLM judge como gate |
| Azure Blob unreadable (credenciais expiradas) | Baixa | Alto | Fallback para Supabase `transcript_segments` rows |
| Supersession automática remove informação útil | Baixa | Médio | Human review para contradições; auto-supersede só para duplicates; claim antigo recebe `superseded_by=<new_claim_id>` |
| Volume de emails muito alto (spam/auto) | Alta | Baixo | Filtro Gmail oficial v1: `newer_than:7d -from:me -category:promotions -category:social -subject:(auto OR automatic OR notification)` + allowlist por domínio (`@livingnet.com.br`, clientes mapeados) |

---

## 14. Futuras Extensões (Pós-v2)

- **MiniMax como summarizer** (rever texto dos connectors minimax para contexto)
- **RAG multimodal** para DOCX/XLSX/PDF em Google Drive
- **Domain-wide Delegation** para Gmail/Calendar institucional (sem OAuth manual)
- **Livy Deep** integrado como cérebro pessoal (Escritório de Memória Privado)
- **Evo como agente de evolução** de processos (cria PRs automaticamente para padrões detectados)

---

_Last updated: 2026-04-19 11:51 UTC_
