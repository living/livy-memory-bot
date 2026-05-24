import pytest
from vault.qw2.filter import should_skip

@pytest.mark.parametrize("text,expected_skip,reason", [
    # Trello: DONE cards sao dados operacionais — nenhum filtro DONE_CARD_RE
    # Trello filtra no fetch (card utilidade), nao no should_skip
    ("foi decidido que...", False, "real decision"),
    # Length
    ("x" * 49, True, "49 chars — too short"),
    ("x" * 50, False, "50 chars — exact threshold"),
    ("x" * 51, False, "51 chars — OK"),
    # Confidence
    ({"text": "x" * 51, "confidence": 0.74}, True, "confidence below 0.75"),
    ({"text": "x" * 51, "confidence": 0.75}, False, "confidence at threshold"),
    # No decisions
    ("Sem decisões registradas", True, "TLDV no-decisions placeholder"),
    ("sem decisões registradas", True, "lowercase variant"),
    # Status meeting override: high confidence (>=0.90) survives filter
    ({"text": "x" * 51, "confidence": 0.92, "_is_status_meeting": True}, False, "Status meeting with high confidence survives"),
    ({"text": "x" * 51, "confidence": 0.89, "_is_status_meeting": True}, True, "Status meeting with low confidence still filtered"),
])
def test_should_skip(text, expected_skip, reason):
    if isinstance(text, dict):
        skip, _ = should_skip(text)
    else:
        skip, _ = should_skip({"text": text, "confidence": 0.90})
    assert skip == expected_skip, reason
