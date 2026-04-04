"""
PDF Reader — uses PyMuPDF (fitz) to extract text from company PDFs.
"""
import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFReader:
    """Extracts text from PDF files using PyMuPDF."""

    def extract_text(self, pdf_path: str | Path, max_chars: int = 12_000) -> str:
        """
        Extract all text from a PDF and return it as a single string.

        Args:
            pdf_path: Path to the PDF file.
            max_chars: Truncate to this many characters to stay inside API limits.

        Returns:
            Extracted text (truncated if necessary).
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            doc = fitz.open(str(pdf_path))
            pages_text: list[str] = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                pages_text.append(page.get_text("text"))

            doc.close()

            full_text = "\n\n".join(pages_text).strip()
            if len(full_text) > max_chars:
                logger.warning(
                    "PDF text truncated from %d to %d characters: %s",
                    len(full_text),
                    max_chars,
                    pdf_path.name,
                )
                full_text = full_text[:max_chars] + "\n\n[... texto truncado ...]"

            return full_text

        except Exception as exc:
            logger.error("Error reading PDF %s: %s", pdf_path, exc)
            raise

    def get_metadata(self, pdf_path: str | Path) -> dict:
        """Return basic metadata (title, author, page count) from a PDF."""
        pdf_path = Path(pdf_path)
        doc = fitz.open(str(pdf_path))
        meta = doc.metadata or {}
        meta["page_count"] = len(doc)
        doc.close()
        return meta
