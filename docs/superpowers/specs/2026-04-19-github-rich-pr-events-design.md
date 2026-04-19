# GitHub Rich PR Events — Design Spec (2026-04-19)

## 1) Goal

Expand GitHub PR ingestion in the research pipeline from lightweight merge metadata to a rich event model suitable for:

- identity/context enrichment,
- crosslink hypotheses (GitHub ↔ Trello ↔ Issues),
- historical/backfill processing across PR lifecycle states,
- dual representation: immutable raw snapshot + derived sanitized view.

---

## 2) Event Schema

### 2.1 Raw layer (immutable)

`raw_payload` preserves full fetched structures as returned by GitHub APIs (REST + GraphQL):

```json
{
  "pr": {"...": "full PR payload"},
  "reviews": [{"...": "review"}],
  "issue_comments": [{"...": "issue comment"}],
  "review_comments": [{"...": "review comment"}],
  "linked_issues": [{"...": "crossReferences node"}],
  "fetched_at": "ISO timestamp",
  "repo": "owner/repo",
  "pr_number": 123
}
```

Rules:
- No text mutation in raw layer.
- No field dropping unless API omitted field.
- Always store arrays, even when empty.

### 2.2 Sanitized layer (derived)

`sanitized_view` is a deterministic projection from raw:

```json
{
  "source": "github",
  "event_type": "github:pr_rich",
  "id": "owner/repo#123",
  "repo": "owner/repo",
  "pr_number": 123,
  "state": "open|closed|merged|draft|ready_for_review",
  "title": "...",
  "body": "sanitized text",
  "created_at": "...",
  "updated_at": "...",
  "merged_at": "...|null",
  "author": {"login": "...", "id": 1},
  "labels": [{"name": "bug", "color": "f00"}],
  "milestone": {"title": "M1", "number": 7}|null,
  "assignees": [{"login": "..."}],
  "requested_reviewers": [{"login": "..."}],
  "reviews": [{"id": 1, "state": "APPROVED", "user": {"login": "..."}, "body": "..."}],
  "issue_comments": [{"id": 2, "user": {"login": "..."}, "body": "..."}],
  "review_comments": [{"id": 3, "user": {"login": "..."}, "body": "..."}],
  "linked_issues": [{"id": "...", "number": 99, "url": "...", "title": "..."}]
}
```

Rules:
- Preserve semantic text, remove mechanical noise only.
- Dedupe by (`id`, text_hash) for comments/reviews.
- Keep references to originals for traceability.

---

## 3) Required API Calls

## 3.1 PR listing (all states)

- `gh api repos/{repo}/pulls --paginate -f state=open -f sort=updated -f direction=desc`
- `gh api repos/{repo}/pulls --paginate -f state=closed -f sort=updated -f direction=desc`

State derivation:
- merged: `merged_at != null`
- draft: `draft == true`
- ready_for_review: `draft == false && state == open`
- closed: `state == closed && merged_at == null`
- open: included in open list.

## 3.2 Per-PR rich fetch

- Full PR: `gh api repos/{repo}/pulls/{number}`
- Reviews: `gh api repos/{repo}/pulls/{number}/reviews --paginate`
- Review comments: `gh api repos/{repo}/pulls/{number}/comments --paginate`
- Issue comments: `gh api repos/{repo}/issues/{number}/comments --paginate`

Labels/milestone/assignees/requested_reviewers come from full PR payload.

## 3.3 Linked issues via GraphQL

Use `gh api graphql --jq .` query on PR node and `crossReferences(first: 100)`.
Extract issues/PR references for crosslink hypotheses.

---

## 4) Sanitization Rules

Text sanitization helper (`_sanitize_text`):
- Normalize CRLF to LF.
- Collapse repeated blank lines (max 2).
- Remove boilerplate signatures/footers (e.g., `Co-authored-by:`, bot-generated trailers).
- Remove obvious bot spam patterns (`[bot]`, repetitive automation comments).
- Keep meaningful prose, issue references, Trello URLs, and action verbs.

Dedup helper:
- Compute SHA-256 hash on sanitized text.
- Dedupe comments/reviews by tuple `(id, hash)` preserving first-seen order.

Crosslink extraction:
- `_extract_trello_urls(text)` → list of Trello card/board URLs.
- `_extract_github_refs(text)` → issue/PR refs (`#123`, `owner/repo#123`, URLs).

---

## 5) Pipeline Integration Points

1. Introduce `GitHubRichClient` (new file) to avoid breaking existing `GitHubClient`.
2. In `ResearchPipeline.run()` for source `github`:
   - keep lightweight events fetch,
   - enrich each event with `GitHubRichClient.fetch_rich_pr(...)`,
   - pass rich payload into `_build_context(...)`.
3. Add `_build_github_hypothesis(event)` that:
   - scans PR body/comments/reviews,
   - extracts Trello URLs + GitHub refs,
   - emits typed crosslink hypotheses:
     - `mentions`
     - `implements`
     - `blocks`
     - `reviews`
     - `approved_by`
4. Preserve existing behavior for non-rich sources.

---

## 6) Test Plan

### 6.1 Client schema tests

`tests/research/test_github_rich_client.py`:
- rich PR contains body + metadata,
- reviews/comments endpoints fetched,
- labels/milestone/assignees/reviewers captured,
- linked issues fetched via GraphQL,
- normalized event includes complete rich fields,
- raw payload immutable,
- sanitized view dedupes duplicates,
- all PR states fetched.

### 6.2 Pipeline integration tests

`tests/research/test_github_rich_pipeline.py`:
- pipeline uses rich client for enrichment,
- rich payload reaches context builder,
- crosslink hypotheses include GitHub relations,
- backfill/state fetch handles historical PRs.

### 6.3 Validation

- Run RED first and confirm failures.
- Implement minimal GREEN.
- Refactor while staying green.
- Run full research test suite.
- Compile checks on modified/new Python files.

---

## 7) Backwards Compatibility

- Keep `vault/research/github_client.py` unchanged for legacy tests and existing consumers.
- Rich behavior is additive (`github_rich_client.py` + pipeline integration).
- Existing tests (`test_github_client.py`, `test_pipeline_github.py`) remain unmodified.
