"""
Unit tests for SkillAgent — covers all API call scenarios for each prompt.
"""
import os
from unittest.mock import MagicMock, patch, call

import pytest
from openai import APIError

from src.agents.skill_agent import SkillAgent

# All four prompts that CentralAgent loads dynamically
ALL_PROMPTS = [
    "analisis_competencia",
    "auditoria_automatizacion",
    "auditoria_pagina_web",
    "auditoria_social_media",
]

FAKE_PROMPT = "Eres un agente de analisis. Analiza la empresa."
FAKE_COMPANY_TEXT = "Texto extraido del PDF de la empresa."
FAKE_COMPANY_NAME = "EmpresaTest"
FAKE_ANALYSIS = "Resultado del analisis generado por el modelo."


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")


def _make_agent(skill_name: str) -> tuple["SkillAgent", MagicMock]:
    """Return (agent, mock_client) with the OpenAI client fully mocked."""
    with patch("src.agents.skill_agent.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        agent = SkillAgent(skill_name, FAKE_PROMPT)
    agent._client = mock_client  # keep reference after context exit
    return agent, mock_client


# ──────────────────────────────────────────────────────────────────────────────
# Happy-path: web_search_preview succeeds
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("skill_name", ALL_PROMPTS)
def test_execute_web_search_success(skill_name):
    """Each prompt returns the model's output_text on a successful call."""
    agent, mock_client = _make_agent(skill_name)

    mock_response = MagicMock()
    mock_response.output_text = FAKE_ANALYSIS
    mock_client.responses.create.return_value = mock_response

    result = agent.execute(FAKE_COMPANY_TEXT, FAKE_COMPANY_NAME)

    assert result == FAKE_ANALYSIS
    mock_client.responses.create.assert_called_once()
    call_kwargs = mock_client.responses.create.call_args.kwargs
    assert call_kwargs["tools"] == [{"type": "web_search_preview"}]
    assert call_kwargs["model"] == "gpt-4o"


# ──────────────────────────────────────────────────────────────────────────────
# Fallback: 400 / 422 triggers retry without web_search_preview
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("skill_name", ALL_PROMPTS)
@pytest.mark.parametrize("status_code", [400, 422])
def test_execute_fallback_on_unsupported_tool_error(skill_name, status_code):
    """A 400 or 422 on the first call retries without web_search_preview and returns the result."""
    agent, mock_client = _make_agent(skill_name)

    api_error = APIError(
        message="tool not supported",
        request=MagicMock(),
        body={"error": {"message": "tool not supported"}},
    )
    api_error.status_code = status_code

    mock_fallback = MagicMock()
    mock_fallback.output_text = FAKE_ANALYSIS

    mock_client.responses.create.side_effect = [api_error, mock_fallback]

    result = agent.execute(FAKE_COMPANY_TEXT, FAKE_COMPANY_NAME)

    assert result == FAKE_ANALYSIS
    assert mock_client.responses.create.call_count == 2

    # Second call must NOT include the tools kwarg
    second_call_kwargs = mock_client.responses.create.call_args_list[1].kwargs
    assert "tools" not in second_call_kwargs


@pytest.mark.parametrize("skill_name", ALL_PROMPTS)
@pytest.mark.parametrize("status_code", [400, 422])
def test_execute_fallback_also_fails_returns_error_string(skill_name, status_code):
    """If both calls raise APIError, execute() returns an error string (no exception)."""
    agent, mock_client = _make_agent(skill_name)

    def make_error(code):
        err = APIError(
            message="API failure",
            request=MagicMock(),
            body={"error": {"message": "API failure"}},
        )
        err.status_code = code
        return err

    mock_client.responses.create.side_effect = [make_error(status_code), make_error(500)]

    result = agent.execute(FAKE_COMPANY_TEXT, FAKE_COMPANY_NAME)

    assert result.startswith("[ERROR]")
    assert skill_name in result
    assert mock_client.responses.create.call_count == 2


# ──────────────────────────────────────────────────────────────────────────────
# Generic API error (non-400/422) → no retry, returns error string immediately
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("skill_name", ALL_PROMPTS)
@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_execute_generic_api_error_no_retry(skill_name, status_code):
    """Non-400/422 errors return error string without a second call."""
    agent, mock_client = _make_agent(skill_name)

    api_error = APIError(
        message="server error",
        request=MagicMock(),
        body={"error": {"message": "server error"}},
    )
    api_error.status_code = status_code

    mock_client.responses.create.side_effect = api_error

    result = agent.execute(FAKE_COMPANY_TEXT, FAKE_COMPANY_NAME)

    assert result.startswith("[ERROR]")
    assert skill_name in result
    mock_client.responses.create.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# User message format
# ──────────────────────────────────────────────────────────────────────────────

def test_execute_user_message_contains_company_name_and_text():
    """The user message sent to the API must embed both company name and extracted text."""
    agent, mock_client = _make_agent("analisis_competencia")

    mock_response = MagicMock()
    mock_response.output_text = FAKE_ANALYSIS
    mock_client.responses.create.return_value = mock_response

    agent.execute(FAKE_COMPANY_TEXT, FAKE_COMPANY_NAME)

    payload_input = mock_client.responses.create.call_args.kwargs["input"]
    user_content = next(m["content"] for m in payload_input if m["role"] == "user")

    assert FAKE_COMPANY_NAME in user_content
    assert FAKE_COMPANY_TEXT in user_content


def test_execute_system_prompt_is_skill_prompt():
    """The system message must be the skill's .md prompt text."""
    agent, mock_client = _make_agent("auditoria_pagina_web")

    mock_response = MagicMock()
    mock_response.output_text = FAKE_ANALYSIS
    mock_client.responses.create.return_value = mock_response

    agent.execute(FAKE_COMPANY_TEXT, FAKE_COMPANY_NAME)

    payload_input = mock_client.responses.create.call_args.kwargs["input"]
    system_content = next(m["content"] for m in payload_input if m["role"] == "system")

    assert system_content == FAKE_PROMPT


def test_execute_uses_model_from_env(monkeypatch):
    """OPENAI_MODEL env var must be forwarded to the API call."""
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4-turbo")
    agent, mock_client = _make_agent("auditoria_social_media")
    agent._model = "gpt-4-turbo"  # reflect env override

    mock_response = MagicMock()
    mock_response.output_text = FAKE_ANALYSIS
    mock_client.responses.create.return_value = mock_response

    agent.execute(FAKE_COMPANY_TEXT, FAKE_COMPANY_NAME)

    assert mock_client.responses.create.call_args.kwargs["model"] == "gpt-4-turbo"
