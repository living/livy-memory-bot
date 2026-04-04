# Session: 2026-04-04 03:27:16 UTC

- **Session Key**: agent:memory-agent:telegram:memory:direct:7426291192
- **Session ID**: d1033a30-8092-4658-9f67-9fd5dcbf7938
- **Source**: telegram

## Conversation Summary

user: Conversation info (untrusted metadata):
```json
{
  "message_id": "6864",
  "sender_id": "7426291192",
  "sender": "Lincoln Quinan Junior",
  "timestamp": "Wed 2026-04-01 19:48 UTC"
}
```

Sender (untrusted metadata):
```json
{
  "label": "Lincoln Quinan Junior (7426291192)",
  "id": "7426291192",
  "name": "Lincoln Quinan Junior",
  "username": "lincolnqjunior"
}
```

em pt-br por favor
assistant: 昨天 sobre Delphos — pontos principais dos logs de sessão:

**2026-03-31 16:51 UTC — Topic file criado**
- `delphos-video-vistoria.md` criado com completeness 10.0, 22 cross-refs
- Registrado: pipeline em operação ativa
- 2 cross-refs (BAT/ConectaBot + TLDV)

**2026-03-31 16:52 UTC — Autoresearch completo**
- 8 topic files criados (incluindo Delphos)
- Métricas: completeness 10.0, crossrefs 17, actions 11, interventions 0

**2026-03-31 20:04–23:05 UTC — Crons automáticos**
- Delphos sempreIncluded nos 8 arquivos curados enviados
- Status: ✅ sem erros

**Resumo:** ontem não houve discussão manual sobre Delphos — tudo foi execução automática de cron. A única ação manual foi às 16:51, quando o topic file foi criado documentando o pipeline de video vistoria (Vonage/OpenTok + MongoDB Atlas, reports às 12h e 20h BRT via Telegram).

O topic file não tem conteúdo novo — está igual ao de hoje.
assistant: Cron completo às 20:05-20:06 BRT.

**Resumo:**
- Health check: OK (3/3 layers)
- Feedback acumulado: nenhum
- Consolidação (Mente Coletiva — DRY RUN aplicado): 7 mudanças pendentes, lock adquirido/liberado normalmente
- Topics processados: 13 topic files referenciados
- Stale entries: 8 (memory-agent) / 102 (Livy Deep main)
- Orphaned: 11 (memory-agent) / 121 (Livy Deep main)
- MEMORY.md: 82 linhas (memory-agent) / 123 linhas (Livy Deep)
- Dream (sessions): executado
- Autoresearch TLDV: sem feedback
- Memory evolution: sem violações
- 8 arquivos curados enviados via Telegram Direct ✅

Nenhuma intervenção necessária.
assistant: **Autoresearch Cron — 02/04/2026 00:03 UTC**

- **Health check:** OK (3/3 layers)
- **Feedback:** Nenhum para processar
- **Consolidação (Mente Coletiva — DRY RUN aplicado):**
  - `memory-agent`: 8 stale, 11 orphaned → 7 mudanças aplicadas
  - `main (Livy Deep)`: 103 stale, 121 orphaned → 7 mudanças aplicadas
  - MEMORY.md de ambos espaços atualizados
  - Log: `memory/consolidation-log.md`
- **Memory evolution:** Sem violações
- **Métricas:** completeness 10.0, crossrefs 20, actions 0, interventions 0 (inalterado)
- **Autoresearch (8 arquivos enviados via Telegram):** todos entregues com sucesso

Cron completo sem erros.
assistant: **Autoresearch Cron — 03/04/2026 00:04 BRT**

- **Health check:** OK (3/3 layers)
- **Feedback acumulado:** nenhum para processar
- **Consolidação (Mente Coletiva):**
  - memory-agent: 8 stale, 11 orphaned
  - Livy Deep (main): 103 stale, 122 orphaned
  - 8 mudanças pendentes aplicadas — MEMORY.md atualizado (82 e 145 linhas)
  - Log: `memory/consolidation-log.md`
- **Memory evolution:** sem violações
- **Autoresearch:** enviou 7 arquivos de memória (BAT/ConectaBot, claude-mem, Delphos, Forge, Livy Evo, Livy Memory Agent, OpenClaw Gateway, TLDV)
  - 1 aviso: busca `openclaw memory search` deu timeout (10s) — não afetou o envio

**Status:** completo sem erros críticos.
user: [media attached: /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan---241c614a-7d8b-42e9-93b1-fff94b4d7444.md (text/markdown) | /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan---241c614a-7d8b-42e9-93b1-fff94b4d7444.md]
To send an image back, prefer the message tool (media/path/filePath). If you must inline, use MEDIA:https://example.com/image.jpg (spaces ok, quote if needed) or a safe relative path like MEDIA:./image.jpg. Avoid absolute paths (MEDIA:/...) and ~ paths — they are blocked for security. Keep caption in the text body.
Conversation info (untrusted metadata):
```json
{
  "message_id": "7891",
  "sender_id": "7426291192",
  "sender": "Lincoln Quinan Junior",
  "timestamp": "Sat 2026-04-04 02:32 UTC"
}
```

Sender (untrusted metadata):
```json
{
  "label": "Lincoln Quinan Junior (7426291192)",
  "id": "7426291192",
  "name": "Lincoln Quinan Junior",
  "username": "lincolnqjunior"
}
```

[Telegram Lincoln Quinan Junior (@lincolnqjunior) id:7426291192 +2d Sat 2026-04-04 02:32 UTC] Faça review de um plano?

<file name="2026-04-04-rerank-moderation-plan---241c614a-7d8b-42e9-93b1-fff94b4d7444.md" mime="text/markdown">
# Rerank + Moderação Guardrails (OmniRoute) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add listwise rerank + safety moderation to the tl;dv ingest pipeline (segments + insights), using OmniRoute `fastest` with OpenAI direct fallback, plus structured logs and retries.

**Architecture:** Add two focused modules (`reranker.py`, `moderator.py`) wired into `step_enrich` and `generate_insights`. Use existing `search_context()` for 3‑camadas memory and `circuit_breaker.py` for resilience. API regeneration inherits ingest_worker behavior.

**Tech Stack:** Python 3, OpenAI SDK, FastAPI (existing), OmniRoute local, pytest.

---

## File/Component Map

**Create:**
- `ingest_worker/lib/reranker.py` — listwise rerank with OmniRoute + OpenAI fallback, retry/backoff, circuit breaker, structured logs.
- `ingest_worker/lib/moderator.py` — regex redaction + LLM semantic moderation, retry/backoff, circuit breaker, structured logs.
- `tests/test_reranker.py` — unit tests for rerank logic.
- `tests/test_moderator.py` — unit tests for moderation logic.

**Modify:**
- `ingest_worker/lib/circuit_breaker.py` — add configs for `omniroute_rerank`, `omniroute_moderation`.
- `ingest_worker/jobs/enrich.py` — plug rerank+moderation in `step_enrich`.
- `ingest_worker/lib/insights_generator.py` — plug rerank+moderation in `generate_insights`.

---

## Task 1: Add circuit breaker configs

**Files:**
- Modify: `ingest_worker/lib/circuit_breaker.py`

- [ ] **Step 1: Write failing test** (optional, if no existing tests) — skip (no tests here)
- [ ] **Step 2: Implement config**

```python
_CIRCUIT_CONFIG = {
 # ... existing ...
 "omniroute_rerank": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
 "omniroute_moderation": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
}
```

- [ ] **Step 3: Commit**

```bash
git add ingest_worker/lib/circuit_breaker.py
git commit -m "chore: add circuit breaker configs for rerank/moderation"
```

---

## Task 2: Implement reranker module

**Files:**
- Create: `ingest_worker/lib/reranker.py`
- Test: `tests/test_reranker.py`

### API (target)

```python
def rerank_segments(segments: list[dict], query: str, memory_snippets: list[dict], top_k: int = 12, candidate_limit: int = 40) -> list[dict]:
 ...

def rerank_insights(insights: list[dict], query: str, memory_snippets: list[dict], top_k: int = 6, candidate_limit: int = 20) -> list[dict]:
 ...
```

- [ ] **Step 1: Write failing test**

```python
# tests/test_reranker.py
from ingest_worker.lib.reranker import rerank_segments

def test_rerank_segments_falls_back_on_invalid_json(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 def fake_call(*args, **kwargs):
 return "not-json"
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", fake_call)
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert ranked == segments
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/reranker.py
import json, re, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
RERANK_MODEL = os.getenv("RERANK_MODEL", "fastest")
RERANK_FALLBACK_MODEL = os.getenv("RERANK_FALLBACK_MODEL", "gpt-4o-mini")

def _call_rerank_llm(client: OpenAI, model: str, payload: dict) -> str:
 """Call chat.completions and return raw content string."""

def _parse_json(raw: str) -> dict | None:
 """Extract JSON object from raw text; return None if invalid."""

def _retry_with_backoff(fn, retries: int, delays: list[float]):
 """Retry helper with exponential backoff; re-raise last error."""
```

Include:
- OmniRoute client: `OpenAI(api_key=OMNIROUTE_API_KEY, base_url=OMNIROUTE_BASE_URL)`
- Fallback client: `OpenAI(api_key=OPENAI_API_KEY)`
- Retry 3x (1s,2s,4s) for OmniRoute; 2x for OpenAI fallback
- Structured logs: `[rerank] [INFO] ...`
- If circuit open → immediate fallback
- If JSON parse fails → fallback to original order

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_reranker.py

def test_rerank_segments_uses_ranked_order(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: '{"ranked":[{"id":2,"score":0.9,"reason":"x"},{"id":1,"score":0.5,"reason":"y"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [2,1]


def test_rerank_fallback_openai_on_omniroute_failure(monkeypatch):
 segments = [{"id": 1, "text": "A"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.reranker._call_openai_fallback", lambda *a, **k: '{"ranked":[{"id":1,"score":0.9,"reason":"x"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [1]
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_reranker.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/reranker.py tests/test_reranker.py
git commit -m "feat: add listwise reranker with OmniRoute fallback"
```

---

## Task 3: Implement moderator module

**Files:**
- Create: `ingest_worker/lib/moderator.py`
- Test: `tests/test_moderator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_moderator.py
from ingest_worker.lib.moderator import moderate_input

def test_moderate_input_redacts_email():
 text = "contato: pessoa@empresa.com"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:email]" in cleaned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/moderator.py
import re, json, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

# regex patterns map
# helper: _apply_regex(text) -> (cleaned, flags)
# helper: _call_moderation_llm(text) -> flags
# helper: _redact_semantic(text, flags)

# moderate_input: regex only
# moderate_output: regex + LLM semantic, with fallback to regex-only
```

Include:
- OmniRoute client + OpenAI fallback (same pattern as reranker).
- Structured logs: `[moderation] [WARN] ...`
- If LLM fails → return regex-only result

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_moderator.py

def test_moderate_output_semantic_flags(monkeypatch):
 def fake_llm(*args, **kwargs):
 return '{"flags":[{"category":"financeiro","text":"R$ 9.000","action":"REDACT","reason":"valor"}]}'
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", fake_llm)
 cleaned, flags = moderate_output("Pagamento R$ 9.000")
 assert "[REDACTED:financeiro]" in cleaned

def test_moderation_fallback_openai(monkeypatch):
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.moderator._call_openai_fallback", lambda *a, **k: '{"flags":[]}')
 cleaned, flags = moderate_output("Texto neutro")
 assert cleaned == "Texto neutro"
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_moderator.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/moderator.py tests/test_moderator.py
git commit -m "feat: add moderation guardrails with redaction"
```

---

## Task 4: Wire rerank + moderation into step_enrich

**Files:**
- Modify: `ingest_worker/jobs/enrich.py`

- [ ] **Step 1: Write failing test** (optional; no existing unit tests for enrich.py) — skip

- [ ] **Step 2: Implement integration**

Insert near `step_enrich` after loading segments/transcript:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_segments
from lib.moderator import moderate_input

memory_snippets = search_context(meeting_name, params={}, limit=3)
moderated_transcript, input_flags = moderate_input(effective_transcript, cid=str(job["id"]), meeting_id=meeting_id)
ranked_segments = rerank_segments(segments, query=meeting_name, memory_snippets=memory_snippets, top_k=12)

# override inputs used by hook_pre_enrich/consolidator
# - effective_transcript = moderated_transcript
# - segments = ranked_segments
```

- [ ] **Step 3: Run lint/test smoke**

Run: `pytest tests/test_enrich.py::test_enrich_happy_path -v`
Expected: PASS (or skip if not available)

- [ ] **Step 4: Commit**

```bash
git add ingest_worker/jobs/enrich.py
git commit -m "feat: integrate rerank+moderation in enrich pipeline"
```

---

## Task 5: Wire rerank + moderation into insights generator

**Files:**
- Modify: `ingest_worker/lib/insights_generator.py`

- [ ] **Step 1: Write failing test** (optional; create minimal unit test)

```python
# tests/test_insights_generator_rerank.py
from ingest_worker.lib import insights_generator as ig

def test_generate_insights_reranks_flags(monkeypatch):
 monkeypatch.setattr(ig, "_call_llm", lambda *_: {"summary":"ok","flags":[{"text":"a"},{"text":"b"}]})
 monkeypatch.setattr("ingest_worker.lib.reranker.rerank_insights", lambda flags, *a, **k: [flags[1]])
 monkeypatch.setattr("ingest_worker.lib.moderator.moderate_output", lambda text, **_: (text, []))
 monkeypatch.setattr("ingest_worker.lib.insights_generator._save_insights", lambda *_: None)
 monkeypatch.setattr("ingest_worker.lib.insights_generator._get_meeting_context", lambda *_: {"id":"1","name":"x","meeting_type":"outro","created_at":"","topics":[],"decisions":[],"action_items":[],"enrichment_context":{},"insights_json":None,"insights_generated_at":None})
 res = ig.generate_insights("1", force=True)
 assert len(res["flags"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: FAIL (integration missing)

- [ ] **Step 3: Implement integration**

Insert after `_call_llm(prompt)`:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_insights
from lib.moderator import moderate_output

memory_snippets = search_context(ctx["name"], params={}, limit=3)
if result and result.get("flags"):
 result["flags"] = rerank_insights(result["flags"], query=ctx["name"], memory_snippets=memory_snippets, top_k=6)
if result and result.get("summary"):
 result["summary"], _flags = moderate_output(result["summary"], meeting_id=meeting_id)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ingest_worker/lib/insights_generator.py tests/test_insights_generator_rerank.py
git commit -m "feat: add rerank+moderation to insights generation"
```

---

## Task 6: Update docs / environment hints (optional)

**Files:**
- Modify: `CLAUDE.md` (if needed), `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`

- [ ] **Step 1: Ensure env vars documented**
- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-04-04-rerank-moderation-design.md
git commit -m "docs: update rerank/moderation env vars"
```

---

## Verification

Run the focused unit tests:

```bash
pytest tests/test_reranker.py tests/test_moderator.py tests/test_insights_generator_rerank.py -v
```

Expected: PASS

---

## Rollout / Risk Notes

- OmniRoute down → fallback OpenAI direct.
- OpenAI down → fallback to original order / regex-only.
- No schema changes needed.
- Logs are the only audit trail for moderation (phase 1).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-04-rerank-moderation-plan.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

---

## References

- Spec: `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`
- Memory search: `ingest_worker/lib/autoresearch/memory_search.py`
- Circuit breaker: `ingest_worker/lib/circuit_breaker.py`
- Insights generator: `ingest_worker/lib/insights_generator.py`
- Enricher: `ingest_worker/jobs/enrich.py`

---

*Generated by Livy ⚙️*
</file>
assistant: Segue review direto do plano (pt‑BR), focando riscos, lacunas e pontos a esclarecer.

## ✅ Pontos fortes
- Escopo bem delimitado (rerank + moderação).
- Separação em módulos (`reranker.py` / `moderator.py`) com integração clara.
- Fallback OmniRoute → OpenAI → “ordem original/regex-only” reduz risco operacional.
- Testes unitários propostos com cenários de fallback.

## ⚠️ Lacunas / ajustes recomendados

### 1) **Contrato de payload e schema**
- Não está definido **schema de resposta** esperado do reranker e do moderador.
  - Ex: `{ranked:[{id,score,reason}], warnings:[]}` → isso precisa ser documentado e validado no parser.
- Sugestão: definir `pydantic` (ou dict schema + validação explícita) para garantir estabilidade.

### 2) **Compatibilidade com `segments/insights`**
- O plano assume que cada item tem `id`.
  - E se algum item não tiver `id` ou vier duplicado?
- Sugestão: fallback automático para índice (`idx`) + mapeamento estável.

### 3) **Rerank listwise → custo e latência**
- `candidate_limit` default 40/20 sem heurística.
- Falta um limitador baseado em tempo/token.
  - Sugestão: truncar por tamanho total ou por score prévio.

### 4) **Moderation regex + LLM**
- “regex-only fallback” ok, mas:
  - Onde ficam os **padrões regex**? (arquivo config?)
  - Há risco de redaction agressivo sem audit trail.
- Sugestão: log estruturado com `flag_count`, `categories`, `sample_hash`.

### 5) **Circuit breaker**
- Adiciona configs, mas não define **nomes padronizados** (ex: `omniroute_rerank` / `omniroute_moderation`) para telemetry.
- Sugestão: alinhar com naming padrão atual (`openai_…`, `vector_…`) se existir.

### 6) **Integração com `search_context()`**
- O plano usa `search_context(meeting_name, params={}, limit=3)`:
  - Isso é custo adicional e pode aumentar latência.
  - Falta tratar erro (timeout / retorno vazio).
- Sugestão: cache por `meeting_id` no job ou reduzir `limit` default.

### 7) **Testes de integração**
- Faltam testes cobrindo **pipeline completo** com `rerank + moderation` no `enrich` e `insights`.
- Sugestão: mínimo smoke test com mocks e `pytest -k enrich`.

### 8) **Logs estruturados**
- Logs propostos como string `[rerank] [INFO]`, mas sem formato estruturado.
- Sugestão: log JSON padrão (`event`, `duration_ms`, `model`, `fallback`, `error`).

## ❓Perguntas de clarificação (antes de implementar)
1. Qual o **schema oficial** esperado das respostas do reranker/moderator?
2. `segments` e `insights` sempre têm `id` único? Se não, qual fallback?
3. Qual política de redaction desejada (ex.: PII, financeiro, legal)?
4. Qual o limite aceitável de latência para `step_enrich`?
5. Há necessidade de **feature flag** para ligar/desligar rerank/moderação?

Se quiser, eu posso consolidar isso em um checklist de revisão do plano ou escrever as alterações sugeridas diretamente no markdown do plano.
user: [media attached: /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan_1---8370ee17-ec97-42e7-bb48-ef664e082f15.md (text/markdown) | /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan_1---8370ee17-ec97-42e7-bb48-ef664e082f15.md]
To send an image back, prefer the message tool (media/path/filePath). If you must inline, use MEDIA:https://example.com/image.jpg (spaces ok, quote if needed) or a safe relative path like MEDIA:./image.jpg. Avoid absolute paths (MEDIA:/...) and ~ paths — they are blocked for security. Keep caption in the text body.
Conversation info (untrusted metadata):
```json
{
  "message_id": "7893",
  "sender_id": "7426291192",
  "sender": "Lincoln Quinan Junior",
  "timestamp": "Sat 2026-04-04 02:45 UTC"
}
```

Sender (untrusted metadata):
```json
{
  "label": "Lincoln Quinan Junior (7426291192)",
  "id": "7426291192",
  "name": "Lincoln Quinan Junior",
  "username": "lincolnqjunior"
}
```

[Telegram Lincoln Quinan Junior (@lincolnqjunior) id:7426291192 +12m Sat 2026-04-04 02:45 UTC] Revisa essa versão

<file name="2026-04-04-rerank-moderation-plan_1---8370ee17-ec97-42e7-bb48-ef664e082f15.md" mime="text/markdown">
# Rerank + Moderação Guardrails (OmniRoute) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add listwise rerank + safety moderation to the tl;dv ingest pipeline (segments + insights), using OmniRoute `fastest` with OpenAI direct fallback, plus structured logs and retries.

**Architecture:** Add two focused modules (`reranker.py`, `moderator.py`) wired into `step_enrich` and `generate_insights`. Use existing `search_context()` for 3‑camadas memory and `circuit_breaker.py` for resilience. API regeneration inherits ingest_worker behavior.

**Tech Stack:** Python 3, OpenAI SDK, FastAPI (existing), OmniRoute local, pytest.

---

## File/Component Map

**Create:**
- `ingest_worker/lib/reranker.py` — listwise rerank with OmniRoute + OpenAI fallback, retry/backoff, circuit breaker, structured logs.
- `ingest_worker/lib/moderator.py` — regex redaction + LLM semantic moderation, retry/backoff, circuit breaker, structured logs.
- `tests/test_reranker.py` — unit tests for rerank logic.
- `tests/test_moderator.py` — unit tests for moderation logic.

**Modify:**
- `ingest_worker/lib/circuit_breaker.py` — add configs for `omniroute_rerank`, `omniroute_moderation`.
- `ingest_worker/jobs/enrich.py` — plug rerank+moderation in `step_enrich`.
- `ingest_worker/lib/insights_generator.py` — plug rerank+moderation in `generate_insights`.

---

## Additions from review (risks/lacunas)

- **Schema validation**: validate rerank/moderation JSON shape before use; fallback on mismatch.
- **ID fallback**: if candidate item lacks `id`, use stable index (`idx`) and map back.
- **Latency/token cap**: cap total candidate text length (e.g., 6–8k chars) in addition to `candidate_limit`.
- **Search context resilience**: wrap `search_context()` in try/except; on failure, use empty list + log.
- **Structured logs**: log JSON payloads (event, duration_ms, model, fallback, error, flag_count, sample_hash).
- **Feature flags**: env toggles `RERANK_ENABLED` / `MODERATION_ENABLED` (default true).

---

## Task 1: Add circuit breaker configs

**Files:**
- Modify: `ingest_worker/lib/circuit_breaker.py`

- [ ] **Step 1: Write failing test** (optional, if no existing tests) — skip (no tests here)
- [ ] **Step 2: Implement config**

```python
_CIRCUIT_CONFIG = {
 # ... existing ...
 "omniroute_rerank": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
 "omniroute_moderation": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
}
```

- [ ] **Step 3: Commit**

```bash
git add ingest_worker/lib/circuit_breaker.py
git commit -m "chore: add circuit breaker configs for rerank/moderation"
```

---

## Task 2: Implement reranker module

**Files:**
- Create: `ingest_worker/lib/reranker.py`
- Test: `tests/test_reranker.py`

### API (target)

```python
def rerank_segments(segments: list[dict], query: str, memory_snippets: list[dict], top_k: int = 12, candidate_limit: int = 40) -> list[dict]:
 ...

def rerank_insights(insights: list[dict], query: str, memory_snippets: list[dict], top_k: int = 6, candidate_limit: int = 20) -> list[dict]:
 ...
```

- [ ] **Step 1: Write failing test**

```python
# tests/test_reranker.py
from ingest_worker.lib.reranker import rerank_segments

def test_rerank_segments_falls_back_on_invalid_json(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 def fake_call(*args, **kwargs):
 return "not-json"
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", fake_call)
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert ranked == segments
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/reranker.py
import json, re, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
RERANK_MODEL = os.getenv("RERANK_MODEL", "fastest")
RERANK_FALLBACK_MODEL = os.getenv("RERANK_FALLBACK_MODEL", "gpt-4o-mini")

def _call_rerank_llm(client: OpenAI, model: str, payload: dict) -> str:
 """Call chat.completions and return raw content string."""

def _parse_json(raw: str) -> dict | None:
 """Extract JSON object from raw text; return None if invalid."""

def _retry_with_backoff(fn, retries: int, delays: list[float]):
 """Retry helper with exponential backoff; re-raise last error."""
```

Include:
- OmniRoute client: `OpenAI(api_key=OMNIROUTE_API_KEY, base_url=OMNIROUTE_BASE_URL)`
- Fallback client: `OpenAI(api_key=OPENAI_API_KEY)`
- Retry 3x (1s,2s,4s) for OmniRoute; 2x for OpenAI fallback
- **Schema validation**: ensure `ranked` is list of objects with `id` (int|str) + `score` (float)
- **ID fallback**: if candidate lacks `id`, assign `idx` and map back
- **Latency cap**: truncate candidate text to total ~8k chars before LLM call
- **Structured logs**: JSON log dict (event, duration_ms, model, fallback, error)
- If circuit open → immediate fallback
- If JSON parse fails → fallback to original order

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_reranker.py

def test_rerank_segments_uses_ranked_order(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: '{"ranked":[{"id":2,"score":0.9,"reason":"x"},{"id":1,"score":0.5,"reason":"y"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [2,1]


def test_rerank_fallback_openai_on_omniroute_failure(monkeypatch):
 segments = [{"id": 1, "text": "A"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.reranker._call_openai_fallback", lambda *a, **k: '{"ranked":[{"id":1,"score":0.9,"reason":"x"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [1]
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_reranker.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/reranker.py tests/test_reranker.py
git commit -m "feat: add listwise reranker with OmniRoute fallback"
```

---

## Task 3: Implement moderator module

**Files:**
- Create: `ingest_worker/lib/moderator.py`
- Test: `tests/test_moderator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_moderator.py
from ingest_worker.lib.moderator import moderate_input

def test_moderate_input_redacts_email():
 text = "contato: pessoa@empresa.com"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:email]" in cleaned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/moderator.py
import re, json, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

# regex patterns map
# helper: _apply_regex(text) -> (cleaned, flags)
# helper: _call_moderation_llm(text) -> flags
# helper: _redact_semantic(text, flags)

# moderate_input: regex only
# moderate_output: regex + LLM semantic, with fallback to regex-only
```

Include:
- OmniRoute client + OpenAI fallback (same pattern as reranker).
- **Schema validation**: ensure `flags` is list of {category,text,action}.
- **Structured logs**: JSON log dict (event, duration_ms, model, fallback, error, flag_count).
- If LLM fails → return regex-only result

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_moderator.py

def test_moderate_output_semantic_flags(monkeypatch):
 def fake_llm(*args, **kwargs):
 return '{"flags":[{"category":"financeiro","text":"R$ 9.000","action":"REDACT","reason":"valor"}]}'
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", fake_llm)
 cleaned, flags = moderate_output("Pagamento R$ 9.000")
 assert "[REDACTED:financeiro]" in cleaned

def test_moderation_fallback_openai(monkeypatch):
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.moderator._call_openai_fallback", lambda *a, **k: '{"flags":[]}')
 cleaned, flags = moderate_output("Texto neutro")
 assert cleaned == "Texto neutro"
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_moderator.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/moderator.py tests/test_moderator.py
git commit -m "feat: add moderation guardrails with redaction"
```

---

## Task 4: Wire rerank + moderation into step_enrich

**Files:**
- Modify: `ingest_worker/jobs/enrich.py`

- [ ] **Step 1: Write failing test** (optional; no existing unit tests for enrich.py) — skip

- [ ] **Step 2: Implement integration**

Insert near `step_enrich` after loading segments/transcript:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_segments
from lib.moderator import moderate_input

try:
 memory_snippets = search_context(meeting_name, params={}, limit=3)
except Exception as e:
 print(f"[rerank] [WARN] event=memory_search_failed meeting={meeting_id} error={e}")
 memory_snippets = []

moderated_transcript, input_flags = moderate_input(effective_transcript, cid=str(job["id"]), meeting_id=meeting_id)
ranked_segments = rerank_segments(segments, query=meeting_name, memory_snippets=memory_snippets, top_k=12)

# override inputs used by hook_pre_enrich/consolidator
# - effective_transcript = moderated_transcript
# - segments = ranked_segments
```

- [ ] **Step 3: Run lint/test smoke**

Run: `pytest tests/test_enrich.py::test_enrich_happy_path -v`
Expected: PASS (or skip if not available)

- [ ] **Step 4: Commit**

```bash
git add ingest_worker/jobs/enrich.py
git commit -m "feat: integrate rerank+moderation in enrich pipeline"
```

---

## Task 5: Wire rerank + moderation into insights generator

**Files:**
- Modify: `ingest_worker/lib/insights_generator.py`

- [ ] **Step 1: Write failing test** (optional; create minimal unit test)

```python
# tests/test_insights_generator_rerank.py
from ingest_worker.lib import insights_generator as ig

def test_generate_insights_reranks_flags(monkeypatch):
 monkeypatch.setattr(ig, "_call_llm", lambda *_: {"summary":"ok","flags":[{"text":"a"},{"text":"b"}]})
 monkeypatch.setattr("ingest_worker.lib.reranker.rerank_insights", lambda flags, *a, **k: [flags[1]])
 monkeypatch.setattr("ingest_worker.lib.moderator.moderate_output", lambda text, **_: (text, []))
 monkeypatch.setattr("ingest_worker.lib.insights_generator._save_insights", lambda *_: None)
 monkeypatch.setattr("ingest_worker.lib.insights_generator._get_meeting_context", lambda *_: {"id":"1","name":"x","meeting_type":"outro","created_at":"","topics":[],"decisions":[],"action_items":[],"enrichment_context":{},"insights_json":None,"insights_generated_at":None})
 res = ig.generate_insights("1", force=True)
 assert len(res["flags"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: FAIL (integration missing)

- [ ] **Step 3: Implement integration**

Insert after `_call_llm(prompt)`:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_insights
from lib.moderator import moderate_output

try:
 memory_snippets = search_context(ctx["name"], params={}, limit=3)
except Exception as e:
 print(f"[rerank] [WARN] event=memory_search_failed meeting={meeting_id} error={e}")
 memory_snippets = []

if result and result.get("flags"):
 result["flags"] = rerank_insights(result["flags"], query=ctx["name"], memory_snippets=memory_snippets, top_k=6)
if result and result.get("summary"):
 result["summary"], _flags = moderate_output(result["summary"], meeting_id=meeting_id)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ingest_worker/lib/insights_generator.py tests/test_insights_generator_rerank.py
git commit -m "feat: add rerank+moderation to insights generation"
```

---

## Task 6: Update docs / environment hints (optional)

**Files:**
- Modify: `CLAUDE.md` (if needed), `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`

- [ ] **Step 1: Ensure env vars documented**
- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-04-04-rerank-moderation-design.md
git commit -m "docs: update rerank/moderation env vars"
```

---

## Verification

Run the focused unit tests:

```bash
pytest tests/test_reranker.py tests/test_moderator.py tests/test_insights_generator_rerank.py -v
```

Expected: PASS

---

## Rollout / Risk Notes

- OmniRoute down → fallback OpenAI direct.
- OpenAI down → fallback to original order / regex-only.
- No schema changes needed.
- Logs are the only audit trail for moderation (phase 1).
- **Feature flags**: `RERANK_ENABLED` / `MODERATION_ENABLED` allow immediate disable if latency spikes.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-04-rerank-moderation-plan.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

---

## References

- Spec: `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`
- Memory search: `ingest_worker/lib/autoresearch/memory_search.py`
- Circuit breaker: `ingest_worker/lib/circuit_breaker.py`
- Insights generator: `ingest_worker/lib/insights_generator.py`
- Enricher: `ingest_worker/jobs/enrich.py`

---

*Generated by Livy ⚙️*
</file>
assistant: Review da versão atual (pt‑BR) — foco em riscos remanescentes e ajustes finos.

## ✅ Melhorias incorporadas
- Schema validation + fallback explícito.
- ID fallback por `idx`.
- Cap de latência por tamanho total.
- `search_context()` protegido com try/except.
- Logs estruturados.
- Feature flags `RERANK_ENABLED` / `MODERATION_ENABLED`.

## ⚠️ Pontos ainda abertos / ajustes recomendados

1) **Contrato de payload (rerank/moderação)**
- Precisa fixar o schema esperado em doc ou constante (`RERANK_SCHEMA`, `MOD_SCHEMA`) para evitar deriva.
- Sugestão: definir a interface do JSON no próprio arquivo e validar estritamente.

2) **Mapeamento de saída**
- `rerank_segments()` deve preservar todos os campos originais (não só id/text).
- Garantir que itens não retornados pelo LLM sejam apendados no final (ordem original).

3) **Moderation regex**
- Falta listar quais padrões PII/financeiro/segurança serão usados.
- Sugestão: tabela mínima de regexes + unit tests cobrindo 2–3 casos.

4) **Logs estruturados**
- O plano fala “log JSON”, mas o exemplo usa `print`.
- Sugestão: padronizar com `log_event(event="rerank", ...)` e centralizar em helper.

5) **Fallback OpenAI**
- Precisamos saber se a API key do OpenAI está sempre disponível nesse worker.
- Sugestão: se `OPENAI_API_KEY` ausente → fallback direto para ordem original / regex-only.

6) **Feature flags em runtime**
- Onde ficam setadas (env do worker, config, .env)?
- Sugestão: doc rápido em `CLAUDE.md` ou env template.

## Perguntas rápidas antes de executar
1) Qual schema final esperado para `ranked` e `flags`?
2) Existe um set mínimo de categorias de moderação exigidas?
3) O limite de 8k chars é ok para o SLA do pipeline?

Se quiser, eu ajusto o plano com esses pontos já embutidos (mais 3–4 bullets + um helper de logging).
user: [media attached: /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan_2---8a685e04-5968-4a32-9fee-840b0edb720e.md (text/markdown) | /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan_2---8a685e04-5968-4a32-9fee-840b0edb720e.md]
To send an image back, prefer the message tool (media/path/filePath). If you must inline, use MEDIA:https://example.com/image.jpg (spaces ok, quote if needed) or a safe relative path like MEDIA:./image.jpg. Avoid absolute paths (MEDIA:/...) and ~ paths — they are blocked for security. Keep caption in the text body.
Conversation info (untrusted metadata):
```json
{
  "message_id": "7895",
  "sender_id": "7426291192",
  "sender": "Lincoln Quinan Junior",
  "timestamp": "Sat 2026-04-04 02:56 UTC"
}
```

Sender (untrusted metadata):
```json
{
  "label": "Lincoln Quinan Junior (7426291192)",
  "id": "7426291192",
  "name": "Lincoln Quinan Junior",
  "username": "lincolnqjunior"
}
```

[Telegram Lincoln Quinan Junior (@lincolnqjunior) id:7426291192 +10m Sat 2026-04-04 02:56 UTC] Nova versão, revisa

<file name="2026-04-04-rerank-moderation-plan_2---8a685e04-5968-4a32-9fee-840b0edb720e.md" mime="text/markdown">
# Rerank + Moderação Guardrails (OmniRoute) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add listwise rerank + safety moderation to the tl;dv ingest pipeline (segments + insights), using OmniRoute `fastest` with OpenAI direct fallback, plus structured logs and retries.

**Architecture:** Add two focused modules (`reranker.py`, `moderator.py`) wired into `step_enrich` and `generate_insights`. Use existing `search_context()` for 3‑camadas memory and `circuit_breaker.py` for resilience. API regeneration inherits ingest_worker behavior.

**Tech Stack:** Python 3, OpenAI SDK, FastAPI (existing), OmniRoute local, pytest.

---

## File/Component Map

**Create:**
- `ingest_worker/lib/reranker.py` — listwise rerank with OmniRoute + OpenAI fallback, retry/backoff, circuit breaker, structured logs.
- `ingest_worker/lib/moderator.py` — regex redaction + LLM semantic moderation, retry/backoff, circuit breaker, structured logs.
- `tests/test_reranker.py` — unit tests for rerank logic.
- `tests/test_moderator.py` — unit tests for moderation logic.

**Modify:**
- `ingest_worker/lib/circuit_breaker.py` — add configs for `omniroute_rerank`, `omniroute_moderation`.
- `ingest_worker/jobs/enrich.py` — plug rerank+moderation in `step_enrich`.
- `ingest_worker/lib/insights_generator.py` — plug rerank+moderation in `generate_insights`.

---

## Additions from review (risks/lacunas)

- **Schema validation**: define constants `RERANK_SCHEMA` / `MOD_SCHEMA` and validate strictly; fallback on mismatch.
- **ID fallback**: if candidate item lacks `id`, use stable index (`idx`) and map back.
- **Preserve payload**: rerank returns full original item dicts; items not returned by LLM are appended in original order.
- **Latency/token cap**: cap total candidate text length (e.g., 6–8k chars) in addition to `candidate_limit`.
- **Search context resilience**: wrap `search_context()` in try/except; on failure, use empty list + log.
- **Structured logs**: centralize `log_event(event=..., data={...})` helper and emit JSON payloads.
- **Feature flags**: env toggles `RERANK_ENABLED` / `MODERATION_ENABLED` (default true).
- **OpenAI key absence**: if `OPENAI_API_KEY` missing, fallback directly to original order / regex-only.

---

## Task 1: Add circuit breaker configs

**Files:**
- Modify: `ingest_worker/lib/circuit_breaker.py`

- [ ] **Step 1: Write failing test** (optional, if no existing tests) — skip (no tests here)
- [ ] **Step 2: Implement config**

```python
_CIRCUIT_CONFIG = {
 # ... existing ...
 "omniroute_rerank": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
 "omniroute_moderation": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
}
```

- [ ] **Step 3: Commit**

```bash
git add ingest_worker/lib/circuit_breaker.py
git commit -m "chore: add circuit breaker configs for rerank/moderation"
```

---

## Task 2: Implement reranker module

**Files:**
- Create: `ingest_worker/lib/reranker.py`
- Test: `tests/test_reranker.py`

### API (target)

```python
def rerank_segments(segments: list[dict], query: str, memory_snippets: list[dict], top_k: int = 12, candidate_limit: int = 40) -> list[dict]:
 """Return full item dicts; append missing items in original order; stable ID fallback to idx."""

def rerank_insights(insights: list[dict], query: str, memory_snippets: list[dict], top_k: int = 6, candidate_limit: int = 20) -> list[dict]:
 """Return full item dicts; append missing items in original order; stable ID fallback to idx."""
```

- [ ] **Step 1: Write failing test**

```python
# tests/test_reranker.py
from ingest_worker.lib.reranker import rerank_segments

def test_rerank_segments_falls_back_on_invalid_json(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 def fake_call(*args, **kwargs):
 return "not-json"
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", fake_call)
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert ranked == segments
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/reranker.py
import json, re, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
RERANK_MODEL = os.getenv("RERANK_MODEL", "fastest")
RERANK_FALLBACK_MODEL = os.getenv("RERANK_FALLBACK_MODEL", "gpt-4o-mini")

def _call_rerank_llm(client: OpenAI, model: str, payload: dict) -> str:
 """Call chat.completions and return raw content string."""

def _parse_json(raw: str) -> dict | None:
 """Extract JSON object from raw text; return None if invalid."""

def _retry_with_backoff(fn, retries: int, delays: list[float]):
 """Retry helper with exponential backoff; re-raise last error."""
```

Include:
- OmniRoute client: `OpenAI(api_key=OMNIROUTE_API_KEY, base_url=OMNIROUTE_BASE_URL)`
- Fallback client: `OpenAI(api_key=OPENAI_API_KEY)` (if missing → skip OpenAI fallback)
- Retry 3x (1s,2s,4s) for OmniRoute; 2x for OpenAI fallback
- **Schema validation**: `RERANK_SCHEMA` requires `ranked: [{id, score, reason?}]` and `warnings: []`
- **ID fallback**: if candidate lacks `id`, assign `idx` and map back
- **Preserve payload**: return full item dicts; append LLM-missing items in original order
- **Latency cap**: truncate candidate text to total ~8k chars before LLM call
- **Structured logs**: `log_event("rerank", {...})` (JSON)
- If circuit open → immediate fallback
- If JSON parse fails → fallback to original order

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_reranker.py

def test_rerank_segments_uses_ranked_order(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: '{"ranked":[{"id":2,"score":0.9,"reason":"x"},{"id":1,"score":0.5,"reason":"y"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [2,1]


def test_rerank_fallback_openai_on_omniroute_failure(monkeypatch):
 segments = [{"id": 1, "text": "A"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.reranker._call_openai_fallback", lambda *a, **k: '{"ranked":[{"id":1,"score":0.9,"reason":"x"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [1]
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_reranker.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/reranker.py tests/test_reranker.py
git commit -m "feat: add listwise reranker with OmniRoute fallback"
```

---

## Task 3: Implement moderator module

**Files:**
- Create: `ingest_worker/lib/moderator.py`
- Test: `tests/test_moderator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_moderator.py
from ingest_worker.lib.moderator import moderate_input

def test_moderate_input_redacts_email():
 text = "contato: pessoa@empresa.com"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:email]" in cleaned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/moderator.py
import re, json, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

# regex patterns map
# helper: _apply_regex(text) -> (cleaned, flags)
# helper: _call_moderation_llm(text) -> flags
# helper: _redact_semantic(text, flags)

# moderate_input: regex only
# moderate_output: regex + LLM semantic, with fallback to regex-only
```

Include:
- OmniRoute client + OpenAI fallback (same pattern as reranker).
- **Schema validation**: `MOD_SCHEMA` requires `flags: [{category,text,action,reason?}]`.
- **Structured logs**: `log_event("moderation", {...})` with JSON payload (flag_count, sample_hash).
- If LLM fails → return regex-only result

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_moderator.py

def test_moderate_output_semantic_flags(monkeypatch):
 def fake_llm(*args, **kwargs):
 return '{"flags":[{"category":"financeiro","text":"R$ 9.000","action":"REDACT","reason":"valor"}]}'
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", fake_llm)
 cleaned, flags = moderate_output("Pagamento R$ 9.000")
 assert "[REDACTED:financeiro]" in cleaned

def test_moderation_fallback_openai(monkeypatch):
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.moderator._call_openai_fallback", lambda *a, **k: '{"flags":[]}')
 cleaned, flags = moderate_output("Texto neutro")
 assert cleaned == "Texto neutro"
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_moderator.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/moderator.py tests/test_moderator.py
git commit -m "feat: add moderation guardrails with redaction"
```

---

## Task 4: Wire rerank + moderation into step_enrich

**Files:**
- Modify: `ingest_worker/jobs/enrich.py`

- [ ] **Step 1: Write failing test** (optional; no existing unit tests for enrich.py) — skip

- [ ] **Step 2: Implement integration**

Insert near `step_enrich` after loading segments/transcript:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_segments
from lib.moderator import moderate_input

try:
 memory_snippets = search_context(meeting_name, params={}, limit=3)
except Exception as e:
 print(f"[rerank] [WARN] event=memory_search_failed meeting={meeting_id} error={e}")
 memory_snippets = []

moderated_transcript, input_flags = moderate_input(effective_transcript, cid=str(job["id"]), meeting_id=meeting_id)
ranked_segments = rerank_segments(segments, query=meeting_name, memory_snippets=memory_snippets, top_k=12)

# override inputs used by hook_pre_enrich/consolidator
# - effective_transcript = moderated_transcript
# - segments = ranked_segments
```

- [ ] **Step 3: Run lint/test smoke**

Run: `pytest tests/test_enrich.py::test_enrich_happy_path -v`
Expected: PASS (or skip if not available)

- [ ] **Step 4: Commit**

```bash
git add ingest_worker/jobs/enrich.py
git commit -m "feat: integrate rerank+moderation in enrich pipeline"
```

---

## Task 5: Wire rerank + moderation into insights generator

**Files:**
- Modify: `ingest_worker/lib/insights_generator.py`

- [ ] **Step 1: Write failing test** (optional; create minimal unit test)

```python
# tests/test_insights_generator_rerank.py
from ingest_worker.lib import insights_generator as ig

def test_generate_insights_reranks_flags(monkeypatch):
 monkeypatch.setattr(ig, "_call_llm", lambda *_: {"summary":"ok","flags":[{"text":"a"},{"text":"b"}]})
 monkeypatch.setattr("ingest_worker.lib.reranker.rerank_insights", lambda flags, *a, **k: [flags[1]])
 monkeypatch.setattr("ingest_worker.lib.moderator.moderate_output", lambda text, **_: (text, []))
 monkeypatch.setattr("ingest_worker.lib.insights_generator._save_insights", lambda *_: None)
 monkeypatch.setattr("ingest_worker.lib.insights_generator._get_meeting_context", lambda *_: {"id":"1","name":"x","meeting_type":"outro","created_at":"","topics":[],"decisions":[],"action_items":[],"enrichment_context":{},"insights_json":None,"insights_generated_at":None})
 res = ig.generate_insights("1", force=True)
 assert len(res["flags"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: FAIL (integration missing)

- [ ] **Step 3: Implement integration**

Insert after `_call_llm(prompt)`:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_insights
from lib.moderator import moderate_output

try:
 memory_snippets = search_context(ctx["name"], params={}, limit=3)
except Exception as e:
 print(f"[rerank] [WARN] event=memory_search_failed meeting={meeting_id} error={e}")
 memory_snippets = []

if result and result.get("flags"):
 result["flags"] = rerank_insights(result["flags"], query=ctx["name"], memory_snippets=memory_snippets, top_k=6)
if result and result.get("summary"):
 result["summary"], _flags = moderate_output(result["summary"], meeting_id=meeting_id)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ingest_worker/lib/insights_generator.py tests/test_insights_generator_rerank.py
git commit -m "feat: add rerank+moderation to insights generation"
```

---

## Task 6: Update docs / environment hints (optional)

**Files:**
- Modify: `CLAUDE.md` (if needed), `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`

- [ ] **Step 1: Ensure env vars documented**
- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-04-04-rerank-moderation-design.md
git commit -m "docs: update rerank/moderation env vars"
```

---

## Verification

Run the focused unit tests:

```bash
pytest tests/test_reranker.py tests/test_moderator.py tests/test_insights_generator_rerank.py -v
```

Expected: PASS

**Opcional (smoke):**
```bash
pytest tests/test_enrich.py -k "enrich" -v
```

---

## Rollout / Risk Notes

- OmniRoute down → fallback OpenAI direct (if `OPENAI_API_KEY` present).
- OpenAI down/absent → fallback to original order / regex-only.
- No schema changes needed.
- Logs are the only audit trail for moderation (phase 1).
- **Feature flags**: `RERANK_ENABLED` / `MODERATION_ENABLED` allow immediate disable if latency spikes.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-04-rerank-moderation-plan.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

---

## References

- Spec: `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`
- Memory search: `ingest_worker/lib/autoresearch/memory_search.py`
- Circuit breaker: `ingest_worker/lib/circuit_breaker.py`
- Insights generator: `ingest_worker/lib/insights_generator.py`
- Enricher: `ingest_worker/jobs/enrich.py`

---

*Generated by Livy ⚙️*
</file>
assistant: Review da v2 (pt‑BR) — está praticamente fechada. Só restam micro‑ajustes para evitar ambiguidade na implementação:

## ✅ OK / pronto
- Schema validation + fallback
- ID fallback + preservação de payload
- Cap de tamanho + resilience do `search_context`
- Logs estruturados centralizados
- Feature flags + fallback sem OpenAI

## ⚠️ Ajustes finais sugeridos (bem pequenos)
1) **Definir `RERANK_SCHEMA` / `MOD_SCHEMA` explicitamente**
   - Ex: `{"ranked": list[{"id": (str|int), "score": float, "reason": str?}], "warnings": list[str]}`  
   - E `{"flags": list[{"category": str, "text": str, "action": "REDACT"|"WARN", "reason"?: str}]}`  
   (evita interpretações diferentes por quem codar)

2) **Política de itens não retornados pelo LLM**
   - Já diz “append missing items”. Sugiro explicitar:  
     “**preservar ordem original dos missing + sem duplicação**”.

3) **Regex baseline mínimo**
   - Listar 3 regexes iniciais no plano (email, telefone, CPF/CNPJ) com 1 teste cada.  
   Isso evita o arquivo nascer “vazio”.

4) **`log_event`**
   - Dizer onde fica (ex: `lib/logging.py` ou no próprio módulo)  
   - e que o output é uma linha JSON (para grep).

Se quiser, posso devolver o plano já com esses 4 pontos inseridos como bullets objetivos.
user: [media attached: /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan_3---aec9d8b2-2824-4c0d-b8e5-f83a69cba7f4.md (text/markdown) | /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan_3---aec9d8b2-2824-4c0d-b8e5-f83a69cba7f4.md]
To send an image back, prefer the message tool (media/path/filePath). If you must inline, use MEDIA:https://example.com/image.jpg (spaces ok, quote if needed) or a safe relative path like MEDIA:./image.jpg. Avoid absolute paths (MEDIA:/...) and ~ paths — they are blocked for security. Keep caption in the text body.
Conversation info (untrusted metadata):
```json
{
  "message_id": "7897",
  "sender_id": "7426291192",
  "sender": "Lincoln Quinan Junior",
  "timestamp": "Sat 2026-04-04 03:00 UTC"
}
```

Sender (untrusted metadata):
```json
{
  "label": "Lincoln Quinan Junior (7426291192)",
  "id": "7426291192",
  "name": "Lincoln Quinan Junior",
  "username": "lincolnqjunior"
}
```

[Telegram Lincoln Quinan Junior (@lincolnqjunior) id:7426291192 +5m Sat 2026-04-04 03:00 UTC] Segue versão nova

<file name="2026-04-04-rerank-moderation-plan_3---aec9d8b2-2824-4c0d-b8e5-f83a69cba7f4.md" mime="text/markdown">
# Rerank + Moderação Guardrails (OmniRoute) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add listwise rerank + safety moderation to the tl;dv ingest pipeline (segments + insights), using OmniRoute `fastest` with OpenAI direct fallback, plus structured logs and retries.

**Architecture:** Add two focused modules (`reranker.py`, `moderator.py`) wired into `step_enrich` and `generate_insights`. Use existing `search_context()` for 3‑camadas memory and `circuit_breaker.py` for resilience. API regeneration inherits ingest_worker behavior.

**Tech Stack:** Python 3, OpenAI SDK, FastAPI (existing), OmniRoute local, pytest.

---

## File/Component Map

**Create:**
- `ingest_worker/lib/reranker.py` — listwise rerank with OmniRoute + OpenAI fallback, retry/backoff, circuit breaker, structured logs.
- `ingest_worker/lib/moderator.py` — regex redaction + LLM semantic moderation, retry/backoff, circuit breaker, structured logs.
- `tests/test_reranker.py` — unit tests for rerank logic.
- `tests/test_moderator.py` — unit tests for moderation logic.

**Modify:**
- `ingest_worker/lib/circuit_breaker.py` — add configs for `omniroute_rerank`, `omniroute_moderation`.
- `ingest_worker/jobs/enrich.py` — plug rerank+moderation in `step_enrich`.
- `ingest_worker/lib/insights_generator.py` — plug rerank+moderation in `generate_insights`.

---

## Additions from review (risks/lacunas)

- **Schema validation**: define constants `RERANK_SCHEMA` / `MOD_SCHEMA` and validate strictly; fallback on mismatch.
 - `RERANK_SCHEMA`: `{ranked: [{id: (str|int), score: float, reason?: str}], warnings: [str]}`
 - `MOD_SCHEMA`: `{flags: [{category: str, text: str, action: "REDACT"|"WARN", reason?: str}]}`
- **ID fallback**: if candidate item lacks `id`, use stable index (`idx`) and map back.
- **Preserve payload**: rerank returns full original item dicts; items not returned by LLM are appended in original order **sem duplicação**.
- **Latency/token cap**: cap total candidate text length (e.g., 6–8k chars) in addition to `candidate_limit`.
- **Search context resilience**: wrap `search_context()` in try/except; on failure, use empty list + log.
- **Structured logs**: centralize `log_event(event=..., data={...})` helper (e.g., `ingest_worker/lib/logging.py` or inside each module) and emit **one-line JSON** (grep-friendly).
- **Feature flags**: env toggles `RERANK_ENABLED` / `MODERATION_ENABLED` (default true).
- **OpenAI key absence**: if `OPENAI_API_KEY` missing, fallback directly to original order / regex-only.

---

## Task 1: Add circuit breaker configs

**Files:**
- Modify: `ingest_worker/lib/circuit_breaker.py`

- [ ] **Step 1: Write failing test** (optional, if no existing tests) — skip (no tests here)
- [ ] **Step 2: Implement config**

```python
_CIRCUIT_CONFIG = {
 # ... existing ...
 "omniroute_rerank": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
 "omniroute_moderation": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
}
```

- [ ] **Step 3: Commit**

```bash
git add ingest_worker/lib/circuit_breaker.py
git commit -m "chore: add circuit breaker configs for rerank/moderation"
```

---

## Task 2: Implement reranker module

**Files:**
- Create: `ingest_worker/lib/reranker.py`
- Test: `tests/test_reranker.py`

### API (target)

```python
def rerank_segments(segments: list[dict], query: str, memory_snippets: list[dict], top_k: int = 12, candidate_limit: int = 40) -> list[dict]:
 """Return full item dicts; append missing items in original order; stable ID fallback to idx."""

def rerank_insights(insights: list[dict], query: str, memory_snippets: list[dict], top_k: int = 6, candidate_limit: int = 20) -> list[dict]:
 """Return full item dicts; append missing items in original order; stable ID fallback to idx."""
```

- [ ] **Step 1: Write failing test**

```python
# tests/test_reranker.py
from ingest_worker.lib.reranker import rerank_segments

def test_rerank_segments_falls_back_on_invalid_json(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 def fake_call(*args, **kwargs):
 return "not-json"
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", fake_call)
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert ranked == segments
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/reranker.py
import json, re, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
RERANK_MODEL = os.getenv("RERANK_MODEL", "fastest")
RERANK_FALLBACK_MODEL = os.getenv("RERANK_FALLBACK_MODEL", "gpt-4o-mini")

def _call_rerank_llm(client: OpenAI, model: str, payload: dict) -> str:
 """Call chat.completions and return raw content string."""

def _parse_json(raw: str) -> dict | None:
 """Extract JSON object from raw text; return None if invalid."""

def _retry_with_backoff(fn, retries: int, delays: list[float]):
 """Retry helper with exponential backoff; re-raise last error."""
```

Include:
- OmniRoute client: `OpenAI(api_key=OMNIROUTE_API_KEY, base_url=OMNIROUTE_BASE_URL)`
- Fallback client: `OpenAI(api_key=OPENAI_API_KEY)` (if missing → skip OpenAI fallback)
- Retry 3x (1s,2s,4s) for OmniRoute; 2x for OpenAI fallback
- **Schema validation**: `RERANK_SCHEMA` requires `ranked: [{id, score, reason?}]` and `warnings: []`
- **ID fallback**: if candidate lacks `id`, assign `idx` and map back
- **Preserve payload**: return full item dicts; append LLM-missing items in original order
- **Latency cap**: truncate candidate text to total ~8k chars before LLM call
- **Structured logs**: `log_event("rerank", {...})` (JSON)
- If circuit open → immediate fallback
- If JSON parse fails → fallback to original order

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_reranker.py

def test_rerank_segments_uses_ranked_order(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: '{"ranked":[{"id":2,"score":0.9,"reason":"x"},{"id":1,"score":0.5,"reason":"y"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [2,1]


def test_rerank_fallback_openai_on_omniroute_failure(monkeypatch):
 segments = [{"id": 1, "text": "A"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.reranker._call_openai_fallback", lambda *a, **k: '{"ranked":[{"id":1,"score":0.9,"reason":"x"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [1]
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_reranker.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/reranker.py tests/test_reranker.py
git commit -m "feat: add listwise reranker with OmniRoute fallback"
```

---

## Task 3: Implement moderator module

**Files:**
- Create: `ingest_worker/lib/moderator.py`
- Test: `tests/test_moderator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_moderator.py
from ingest_worker.lib.moderator import moderate_input

def test_moderate_input_redacts_email():
 text = "contato: pessoa@empresa.com"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:email]" in cleaned

def test_moderate_input_redacts_phone():
 text = "telefone: +55 21 99999-0000"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:phone]" in cleaned

def test_moderate_input_redacts_cpf():
 text = "cpf 123.456.789-10"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:cpf]" in cleaned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/moderator.py
import re, json, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

# regex patterns map (mínimo):
# EMAIL = r"[\w.+-]+@[\w-]+\.[\w.-]+"
# PHONE_BR = r"\+?55?\s?\(?\d{2}\)?\s?\d{4,5}[-.\s]?\d{4}"
# CPF = r"\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11}"
# CNPJ = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}"

# helper: _apply_regex(text) -> (cleaned, flags)
# helper: _call_moderation_llm(text) -> flags
# helper: _redact_semantic(text, flags)

# moderate_input: regex only
# moderate_output: regex + LLM semantic, with fallback to regex-only
```

Include:
- OmniRoute client + OpenAI fallback (same pattern as reranker).
- **Schema validation**: `MOD_SCHEMA` requires `flags: [{category,text,action,reason?}]`.
- **Structured logs**: `log_event("moderation", {...})` with JSON payload (flag_count, sample_hash).
- If LLM fails → return regex-only result

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_moderator.py

def test_moderate_output_semantic_flags(monkeypatch):
 def fake_llm(*args, **kwargs):
 return '{"flags":[{"category":"financeiro","text":"R$ 9.000","action":"REDACT","reason":"valor"}]}'
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", fake_llm)
 cleaned, flags = moderate_output("Pagamento R$ 9.000")
 assert "[REDACTED:financeiro]" in cleaned

def test_moderation_fallback_openai(monkeypatch):
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.moderator._call_openai_fallback", lambda *a, **k: '{"flags":[]}')
 cleaned, flags = moderate_output("Texto neutro")
 assert cleaned == "Texto neutro"
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_moderator.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/moderator.py tests/test_moderator.py
git commit -m "feat: add moderation guardrails with redaction"
```

---

## Task 4: Wire rerank + moderation into step_enrich

**Files:**
- Modify: `ingest_worker/jobs/enrich.py`

- [ ] **Step 1: Write failing test** (optional; no existing unit tests for enrich.py) — skip

- [ ] **Step 2: Implement integration**

Insert near `step_enrich` after loading segments/transcript:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_segments
from lib.moderator import moderate_input

try:
 memory_snippets = search_context(meeting_name, params={}, limit=3)
except Exception as e:
 print(f"[rerank] [WARN] event=memory_search_failed meeting={meeting_id} error={e}")
 memory_snippets = []

moderated_transcript, input_flags = moderate_input(effective_transcript, cid=str(job["id"]), meeting_id=meeting_id)
ranked_segments = rerank_segments(segments, query=meeting_name, memory_snippets=memory_snippets, top_k=12)

# override inputs used by hook_pre_enrich/consolidator
# - effective_transcript = moderated_transcript
# - segments = ranked_segments
```

- [ ] **Step 3: Run lint/test smoke**

Run: `pytest tests/test_enrich.py::test_enrich_happy_path -v`
Expected: PASS (or skip if not available)

- [ ] **Step 4: Commit**

```bash
git add ingest_worker/jobs/enrich.py
git commit -m "feat: integrate rerank+moderation in enrich pipeline"
```

---

## Task 5: Wire rerank + moderation into insights generator

**Files:**
- Modify: `ingest_worker/lib/insights_generator.py`

- [ ] **Step 1: Write failing test** (optional; create minimal unit test)

```python
# tests/test_insights_generator_rerank.py
from ingest_worker.lib import insights_generator as ig

def test_generate_insights_reranks_flags(monkeypatch):
 monkeypatch.setattr(ig, "_call_llm", lambda *_: {"summary":"ok","flags":[{"text":"a"},{"text":"b"}]})
 monkeypatch.setattr("ingest_worker.lib.reranker.rerank_insights", lambda flags, *a, **k: [flags[1]])
 monkeypatch.setattr("ingest_worker.lib.moderator.moderate_output", lambda text, **_: (text, []))
 monkeypatch.setattr("ingest_worker.lib.insights_generator._save_insights", lambda *_: None)
 monkeypatch.setattr("ingest_worker.lib.insights_generator._get_meeting_context", lambda *_: {"id":"1","name":"x","meeting_type":"outro","created_at":"","topics":[],"decisions":[],"action_items":[],"enrichment_context":{},"insights_json":None,"insights_generated_at":None})
 res = ig.generate_insights("1", force=True)
 assert len(res["flags"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: FAIL (integration missing)

- [ ] **Step 3: Implement integration**

Insert after `_call_llm(prompt)`:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_insights
from lib.moderator import moderate_output

try:
 memory_snippets = search_context(ctx["name"], params={}, limit=3)
except Exception as e:
 print(f"[rerank] [WARN] event=memory_search_failed meeting={meeting_id} error={e}")
 memory_snippets = []

if result and result.get("flags"):
 result["flags"] = rerank_insights(result["flags"], query=ctx["name"], memory_snippets=memory_snippets, top_k=6)
if result and result.get("summary"):
 result["summary"], _flags = moderate_output(result["summary"], meeting_id=meeting_id)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ingest_worker/lib/insights_generator.py tests/test_insights_generator_rerank.py
git commit -m "feat: add rerank+moderation to insights generation"
```

---

## Task 6: Update docs / environment hints (optional)

**Files:**
- Modify: `CLAUDE.md` (if needed), `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`

- [ ] **Step 1: Ensure env vars documented**
- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-04-04-rerank-moderation-design.md
git commit -m "docs: update rerank/moderation env vars"
```

---

## Verification

Run the focused unit tests:

```bash
pytest tests/test_reranker.py tests/test_moderator.py tests/test_insights_generator_rerank.py -v
```

Expected: PASS

**Opcional (smoke):**
```bash
pytest tests/test_enrich.py -k "enrich" -v
```

---

## Rollout / Risk Notes

- OmniRoute down → fallback OpenAI direct (if `OPENAI_API_KEY` present).
- OpenAI down/absent → fallback to original order / regex-only.
- No schema changes needed.
- Logs are the only audit trail for moderation (phase 1).
- **Feature flags**: `RERANK_ENABLED` / `MODERATION_ENABLED` allow immediate disable if latency spikes.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-04-rerank-moderation-plan.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

---

## References

- Spec: `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`
- Memory search: `ingest_worker/lib/autoresearch/memory_search.py`
- Circuit breaker: `ingest_worker/lib/circuit_breaker.py`
- Insights generator: `ingest_worker/lib/insights_generator.py`
- Enricher: `ingest_worker/jobs/enrich.py`

---

*Generated by Livy ⚙️*
</file>
assistant: Revisão da versão nova: **está consistente e pronta para execução**. 👍

Só dois micro‑ajustes opcionais (se quiser deixar 100% blindado):

1) **Regex CNPJ**: você listou a regex mas não tem teste de CNPJ (só email/phone/CPF).  
   → opcional adicionar `test_moderate_input_redacts_cnpj`.

2) **`log_event`**: se for centralizar em `ingest_worker/lib/logging.py`, sugiro explicitar no plano o caminho exato para evitar implementação divergente.

Fora isso, o plano está fechado. Pode seguir para execução.
user: [media attached: /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan_4---89b79a31-58b8-498c-b0a9-ab083fd39345.md (text/markdown) | /home/lincoln/.openclaw/media/inbound/2026-04-04-rerank-moderation-plan_4---89b79a31-58b8-498c-b0a9-ab083fd39345.md]
To send an image back, prefer the message tool (media/path/filePath). If you must inline, use MEDIA:https://example.com/image.jpg (spaces ok, quote if needed) or a safe relative path like MEDIA:./image.jpg. Avoid absolute paths (MEDIA:/...) and ~ paths — they are blocked for security. Keep caption in the text body.
Conversation info (untrusted metadata):
```json
{
  "message_id": "7899",
  "sender_id": "7426291192",
  "sender": "Lincoln Quinan Junior",
  "timestamp": "Sat 2026-04-04 03:03 UTC"
}
```

Sender (untrusted metadata):
```json
{
  "label": "Lincoln Quinan Junior (7426291192)",
  "id": "7426291192",
  "name": "Lincoln Quinan Junior",
  "username": "lincolnqjunior"
}
```

[Telegram Lincoln Quinan Junior (@lincolnqjunior) id:7426291192 +2m Sat 2026-04-04 03:03 UTC] Segue versão nova

<file name="2026-04-04-rerank-moderation-plan_4---89b79a31-58b8-498c-b0a9-ab083fd39345.md" mime="text/markdown">
# Rerank + Moderação Guardrails (OmniRoute) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add listwise rerank + safety moderation to the tl;dv ingest pipeline (segments + insights), using OmniRoute `fastest` with OpenAI direct fallback, plus structured logs and retries.

**Architecture:** Add two focused modules (`reranker.py`, `moderator.py`) wired into `step_enrich` and `generate_insights`. Use existing `search_context()` for 3‑camadas memory and `circuit_breaker.py` for resilience. API regeneration inherits ingest_worker behavior.

**Tech Stack:** Python 3, OpenAI SDK, FastAPI (existing), OmniRoute local, pytest.

---

## File/Component Map

**Create:**
- `ingest_worker/lib/reranker.py` — listwise rerank with OmniRoute + OpenAI fallback, retry/backoff, circuit breaker, structured logs.
- `ingest_worker/lib/moderator.py` — regex redaction + LLM semantic moderation, retry/backoff, circuit breaker, structured logs.
- `tests/test_reranker.py` — unit tests for rerank logic.
- `tests/test_moderator.py` — unit tests for moderation logic.

**Modify:**
- `ingest_worker/lib/circuit_breaker.py` — add configs for `omniroute_rerank`, `omniroute_moderation`.
- `ingest_worker/jobs/enrich.py` — plug rerank+moderation in `step_enrich`.
- `ingest_worker/lib/insights_generator.py` — plug rerank+moderation in `generate_insights`.

---

## Additions from review (risks/lacunas)

- **Schema validation**: define constants `RERANK_SCHEMA` / `MOD_SCHEMA` and validate strictly; fallback on mismatch.
 - `RERANK_SCHEMA`: `{ranked: [{id: (str|int), score: float, reason?: str}], warnings: [str]}`
 - `MOD_SCHEMA`: `{flags: [{category: str, text: str, action: "REDACT"|"WARN", reason?: str}]}`
- **ID fallback**: if candidate item lacks `id`, use stable index (`idx`) and map back.
- **Preserve payload**: rerank returns full original item dicts; items not returned by LLM are appended in original order **sem duplicação**.
- **Latency/token cap**: cap total candidate text length (e.g., 6–8k chars) in addition to `candidate_limit`.
- **Search context resilience**: wrap `search_context()` in try/except; on failure, use empty list + log.
- **Structured logs**: centralize `log_event(event=..., data={...})` helper in `ingest_worker/lib/logging.py` and emit **one-line JSON** (grep-friendly).
- **Feature flags**: env toggles `RERANK_ENABLED` / `MODERATION_ENABLED` (default true).
- **OpenAI key absence**: if `OPENAI_API_KEY` missing, fallback directly to original order / regex-only.

---

## Task 1: Add circuit breaker configs

**Files:**
- Modify: `ingest_worker/lib/circuit_breaker.py`

- [ ] **Step 1: Write failing test** (optional, if no existing tests) — skip (no tests here)
- [ ] **Step 2: Implement config**

```python
_CIRCUIT_CONFIG = {
 # ... existing ...
 "omniroute_rerank": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
 "omniroute_moderation": CircuitConfig(failure_limit=3, window_seconds=900, recovery_seconds=120),
}
```

- [ ] **Step 3: Commit**

```bash
git add ingest_worker/lib/circuit_breaker.py
git commit -m "chore: add circuit breaker configs for rerank/moderation"
```

---

## Task 2: Implement reranker module

**Files:**
- Create: `ingest_worker/lib/reranker.py`
- Test: `tests/test_reranker.py`

### API (target)

```python
def rerank_segments(segments: list[dict], query: str, memory_snippets: list[dict], top_k: int = 12, candidate_limit: int = 40) -> list[dict]:
 """Return full item dicts; append missing items in original order; stable ID fallback to idx."""

def rerank_insights(insights: list[dict], query: str, memory_snippets: list[dict], top_k: int = 6, candidate_limit: int = 20) -> list[dict]:
 """Return full item dicts; append missing items in original order; stable ID fallback to idx."""
```

- [ ] **Step 1: Write failing test**

```python
# tests/test_reranker.py
from ingest_worker.lib.reranker import rerank_segments

def test_rerank_segments_falls_back_on_invalid_json(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 def fake_call(*args, **kwargs):
 return "not-json"
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", fake_call)
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert ranked == segments
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/reranker.py
import json, re, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
RERANK_MODEL = os.getenv("RERANK_MODEL", "fastest")
RERANK_FALLBACK_MODEL = os.getenv("RERANK_FALLBACK_MODEL", "gpt-4o-mini")

def _call_rerank_llm(client: OpenAI, model: str, payload: dict) -> str:
 """Call chat.completions and return raw content string."""

def _parse_json(raw: str) -> dict | None:
 """Extract JSON object from raw text; return None if invalid."""

def _retry_with_backoff(fn, retries: int, delays: list[float]):
 """Retry helper with exponential backoff; re-raise last error."""
```

Include:
- OmniRoute client: `OpenAI(api_key=OMNIROUTE_API_KEY, base_url=OMNIROUTE_BASE_URL)`
- Fallback client: `OpenAI(api_key=OPENAI_API_KEY)` (if missing → skip OpenAI fallback)
- Retry 3x (1s,2s,4s) for OmniRoute; 2x for OpenAI fallback
- **Schema validation**: `RERANK_SCHEMA` requires `ranked: [{id, score, reason?}]` and `warnings: []`
- **ID fallback**: if candidate lacks `id`, assign `idx` and map back
- **Preserve payload**: return full item dicts; append LLM-missing items in original order
- **Latency cap**: truncate candidate text to total ~8k chars before LLM call
- **Structured logs**: `log_event("rerank", {...})` (JSON)
- If circuit open → immediate fallback
- If JSON parse fails → fallback to original order

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reranker.py::test_rerank_segments_falls_back_on_invalid_json -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_reranker.py

def test_rerank_segments_uses_ranked_order(monkeypatch):
 segments = [{"id": 1, "text": "A"}, {"id": 2, "text": "B"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: '{"ranked":[{"id":2,"score":0.9,"reason":"x"},{"id":1,"score":0.5,"reason":"y"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [2,1]


def test_rerank_fallback_openai_on_omniroute_failure(monkeypatch):
 segments = [{"id": 1, "text": "A"}]
 monkeypatch.setattr("ingest_worker.lib.reranker._call_rerank_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.reranker._call_openai_fallback", lambda *a, **k: '{"ranked":[{"id":1,"score":0.9,"reason":"x"}],"warnings":[]}')
 ranked = rerank_segments(segments, query="q", memory_snippets=[])
 assert [s["id"] for s in ranked] == [1]
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_reranker.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/reranker.py tests/test_reranker.py
git commit -m "feat: add listwise reranker with OmniRoute fallback"
```

---

## Task 3: Implement moderator module

**Files:**
- Create: `ingest_worker/lib/moderator.py`
- Test: `tests/test_moderator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_moderator.py
from ingest_worker.lib.moderator import moderate_input

def test_moderate_input_redacts_email():
 text = "contato: pessoa@empresa.com"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:email]" in cleaned

def test_moderate_input_redacts_phone():
 text = "telefone: +55 21 99999-0000"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:phone]" in cleaned

def test_moderate_input_redacts_cpf():
 text = "cpf 123.456.789-10"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:cpf]" in cleaned

def test_moderate_input_redacts_cnpj():
 text = "cnpj 12.345.678/0001-90"
 cleaned, flags = moderate_input(text)
 assert "[REDACTED:cnpj]" in cleaned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: FAIL (module/function missing)

- [ ] **Step 3: Write minimal implementation**

```python
# ingest_worker/lib/moderator.py
import re, json, time
from openai import OpenAI
from lib.circuit_breaker import get_circuit, CircuitOpenError

# regex patterns map (mínimo):
# EMAIL = r"[\w.+-]+@[\w-]+\.[\w.-]+"
# PHONE_BR = r"\+?55?\s?\(?\d{2}\)?\s?\d{4,5}[-.\s]?\d{4}"
# CPF = r"\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11}"
# CNPJ = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}"

# helper: _apply_regex(text) -> (cleaned, flags)
# helper: _call_moderation_llm(text) -> flags
# helper: _redact_semantic(text, flags)

# moderate_input: regex only
# moderate_output: regex + LLM semantic, with fallback to regex-only
```

Include:
- OmniRoute client + OpenAI fallback (same pattern as reranker).
- **Schema validation**: `MOD_SCHEMA` requires `flags: [{category,text,action,reason?}]`.
- **Structured logs**: `log_event("moderation", {...})` with JSON payload (flag_count, sample_hash).
- If LLM fails → return regex-only result

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_moderator.py::test_moderate_input_redacts_email -v`
Expected: PASS

- [ ] **Step 5: Add more tests**

```python
# tests/test_moderator.py

def test_moderate_output_semantic_flags(monkeypatch):
 def fake_llm(*args, **kwargs):
 return '{"flags":[{"category":"financeiro","text":"R$ 9.000","action":"REDACT","reason":"valor"}]}'
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", fake_llm)
 cleaned, flags = moderate_output("Pagamento R$ 9.000")
 assert "[REDACTED:financeiro]" in cleaned

def test_moderation_fallback_openai(monkeypatch):
 monkeypatch.setattr("ingest_worker.lib.moderator._call_moderation_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("omniroute down")))
 monkeypatch.setattr("ingest_worker.lib.moderator._call_openai_fallback", lambda *a, **k: '{"flags":[]}')
 cleaned, flags = moderate_output("Texto neutro")
 assert cleaned == "Texto neutro"
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_moderator.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add ingest_worker/lib/moderator.py tests/test_moderator.py
git commit -m "feat: add moderation guardrails with redaction"
```

---

## Task 4: Wire rerank + moderation into step_enrich

**Files:**
- Modify: `ingest_worker/jobs/enrich.py`

- [ ] **Step 1: Write failing test** (optional; no existing unit tests for enrich.py) — skip

- [ ] **Step 2: Implement integration**

Insert near `step_enrich` after loading segments/transcript:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_segments
from lib.moderator import moderate_input

try:
 memory_snippets = search_context(meeting_name, params={}, limit=3)
except Exception as e:
 print(f"[rerank] [WARN] event=memory_search_failed meeting={meeting_id} error={e}")
 memory_snippets = []

moderated_transcript, input_flags = moderate_input(effective_transcript, cid=str(job["id"]), meeting_id=meeting_id)
ranked_segments = rerank_segments(segments, query=meeting_name, memory_snippets=memory_snippets, top_k=12)

# override inputs used by hook_pre_enrich/consolidator
# - effective_transcript = moderated_transcript
# - segments = ranked_segments
```

- [ ] **Step 3: Run lint/test smoke**

Run: `pytest tests/test_enrich.py::test_enrich_happy_path -v`
Expected: PASS (or skip if not available)

- [ ] **Step 4: Commit**

```bash
git add ingest_worker/jobs/enrich.py
git commit -m "feat: integrate rerank+moderation in enrich pipeline"
```

---

## Task 5: Wire rerank + moderation into insights generator

**Files:**
- Modify: `ingest_worker/lib/insights_generator.py`

- [ ] **Step 1: Write failing test** (optional; create minimal unit test)

```python
# tests/test_insights_generator_rerank.py
from ingest_worker.lib import insights_generator as ig

def test_generate_insights_reranks_flags(monkeypatch):
 monkeypatch.setattr(ig, "_call_llm", lambda *_: {"summary":"ok","flags":[{"text":"a"},{"text":"b"}]})
 monkeypatch.setattr("ingest_worker.lib.reranker.rerank_insights", lambda flags, *a, **k: [flags[1]])
 monkeypatch.setattr("ingest_worker.lib.moderator.moderate_output", lambda text, **_: (text, []))
 monkeypatch.setattr("ingest_worker.lib.insights_generator._save_insights", lambda *_: None)
 monkeypatch.setattr("ingest_worker.lib.insights_generator._get_meeting_context", lambda *_: {"id":"1","name":"x","meeting_type":"outro","created_at":"","topics":[],"decisions":[],"action_items":[],"enrichment_context":{},"insights_json":None,"insights_generated_at":None})
 res = ig.generate_insights("1", force=True)
 assert len(res["flags"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: FAIL (integration missing)

- [ ] **Step 3: Implement integration**

Insert after `_call_llm(prompt)`:

```python
from lib.autoresearch.memory_search import search_context
from lib.reranker import rerank_insights
from lib.moderator import moderate_output

try:
 memory_snippets = search_context(ctx["name"], params={}, limit=3)
except Exception as e:
 print(f"[rerank] [WARN] event=memory_search_failed meeting={meeting_id} error={e}")
 memory_snippets = []

if result and result.get("flags"):
 result["flags"] = rerank_insights(result["flags"], query=ctx["name"], memory_snippets=memory_snippets, top_k=6)
if result and result.get("summary"):
 result["summary"], _flags = moderate_output(result["summary"], meeting_id=meeting_id)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_insights_generator_rerank.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ingest_worker/lib/insights_generator.py tests/test_insights_generator_rerank.py
git commit -m "feat: add rerank+moderation to insights generation"
```

---

## Task 6: Update docs / environment hints (optional)

**Files:**
- Modify: `CLAUDE.md` (if needed), `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`

- [ ] **Step 1: Ensure env vars documented**
- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-04-04-rerank-moderation-design.md
git commit -m "docs: update rerank/moderation env vars"
```

---

## Verification

Run the focused unit tests:

```bash
pytest tests/test_reranker.py tests/test_moderator.py tests/test_insights_generator_rerank.py -v
```

Expected: PASS

**Opcional (smoke):**
```bash
pytest tests/test_enrich.py -k "enrich" -v
```

---

## Rollout / Risk Notes

- OmniRoute down → fallback OpenAI direct (if `OPENAI_API_KEY` present).
- OpenAI down/absent → fallback to original order / regex-only.
- No schema changes needed.
- Logs are the only audit trail for moderation (phase 1).
- **Feature flags**: `RERANK_ENABLED` / `MODERATION_ENABLED` allow immediate disable if latency spikes.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-04-rerank-moderation-plan.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

---

## References

- Spec: `docs/superpowers/specs/2026-04-04-rerank-moderation-design.md`
- Memory search: `ingest_worker/lib/autoresearch/memory_search.py`
- Circuit breaker: `ingest_worker/lib/circuit_breaker.py`
- Insights generator: `ingest_worker/lib/insights_generator.py`
- Enricher: `ingest_worker/jobs/enrich.py`

---

*Generated by Livy ⚙️*
</file>
assistant: Revisão da v4: **fechada e pronta para execução**. ✅  

Todos os pontos críticos já estão cobertos (schema, fallback, regex, logs, flags).  
Nenhum ajuste adicional necessário. Pode seguir para execução.
