# honcho-query Skill

## Trigger
Use when: user asks about lessons, past decisions, what was decided about X, what happened with PR #N, or any question that requires searching the institutional memory of past decisions.

## Interface

### `honcho_query(query: str, topK: int = 5) -> list[dict]`

**Fast path:** Searches Honcho peer knowledge base via HTTP API (`POST /v1/search`).

**Fallback:** If Honcho is unreachable or returns empty, performs grep-like text search over `memory/vault/lessons/*.md`.

**Returns:**
```python
[
  {"text": "PR #24 — Enriched Claims Rollout", "source": "memory/vault/lessons/2026-04-21-...md", "path": "..."},
  ...
]
```

### `honcho_health_check() -> bool`
Check if Honcho daemon is reachable at `http://100.121.74.111:8000`.

## Usage

```python
from vault.insights.honcho_query import honcho_query, honcho_health_check

# Check health
if honcho_health_check():
    print("Honcho is up")

# Query lessons
results = honcho_query("enriched claims quality guardrail", topK=5)
for r in results:
    print(r["text"], "|", r["source"])
```

## Environment Variables
- `HONCHO_ENDPOINT` — Honcho API URL (default: `http://100.121.74.111:8000`)
- `HONCHO_API_KEY` — API key for Honcho

## Notes
- Lessons are primary storage in `memory/vault/lessons/` (versioned, portable)
- Honcho is a fast semantic cache — not authoritative
- If Honcho returns empty, disk fallback always works
- Template file (`TEMPLATE.md`) is never included in results
