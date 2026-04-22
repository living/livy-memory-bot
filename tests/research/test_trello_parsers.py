"""Tests for vault.research.trello_parsers — decision extraction from comments/checklists."""
from __future__ import annotations

import pytest

from vault.research.trello_parsers import (
    ParsedTrelloCard,
    card_to_claims,
    parse_trello_card,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(
    card_id: str = "card_1",
    name: str = "Test Card",
    desc: str = "",
    comments: list[dict] | None = None,
    checklists: list[dict] | None = None,
) -> dict:
    """Minimal card payload for testing."""
    payload = {
        "id": card_id,
        "name": name,
        "url": f"https://trello.com/c/{card_id}",
        "idBoard": "board_1",
        "desc": desc,
        "labels": [],
        "dateLastActivity": "2026-04-21T12:00:00.000Z",
    }
    if comments is not None:
        payload["_comments"] = comments
    if checklists is not None:
        payload["_checklists"] = checklists
    return payload


# ---------------------------------------------------------------------------
# card_to_claims — decision extraction from comments
# ---------------------------------------------------------------------------

def test_card_to_claims_extracts_decision_from_comment(mocker):
    """Comments containing decision-like text (>=5 words) yield decision claims."""
    card = _make_card(
        card_id="card_decision_1",
        name="Refactor auth module",
        comments=[
            {
                "text": "Vamos migrar para OAuth 2.0 na próxima sprint",
                "creator": "alice",
                "date": "2026-04-20T10:00:00.000Z",
            },
            {
                "text": "Adicionei logs",  # < 5 words — should be ignored
                "creator": "bob",
                "date": "2026-04-20T11:00:00.000Z",
            },
        ],
    )

    parsed = parse_trello_card(card, list_name="Doing")

    # The parser should store comments on the parsed card
    assert hasattr(parsed, "comments")
    assert len(parsed.comments) == 1  # only the >=5 word comment

    claims = card_to_claims(parsed)

    # Should still produce the status claim
    status_claims = [c for c in claims if c["claim_type"] == "status"]
    assert len(status_claims) == 1

    # Should produce one decision claim from the comment
    decision_claims = [c for c in claims if c["claim_type"] == "decision"]
    assert len(decision_claims) == 1

    decision = decision_claims[0]
    assert decision["needs_review"] is True
    assert decision["review_reason"] == "comentario_trello"
    assert decision["confidence"] == 0.40
    assert "OAuth" in decision["text"]


def test_card_to_claims_extracts_multiple_decisions_from_comments(mocker):
    """Multiple comments with >=5 words each produce multiple decision claims."""
    card = _make_card(
        card_id="card_multi",
        name="Multi decision card",
        comments=[
            {"text": "Aprovado: usar Redis para cache", "creator": "alice", "date": "2026-04-20T09:00:00.000Z"},
            {"text": "Confirmado que vamos persistir no PostgreSQL", "creator": "bob", "date": "2026-04-20T10:00:00.000Z"},
            {"text": "OK", "creator": "carol", "date": "2026-04-20T11:00:00.000Z"},  # < 5 words
        ],
    )

    parsed = parse_trello_card(card, list_name="Done")
    claims = card_to_claims(parsed)

    decision_claims = [c for c in claims if c["claim_type"] == "decision"]
    assert len(decision_claims) == 2
    assert any("Redis" in c["text"] for c in decision_claims)
    assert any("PostgreSQL" in c["text"] for c in decision_claims)


# ---------------------------------------------------------------------------
# card_to_claims — decision extraction from checklists
# ---------------------------------------------------------------------------

def test_card_to_claims_extracts_decision_from_checklist(mocker):
    """Checklist items containing decision-like text (>=5 words) yield decision claims."""
    card = _make_card(
        card_id="card_checklist_1",
        name="Deploy checklist",
        checklists=[
            {
                "id": "checklist_1",
                "name": "Deploy Steps",
                "checkItems": [
                    {"name": "Definido: rodar migrations do banco de dados primeiro", "state": "complete"},
                    {"name": "Deploy", "state": "incomplete"},  # < 5 words
                ],
            }
        ],
    )

    parsed = parse_trello_card(card, list_name="Review")
    assert hasattr(parsed, "checklists")
    assert len(parsed.checklists) == 1  # only the >=5 word item

    claims = card_to_claims(parsed)

    decision_claims = [c for c in claims if c["claim_type"] == "decision"]
    assert len(decision_claims) == 1
    assert decision_claims[0]["needs_review"] is True
    assert decision_claims[0]["review_reason"] == "comentario_trello"
    assert decision_claims[0]["confidence"] == 0.40
    assert "migrations" in decision_claims[0]["text"]


def test_card_to_claims_combines_decisions_from_comments_and_checklists(mocker):
    """Comments and checklists both contribute decision claims."""
    card = _make_card(
        card_id="card_both",
        name="Mixed card",
        comments=[
            {"text": "Decisão: usar Webhooks para notifications", "creator": "alice", "date": "2026-04-20T09:00:00.000Z"},
        ],
        checklists=[
            {
                "id": "checklist_1",
                "name": "Setup",
                "checkItems": [
                    {"name": "Decisão: configurar variáveis de ambiente antes de subir", "state": "complete"},
                ],
            }
        ],
    )

    parsed = parse_trello_card(card, list_name="To Do")

    claims = card_to_claims(parsed)

    decision_claims = [c for c in claims if c["claim_type"] == "decision"]
    assert len(decision_claims) == 2
    texts = [c["text"] for c in decision_claims]
    assert any("Webhooks" in t for t in texts)
    assert any("ambiente" in t for t in texts)


# ---------------------------------------------------------------------------
# card_to_claims — fallback when comments/checklists unavailable
# ---------------------------------------------------------------------------

def test_card_to_claims_no_comments_no_checklists_emits_no_decision_claims(mocker, caplog):
    """When a card has no comments or checklists, no decision claims are emitted."""
    card = _make_card(
        card_id="card_plain",
        name="Plain card",
        desc="Just a description.",
    )

    parsed = parse_trello_card(card, list_name="Backlog")
    claims = card_to_claims(parsed)

    decision_claims = [c for c in claims if c["claim_type"] == "decision"]
    assert len(decision_claims) == 0

    # Should have logged the warning
    assert any("trello_comments_unavailable" in record.message for record in caplog.records)


def test_card_to_claims_empty_comments_list_emits_no_decision_claims(mocker, caplog):
    """Empty comments list should also trigger the fallback warning."""
    card = _make_card(
        card_id="card_empty",
        name="Empty comments card",
        comments=[],
    )

    parsed = parse_trello_card(card, list_name="To Do")
    claims = card_to_claims(parsed)

    decision_claims = [c for c in claims if c["claim_type"] == "decision"]
    assert len(decision_claims) == 0
    assert any("trello_comments_unavailable" in record.message for record in caplog.records)


def test_card_to_claims_all_short_comments_emits_no_decision_claims(mocker, caplog):
    """Comments with fewer than 5 words should not produce decision claims."""
    card = _make_card(
        card_id="card_short",
        name="Short comments card",
        comments=[
            {"text": "OK", "creator": "alice", "date": "2026-04-20T09:00:00.000Z"},
            {"text": "LGTM", "creator": "bob", "date": "2026-04-20T10:00:00.000Z"},
        ],
    )

    parsed = parse_trello_card(card, list_name="Review")
    claims = card_to_claims(parsed)

    decision_claims = [c for c in claims if c["claim_type"] == "decision"]
    assert len(decision_claims) == 0
    assert any("trello_comments_unavailable" in record.message for record in caplog.records)


def test_card_to_claims_comments_with_5_plus_words_without_keyword_emit_no_decisions(mocker, caplog):
    """Comments must match decision keywords; word count alone is not enough."""
    card = _make_card(
        card_id="card_no_keyword",
        name="No keyword card",
        comments=[
            {
                "text": "Precisamos revisar a documentação ainda hoje",
                "creator": "alice",
                "date": "2026-04-20T09:00:00.000Z",
            },
        ],
    )

    parsed = parse_trello_card(card, list_name="Review")
    claims = card_to_claims(parsed)

    decision_claims = [c for c in claims if c["claim_type"] == "decision"]
    assert len(decision_claims) == 0
    assert any("trello_comments_unavailable" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Existing behavior preserved
# ---------------------------------------------------------------------------

def test_card_to_claims_preserves_status_claim_when_decisions_exist(mocker):
    """Adding decision extraction must not break the existing status claim."""
    card = _make_card(
        card_id="card_status",
        name="Feature card",
        comments=[{"text": "Decisão: usar GraphQL para queries complexas", "creator": "alice", "date": "2026-04-20T09:00:00.000Z"}],
    )

    parsed = parse_trello_card(card, list_name="In Progress")
    claims = card_to_claims(parsed)

    status_claims = [c for c in claims if c["claim_type"] == "status"]
    assert len(status_claims) == 1
    assert "In Progress" in status_claims[0]["text"]


def test_card_to_claims_preserves_github_linkage_when_decisions_exist(mocker):
    """Adding decision extraction must not break the existing GitHub linkage claims."""
    card = _make_card(
        card_id="card_linkage",
        name="Feature card with PR",
        desc="Veja https://github.com/living/livy/pull/99",
        comments=[{"text": "Aprovado para merge após code review", "creator": "alice", "date": "2026-04-20T09:00:00.000Z"}],
    )

    parsed = parse_trello_card(card, list_name="Done")
    claims = card_to_claims(parsed)

    linkage_claims = [c for c in claims if c["claim_type"] == "linkage"]
    assert len(linkage_claims) == 1
    assert "pull/99" in linkage_claims[0]["metadata"]["link_url"]


# =============================================================================
# QUICK WIN: Concluído/Done/Liberado list → decision claim
# Root cause: card_to_claims only generates status for these cards
# Expected: card in "Concluído 🎉 (Entregue)" should yield a decision claim
# =============================================================================

def _make_concluido_card(list_name: str) -> ParsedTrelloCard:
    """Card in a completion list — no comments, no checklists."""
    return ParsedTrelloCard(
        card_id="card-concluido-test",
        card_name="Adapter Feriados: lidar com duplicidades",
        card_url="https://trello.com/c/test/123",
        board_id="board-1",
        list_name=list_name,
        labels=[],
        due_date=None,
        github_links=[],
        hours_logged=0.0,
        last_activity="2026-04-20T10:00:00Z",
        comments=[],
        checklists=[],
    )


class TestTrelloCompletionListDecision:
    """Quick win: cards in Concluído/Done/Liberado lists should produce decision claims."""

    @pytest.mark.parametrize("list_name", [
        "Concluído 🎉 (Entregue)",
        "DONE",
        "Concluído 🎉",
        "Liberado Teste interno",
    ])
    def test_concluido_card_produces_decision_claim(self, list_name: str):
        """A card in a completion list (no comments/checklists) should still yield a decision."""
        card = _make_concluido_card(list_name)
        claims = card_to_claims(card)
        claim_types = {c["claim_type"] for c in claims}
        assert "decision" in claim_types, (
            f"Expected 'decision' in {claim_types} for card in '{list_name}'. "
            f"card_to_claims only generates status for completion-list cards — "
            f"this is the root cause of 0% Trello decisions."
        )

    @pytest.mark.parametrize("list_name", [
        "Em andamento",
        "BACKLOG",
        "TO DO",
        "DOING",
    ])
    def test_non_concluido_list_no_decision_claim(self, list_name: str):
        """A card NOT in a completion list should NOT get a decision claim."""
        card = _make_concluido_card(list_name)
        claims = card_to_claims(card)
        claim_types = {c["claim_type"] for c in claims}
        assert "decision" not in claim_types

    def test_concluido_decision_has_correct_metadata(self):
        """Decision claim from completion list should have correct metadata."""
        card = _make_concluido_card("Concluído 🎉 (Entregue)")
        claims = card_to_claims(card)
        dec = next((c for c in claims if c["claim_type"] == "decision"), None)
        assert dec is not None
        assert dec["source"] == "trello"
        assert dec["entity_type"] == "project"
        assert dec["entity_id"] == "card-concluido-test"
        assert "concluido" in dec["text"].lower() or "concluído" in dec["text"].lower()

    def test_concluido_card_also_produces_linkage_to_delivery_stage(self):
        """Completion-list cards should produce linkage claim to delivery stage."""
        card = _make_concluido_card("Concluído 🎉 (Entregue)")
        claims = card_to_claims(card)
        linkage = [c for c in claims if c["claim_type"] == "linkage"]
        assert len(linkage) >= 1
        assert any(c.get("metadata", {}).get("link_type") == "trello_delivery_stage" for c in linkage)


# =============================================================================
# QUICK WIN: github_links already work as linkage — validate existing behavior
# =============================================================================

def _make_card_with_gh_links(github_links: list[str]) -> ParsedTrelloCard:
    return ParsedTrelloCard(
        card_id="card-gh-test",
        card_name="Test GH link card",
        card_url="https://trello.com/c/gh/123",
        board_id="board-1",
        list_name="DONE",
        labels=[],
        due_date=None,
        github_links=github_links,
        hours_logged=0.0,
        last_activity="2026-04-20T10:00:00Z",
        comments=[],
        checklists=[],
    )


class TestTrelloGithubLinkage:
    """github_links → linkage claims (already works, validate it stays working)."""

    def test_github_links_produce_linkage_claims(self):
        card = _make_card_with_gh_links(["https://github.com/living/BAT-CONECTABOT-GLOBAL-APP-BRASIL/actions/new"])
        claims = card_to_claims(card)
        linkage = [c for c in claims if c["claim_type"] == "linkage"]
        assert len(linkage) >= 1, f"Expected linkage claims for github_links, got {len(linkage)}"

    def test_github_links_in_metadata(self):
        card = _make_card_with_gh_links(["https://github.com/living/repo/pull/99"])
        claims = card_to_claims(card)
        gh_link = next((c for c in claims if c["claim_type"] == "linkage" and c["metadata"].get("link_type") == "github"), None)
        assert gh_link is not None, f"Expected github linkage in {claims}"
        assert gh_link["metadata"]["link_url"] == "https://github.com/living/repo/pull/99"
        assert gh_link["metadata"]["link_type"] == "github"
