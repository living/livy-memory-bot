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

## Query Routing

Determine query complexity before executing:

### Simple queries (direct search)
- Contains a specific repo/tag/keyword: e.g. "delphos-svd", "kaba", "PR #23"
- Contains a date range
- Ask "what was decided about X"
→ Use: Direct grep on decisions/*.md with regex, no cross-reference

### Entity queries (people/meetings)
- Ask about a person or meeting
- "who is X?", "what meetings had Y?"
→ Use: entities/ lookup + optional cross-reference

### Complex queries (synthesis)
- Ask "what is happening with project X?"
- Needs cross-source synthesis
- "compare X across sources"
→ Use: Full protocol (search → fetch → cross-ref → synthesize)

## Result Limits

To prevent timeout and manage token usage:

| Query Type | Max Results | Behavior |
|---|---|---|
| Simple keyword | 20 | Early exit, no cross-ref |
| Entity lookup | 10 | Limit to top 10 by recency |
| Concept trace | 15 | Limit to 5 most recent per source |
| Decision history | 30 | Limit by date range |
| Complex/synthesis | 20 | Paginate, agent decides |

### Complexity budget
- Maximum 5 files to cross-reference per query
- Maximum 3 relationship hops
- If exceeded: return top-N by relevance score, signal pagination

## Relevancy Scoring

Each result is scored before being returned to the agent:

| Signal | Score | Notes |
|---|---|---|
| Exact keyword match in text | +10 | Case-insensitive |
| Keyword in tags | +5 | |
| Keyword in source_ref | +3 | |
| Recency (last 30 days) | +2 | |
| Keyword in title/header | +8 | |
| Multiple keyword occurrences | +1 per extra | Max +5 |

Results are sorted by score descending before being returned.
Results with score < 3 are excluded.

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

## Caching

The vault-query agent uses a simple in-memory cache with TTL to avoid re-reading large files:

### Cache strategy
- `index.md` (27KB): cached for 5 minutes, invalidated on writes to vault
- `relationships/` graph: NOT cached (too dynamic)
- `decisions/*.md`: always read directly (small files, ~1-5KB each)

### Cache key
Cached by: workspace path + file path + mtime

### Invalidation
Cache is invalidated when:
- Any write to the vault occurs
- `.cursors/` files change
- Force refresh requested by agent

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

## Structured Decision Lookup

The `decisions/*.md` files have a structured format enabling O(1) tag lookups instead of O(n) text grep.

### Decision block format
```
### YYYY-MM-DD — source

> decision text here

- **Source:** github:org/repo#N  |  tldv:meeting_id  |  trello:card_id
- **Confidence:** 0.92
- **Tags:** tag1, tag2, tag3
```

### Lookup strategies

| Strategy | Method | Speed |
|---|---|---|
| By tag | Pre-built tag index | O(1) |
| By date range | Sorted blocks by date | O(log n) |
| By source_ref | Exact match on Source field | O(n) |
| By text content | Full text search | O(n) |

### Usage in query protocol
1. For "decisions about X": build tag index first, lookup by tag
2. For "decisions from GitHub": filter by source_ref prefix
3. For "recent decisions": binary search by date

## Optional Cross-Reference

Cross-referencing the relationships graph is expensive (loads 36KB of edges). It should only be done when needed.

### When to cross-reference
- Entity queries: always (need to find person across Trello/GitHub/TLDV)
- Concept traces: optional (helps find related entities)
- Simple keyword queries: **never** (direct search sufficient)
- Decision history: optional (only if result count < 5)

### Cross-reference budget
- Maximum 5 files cross-referenced per query (ComplexityBudget)
- Maximum 3 relationship hops
- If budget exhausted: return direct search results only

### How to skip cross-reference
```
if is_simple_keyword_query(query):
    return direct_search_results  # No cross-ref
elif is_entity_query(query) or budget.can_cross_ref():
    results = direct_search_results
    if budget.can_cross_ref():
        results += cross_reference(budget)
    return results
```
