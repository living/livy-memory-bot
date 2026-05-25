"""Tests for QW-3 contradiction detection."""
import pytest
from vault.qw3.contradiction import (
    detect_contradiction,
    check_topic_for_contradictions,
    _has_negation,
    _has_affirmation,
    Contradiction,
)


class TestNegationAffirmation:
    def test_has_negation_nao(self):
        assert _has_negation("não fazer deploy aos domingos")

    def test_has_negation_never(self):
        assert _has_negation("never do this")

    def test_has_negation_not(self):
        assert _has_negation("do not merge without approval")

    def test_has_negation_false_positive(self):
        # "not" in "notification" should NOT match
        assert not _has_negation("send notification via webhook")

    def test_has_affirmative_sim(self):
        assert _has_affirmation("sim, implementar o deploy")

    def test_has_affirmative_approve(self):
        assert _has_affirmation("approve PR #123")

    def test_has_affirmative_add(self):
        assert _has_affirmation("adicionar novo endpoint")


class TestDetectContradiction:
    def test_opposing_signals_detected(self):
        """'do X' vs 'do not do X' should be a contradiction."""
        new = {
            "text": "implementar autenticação JWT",
            "source_ref": "github:living/delphos#10",
            "date": "2026-05-25",
            "source": "github",
            "confidence": 0.9,
        }
        existing = {
            "text": "não usar autenticação JWT — usar OAuth2",
            "source_ref": "github:living/delphos#5",
            "date": "2026-05-20",
            "source": "github",
            "confidence": 0.85,
        }
        contrs = detect_contradiction(new, [existing])
        assert len(contrs) == 1
        assert contrs[0].severity == "high"
        assert contrs[0].existing_ref == "github:living/delphos#5"

    def test_same_signal_no_contradiction(self):
        """Two affirmative decisions should not contradict."""
        new = {
            "text": "implementar autenticação JWT",
            "source_ref": "github:living/delphos#10",
            "date": "2026-05-25",
            "source": "github",
            "confidence": 0.9,
        }
        existing = {
            "text": "usar JWT com RS256 para autenticação",
            "source_ref": "github:living/delphos#5",
            "date": "2026-05-20",
            "source": "github",
            "confidence": 0.85,
        }
        contrs = detect_contradiction(new, [existing])
        assert len(contrs) == 0

    def test_no_keyword_overlap_no_contradiction(self):
        """Decisions about different topics should not contradict."""
        new = {
            "text": "implementar autenticação JWT",
            "source_ref": "github:living/delphos#10",
            "date": "2026-05-25",
            "source": "github",
            "confidence": 0.9,
        }
        existing = {
            "text": "revisar pipeline CI/CD do projeto BAT",
            "source_ref": "github:living/bat#3",
            "date": "2026-05-20",
            "source": "github",
            "confidence": 0.8,
        }
        contrs = detect_contradiction(new, [existing])
        assert len(contrs) == 0

    def test_same_decision_skipped(self):
        """A decision should not contradict itself."""
        decision = {
            "text": "implementar autenticação JWT",
            "source_ref": "github:living/delphos#10",
            "date": "2026-05-25",
            "source": "github",
            "confidence": 0.9,
        }
        contrs = detect_contradiction(decision, [decision])
        assert len(contrs) == 0

    def test_neutral_text_no_contradiction(self):
        """A neutral decision (no affirmation or negation) should not contradict."""
        new = {
            "text": "actualizar documentação da API",
            "source_ref": "github:living/delphos#10",
            "date": "2026-05-25",
            "source": "github",
            "confidence": 0.7,
        }
        existing = {
            "text": "implementar autenticação JWT",
            "source_ref": "github:living/delphos#5",
            "date": "2026-05-20",
            "source": "github",
            "confidence": 0.85,
        }
        contrs = detect_contradiction(new, [existing])
        assert len(contrs) == 0

    def test_severity_high_confidence(self):
        """High confidence decisions should have high severity."""
        new = {
            "text": "não fazer merge sem code review",
            "source_ref": "github:living/delphos#10",
            "date": "2026-05-25",
            "source": "github",
            "confidence": 0.9,
        }
        existing = {
            "text": "fazer merge sem code review para acelerar entregas",
            "source_ref": "github:living/delphos#5",
            "date": "2026-05-20",
            "source": "github",
            "confidence": 0.88,
        }
        contrs = detect_contradiction(new, [existing])
        assert len(contrs) == 1
        assert contrs[0].severity == "high"

    def test_severity_low_confidence(self):
        """Low confidence decisions should have low severity."""
        new = {
            "text": "não usar microservices",
            "source_ref": "github:living/delphos#10",
            "date": "2026-05-25",
            "source": "github",
            "confidence": 0.45,
        }
        existing = {
            "text": "usar microservices para scalability",
            "source_ref": "github:living/delphos#5",
            "date": "2026-05-20",
            "source": "github",
            "confidence": 0.45,
        }
        contrs = detect_contradiction(new, [existing])
        assert len(contrs) == 1
        assert contrs[0].severity == "low"


class TestCheckTopicForContradictions:
    def test_multiple_contradictions_found(self):
        entries = [
            {"text": "não usar autenticação JWT", "source_ref": "dec1", "date": "2026-05-01", "source": "github", "confidence": 0.8},
            {"text": "implementar autenticação JWT", "source_ref": "dec2", "date": "2026-05-10", "source": "github", "confidence": 0.85},
            {"text": "remover o módulo de billing", "source_ref": "dec3", "date": "2026-05-15", "source": "github", "confidence": 0.7},
            {"text": "manter o módulo de billing", "source_ref": "dec4", "date": "2026-05-20", "source": "github", "confidence": 0.75},
        ]
        contrs = check_topic_for_contradictions(entries)
        assert len(contrs) == 4  # 2 unique pairs × 2 directions
        # Each pair detected twice: (A vs B) and (B vs A)
        refs = {c.existing_ref for c in contrs}
        assert "dec1" in refs
        assert "dec2" in refs
        assert "dec3" in refs
        assert "dec4" in refs

    def test_empty_list(self):
        assert check_topic_for_contradictions([]) == []
