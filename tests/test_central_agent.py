"""
Unit tests for CentralAgent — skill loading and full processing cycle.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from src.agents.central_agent import CentralAgent

PROMPTS = {
    "analisis_competencia": "Prompt de analisis de competencia.",
    "auditoria_automatizacion": "Prompt de auditoria de automatizacion.",
    "auditoria_pagina_web": "Prompt de auditoria de pagina web.",
    "auditoria_social_media": "Prompt de auditoria de social media.",
}

FAKE_COMPANY_TEXT = "Contenido extraido del PDF."


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_central_agent(tmp_path: Path) -> CentralAgent:
    prompts_dir = tmp_path / "prompts"
    empresas_dir = tmp_path / "empresas"
    outputs_dir = tmp_path / "outputs"
    prompts_dir.mkdir()
    empresas_dir.mkdir()
    outputs_dir.mkdir()
    return CentralAgent(prompts_dir, empresas_dir, outputs_dir)


def _write_prompts(agent: CentralAgent) -> None:
    for name, content in PROMPTS.items():
        (agent.prompts_dir / f"{name}.md").write_text(content, encoding="utf-8")


def _write_fake_pdf(agent: CentralAgent, name: str) -> Path:
    pdf_path = agent.empresas_dir / f"{name}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")
    return pdf_path


# ──────────────────────────────────────────────────────────────────────────────
# load_skills
# ──────────────────────────────────────────────────────────────────────────────

@patch("src.agents.central_agent.SkillAgent")
def test_load_skills_creates_one_agent_per_prompt(MockSkillAgent, tmp_path):
    """load_skills() should create a SkillAgent for each .md file found."""
    ca = _make_central_agent(tmp_path)
    _write_prompts(ca)

    ca.load_skills()

    assert set(ca._skills.keys()) == set(PROMPTS.keys())
    assert set(ca._agents.keys()) == set(PROMPTS.keys())
    assert MockSkillAgent.call_count == len(PROMPTS)


@patch("src.agents.central_agent.SkillAgent")
def test_load_skills_passes_correct_prompt_text(MockSkillAgent, tmp_path):
    """Each SkillAgent must receive the exact text of its .md file."""
    ca = _make_central_agent(tmp_path)
    _write_prompts(ca)

    ca.load_skills()

    for ctor_call in MockSkillAgent.call_args_list:
        skill_name, prompt_text = ctor_call.args
        assert prompt_text == PROMPTS[skill_name]


@patch("src.agents.central_agent.SkillAgent")
def test_load_skills_clears_previous_state(MockSkillAgent, tmp_path):
    """Calling load_skills() twice should not accumulate agents."""
    ca = _make_central_agent(tmp_path)
    _write_prompts(ca)

    ca.load_skills()
    ca.load_skills()

    assert len(ca._agents) == len(PROMPTS)
    assert MockSkillAgent.call_count == len(PROMPTS) * 2


def test_load_skills_missing_directory_logs_warning(tmp_path, caplog):
    ca = _make_central_agent(tmp_path)
    ca.prompts_dir = tmp_path / "nonexistent"

    with caplog.at_level("WARNING"):
        ca.load_skills()

    assert ca._agents == {}
    assert "not found" in caplog.text.lower() or "Prompts directory" in caplog.text


def test_load_skills_empty_directory_logs_warning(tmp_path, caplog):
    ca = _make_central_agent(tmp_path)
    # prompts_dir exists but has no .md files

    with caplog.at_level("WARNING"):
        ca.load_skills()

    assert ca._agents == {}
    assert "No .md" in caplog.text or "skill" in caplog.text.lower()


# ──────────────────────────────────────────────────────────────────────────────
# run_cycle
# ──────────────────────────────────────────────────────────────────────────────

@patch("src.agents.central_agent.SkillAgent")
def test_run_cycle_yields_results_for_each_company(MockSkillAgent, tmp_path):
    """run_cycle() should yield (company_name, results_dict) for every PDF."""
    ca = _make_central_agent(tmp_path)
    _write_prompts(ca)

    companies = ["EmpresaA", "EmpresaB"]
    for name in companies:
        _write_fake_pdf(ca, name)

    # Make every agent return a predictable string
    mock_agent_instance = MagicMock()
    mock_agent_instance.execute.return_value = "resultado"
    MockSkillAgent.return_value = mock_agent_instance

    with patch.object(ca._pdf_reader, "extract_text", return_value=FAKE_COMPANY_TEXT):
        results = list(ca.run_cycle())

    yielded_companies = [r[0] for r in results]
    assert set(yielded_companies) == set(companies)

    for _, result_dict in results:
        assert set(result_dict.keys()) == set(PROMPTS.keys())
        assert all(v == "resultado" for v in result_dict.values())


@patch("src.agents.central_agent.SkillAgent")
def test_run_cycle_calls_execute_for_all_prompts(MockSkillAgent, tmp_path):
    """Each SkillAgent.execute() must be called once per company."""
    ca = _make_central_agent(tmp_path)
    _write_prompts(ca)
    _write_fake_pdf(ca, "EmpresaX")

    mock_agent_instance = MagicMock()
    mock_agent_instance.execute.return_value = "ok"
    MockSkillAgent.return_value = mock_agent_instance

    with patch.object(ca._pdf_reader, "extract_text", return_value=FAKE_COMPANY_TEXT):
        list(ca.run_cycle())

    assert mock_agent_instance.execute.call_count == len(PROMPTS)


def test_run_cycle_no_agents_aborts(tmp_path, caplog):
    """If no skills are loaded, run_cycle() should yield nothing and log an error."""
    ca = _make_central_agent(tmp_path)
    # No .md files → _agents stays empty

    with caplog.at_level("ERROR"):
        results = list(ca.run_cycle())

    assert results == []
    assert "No skills" in caplog.text or "aborting" in caplog.text.lower()


@patch("src.agents.central_agent.SkillAgent")
def test_run_cycle_no_pdfs_yields_nothing(MockSkillAgent, tmp_path, caplog):
    """If empresas_dir has no PDFs, run_cycle() should yield nothing."""
    ca = _make_central_agent(tmp_path)
    _write_prompts(ca)
    MockSkillAgent.return_value = MagicMock()

    with caplog.at_level("WARNING"):
        results = list(ca.run_cycle())

    assert results == []
    assert "No PDF" in caplog.text or "pdf" in caplog.text.lower()


@patch("src.agents.central_agent.SkillAgent")
def test_run_cycle_pdf_read_error_skips_company(MockSkillAgent, tmp_path, caplog):
    """A PDF that cannot be read should be skipped; other companies still process."""
    ca = _make_central_agent(tmp_path)
    _write_prompts(ca)
    _write_fake_pdf(ca, "Buena")
    _write_fake_pdf(ca, "Mala")

    mock_agent_instance = MagicMock()
    mock_agent_instance.execute.return_value = "resultado"
    MockSkillAgent.return_value = mock_agent_instance

    def fake_extract(path):
        if "Mala" in str(path):
            raise RuntimeError("PDF corrupto")
        return FAKE_COMPANY_TEXT

    with patch.object(ca._pdf_reader, "extract_text", side_effect=fake_extract):
        with caplog.at_level("ERROR"):
            results = list(ca.run_cycle())

    yielded_companies = [r[0] for r in results]
    assert "Buena" in yielded_companies
    assert "Mala" not in yielded_companies
    assert "Mala" in caplog.text
