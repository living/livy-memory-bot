import os
import pytest


def test_extract_summary_from_transcript():
    """Given a transcript text, extract summary and decisions (mocked LLM)."""
    from unittest.mock import patch
    from vault.enrich.llm_summarize import extract_meeting_insights

    transcript = """
    Lincoln: Vamos discutir o deploy do voice commerce.
    Marcio: O deploy em UAT ficou estável, sem erros há 3 dias.
    Esteves: Podemos ir para prod na segunda.
    Lincoln: Ok, aprovado. Marcio, prepara o release notes.
    Marcio: Vou preparar até sexta.
    """

    mock_response = '{"summary": "Discussão sobre deploy do voice commerce em produção.", "decisions": ["Aprovar deploy do voice commerce em prod na segunda", "Marcio prepara release notes até sexta"]}'
    with patch("vault.enrich.llm_summarize._call_llm", return_value=mock_response):
        result = extract_meeting_insights(transcript)

    assert "summary" in result
    assert "decisions" in result
    assert isinstance(result["decisions"], list)
    assert len(result["decisions"]) >= 1


def test_extract_summary_empty_transcript():
    from vault.enrich.llm_summarize import extract_meeting_insights
    result = extract_meeting_insights("")
    assert result["summary"] == ""
    assert result["decisions"] == []


def test_extract_summary_json_parse_fallback():
    """Test JSON extraction from markdown code block."""
    from unittest.mock import patch
    from vault.enrich.llm_summarize import extract_meeting_insights

    transcript = "Some discussion text."
    mock_response = '```json\n{"summary": "Test summary", "decisions": ["dec1"]}\n```'
    with patch("vault.enrich.llm_summarize._call_llm", return_value=mock_response):
        result = extract_meeting_insights(transcript)
    assert result["summary"] == "Test summary"
    assert result["decisions"] == ["dec1"]
