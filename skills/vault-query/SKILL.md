---
name: vault-query
description: Query the Living Memory vault wiki — search entities, trace provenance, cross-reference sources, generate insights. Creates new pages when queries produce synthesis.
---

# Vault Query Skill

## When to Use

- User asks about meetings, people, projects, or decisions in Living's memory
- Need to trace why an entity exists (provenance)
- Cross-reference across TLDV, Trello, GitHub sources
- Generate synthesis or concept pages from query results

## Vault Structure

```
memory/vault/
├── index.md              # Catalog of all pages
├── log.md                # Run history
├── entities/             # People, meetings, cards
├── concepts/             # Domain concepts
├── decisions/            # Decision records
├── relationships/        # Entity edges
├── .cursors/             # Incremental state + locks
├── .delivery-failures.jsonl
└── log-archive/
```

## Query Protocol

1. **Search** — Read `index.md` to find relevant pages
2. **Fetch** — Read specific entity/concept/decision pages
3. **Cross-reference** — Use `relationships/` for connections
4. **Synthesize** — If query produces new insight, create a page using templates

## 6 Query Types

| Type | Description | Example |
|---|---|---|
| entity lookup | Find entity by id_canonical or source_key | "Who is person X?" |
| concept trace | Follow concept across entities | "What meetings discussed BAT?" |
| decision history | Find decisions by topic/project | "What was decided about whisper?" |
| provenance | Trace entity back to source events | "Why does this person exist?" |
| cross-reference | Match entities across sources | "Is this person in Trello too?" |
| gap analysis | Find missing connections | "Who hasn't been seen in 30 days?" |

## Trust Policy

- `high` confidence: auto-derived from official source (API)
- `medium` confidence: derived from transcript/heuristic
- `low` confidence: derived from name-matching only
- Never auto-promote above source confidence

## Creating Pages

When a query generates a new insight:
1. Use appropriate template from `templates/`
2. Include `provenance` frontmatter with `source`, `source_key`, `fetched_at`, `run_id`
3. Add entry to `index.md`
4. Log the creation in `log.md`
