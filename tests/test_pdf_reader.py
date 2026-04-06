"""
Unit tests for PDFReader.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from src.utils.pdf_reader import PDFReader


@pytest.fixture
def reader():
    return PDFReader()


# ──────────────────────────────────────────────────────────────────────────────
# extract_text
# ──────────────────────────────────────────────────────────────────────────────

def test_extract_text_file_not_found(reader, tmp_path):
    missing = tmp_path / "ghost.pdf"
    with pytest.raises(FileNotFoundError, match="ghost.pdf"):
        reader.extract_text(missing)


def test_extract_text_returns_joined_pages(reader, tmp_path):
    fake_pdf = tmp_path / "empresa.pdf"
    fake_pdf.write_bytes(b"%PDF")  # must exist for the path check

    mock_page_1 = MagicMock()
    mock_page_1.get_text.return_value = "pagina uno"
    mock_page_2 = MagicMock()
    mock_page_2.get_text.return_value = "pagina dos"

    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 2
    mock_doc.__getitem__.side_effect = [mock_page_1, mock_page_2]

    with patch("src.utils.pdf_reader.fitz.open", return_value=mock_doc):
        result = reader.extract_text(fake_pdf)

    assert "pagina uno" in result
    assert "pagina dos" in result
    mock_doc.close.assert_called_once()


def test_extract_text_truncates_long_content(reader, tmp_path):
    fake_pdf = tmp_path / "large.pdf"
    fake_pdf.write_bytes(b"%PDF")

    long_text = "x" * 20_000

    mock_page = MagicMock()
    mock_page.get_text.return_value = long_text

    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.return_value = mock_page

    with patch("src.utils.pdf_reader.fitz.open", return_value=mock_doc):
        result = reader.extract_text(fake_pdf, max_chars=12_000)

    assert len(result) <= 12_000 + len("\n\n[... texto truncado ...]") + 5
    assert "texto truncado" in result


def test_extract_text_no_truncation_when_short(reader, tmp_path):
    fake_pdf = tmp_path / "short.pdf"
    fake_pdf.write_bytes(b"%PDF")

    short_text = "contenido breve"

    mock_page = MagicMock()
    mock_page.get_text.return_value = short_text

    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.return_value = mock_page

    with patch("src.utils.pdf_reader.fitz.open", return_value=mock_doc):
        result = reader.extract_text(fake_pdf)

    assert "texto truncado" not in result
    assert result.strip() == short_text


def test_extract_text_propagates_fitz_exception(reader, tmp_path):
    fake_pdf = tmp_path / "bad.pdf"
    fake_pdf.write_bytes(b"%PDF")

    with patch("src.utils.pdf_reader.fitz.open", side_effect=RuntimeError("corrupt")):
        with pytest.raises(RuntimeError, match="corrupt"):
            reader.extract_text(fake_pdf)


# ──────────────────────────────────────────────────────────────────────────────
# get_metadata
# ──────────────────────────────────────────────────────────────────────────────

def test_get_metadata_returns_page_count(reader, tmp_path):
    fake_pdf = tmp_path / "meta.pdf"
    fake_pdf.write_bytes(b"%PDF")

    mock_doc = MagicMock()
    mock_doc.metadata = {"title": "Reporte Anual", "author": "Empresa S.A."}
    mock_doc.__len__.return_value = 5

    with patch("src.utils.pdf_reader.fitz.open", return_value=mock_doc):
        meta = reader.get_metadata(fake_pdf)

    assert meta["page_count"] == 5
    assert meta["title"] == "Reporte Anual"
    mock_doc.close.assert_called_once()


def test_get_metadata_empty_metadata(reader, tmp_path):
    fake_pdf = tmp_path / "empty_meta.pdf"
    fake_pdf.write_bytes(b"%PDF")

    mock_doc = MagicMock()
    mock_doc.metadata = {}
    mock_doc.__len__.return_value = 3

    with patch("src.utils.pdf_reader.fitz.open", return_value=mock_doc):
        meta = reader.get_metadata(fake_pdf)

    assert meta["page_count"] == 3
