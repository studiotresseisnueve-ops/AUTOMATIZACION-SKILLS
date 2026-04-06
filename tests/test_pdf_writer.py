"""
Unit tests for PDFReportWriter.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.utils.pdf_writer import PDFReportWriter, _safe


@pytest.fixture
def writer():
    return PDFReportWriter()


# ──────────────────────────────────────────────────────────────────────────────
# _safe helper
# ──────────────────────────────────────────────────────────────────────────────

def test_safe_passes_ascii():
    assert _safe("hello world") == "hello world"


def test_safe_replaces_non_latin1_chars():
    result = _safe("cafe\u2019s")   # right-single-quote is outside latin-1
    assert isinstance(result, str)
    assert "cafe" in result


# ──────────────────────────────────────────────────────────────────────────────
# generate_report — file creation
# ──────────────────────────────────────────────────────────────────────────────

def test_generate_report_creates_output_file(writer, tmp_path):
    output_path = tmp_path / "reports" / "test_report.pdf"
    writer.generate_report(
        output_path=output_path,
        company_name="EmpresaTest",
        skill_name="auditoria_pagina_web",
        content="## Resumen\nContenido de prueba.",
    )
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_generate_report_creates_missing_parent_dirs(writer, tmp_path):
    output_path = tmp_path / "a" / "b" / "c" / "report.pdf"
    writer.generate_report(
        output_path=output_path,
        company_name="Empresa",
        skill_name="analisis_competencia",
        content="Contenido.",
    )
    assert output_path.exists()


# ──────────────────────────────────────────────────────────────────────────────
# generate_report — content variants
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("skill_name", [
    "analisis_competencia",
    "auditoria_automatizacion",
    "auditoria_pagina_web",
    "auditoria_social_media",
])
def test_generate_report_all_skill_names(writer, tmp_path, skill_name):
    """Each skill name must produce a valid PDF without errors."""
    output_path = tmp_path / f"{skill_name}_report.pdf"
    writer.generate_report(
        output_path=output_path,
        company_name="EmpresaDemo",
        skill_name=skill_name,
        content=f"# Analisis\n## Seccion\n- Bullet uno\n- Bullet dos\nTexto normal.",
    )
    assert output_path.exists()


def test_generate_report_with_top_heading(writer, tmp_path):
    output_path = tmp_path / "heading.pdf"
    writer.generate_report(
        output_path=output_path,
        company_name="Empresa",
        skill_name="auditoria_social_media",
        content="# Titulo Principal\nParrafo debajo del titulo.",
    )
    assert output_path.exists()


def test_generate_report_with_section_heading(writer, tmp_path):
    output_path = tmp_path / "section.pdf"
    writer.generate_report(
        output_path=output_path,
        company_name="Empresa",
        skill_name="auditoria_automatizacion",
        content="## Seccion de Auditoria\nContenido de la seccion.",
    )
    assert output_path.exists()


def test_generate_report_with_bullets(writer, tmp_path):
    output_path = tmp_path / "bullets.pdf"
    writer.generate_report(
        output_path=output_path,
        company_name="Empresa",
        skill_name="analisis_competencia",
        content="- Punto uno\n* Punto dos\n- Punto tres",
    )
    assert output_path.exists()


def test_generate_report_with_empty_lines(writer, tmp_path):
    output_path = tmp_path / "empty_lines.pdf"
    writer.generate_report(
        output_path=output_path,
        company_name="Empresa",
        skill_name="auditoria_pagina_web",
        content="Parrafo uno\n\n\nParrafo dos",
    )
    assert output_path.exists()


def test_generate_report_with_special_characters(writer, tmp_path):
    """Non-latin-1 characters must not raise exceptions."""
    output_path = tmp_path / "special.pdf"
    writer.generate_report(
        output_path=output_path,
        company_name="Empresa \u00e9\u00e0\u00fc",
        skill_name="auditoria_social_media",
        content="Contenido con emojis \U0001f4ca y simbolos \u2019\u201c\u201d.",
    )
    assert output_path.exists()
