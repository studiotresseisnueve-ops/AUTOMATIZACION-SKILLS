"""
PDF Report Writer — generates professional PDF reports using fpdf2.
"""
import logging
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

logger = logging.getLogger(__name__)

# Palette
COLOR_PRIMARY = (30, 80, 160)     # deep blue
COLOR_SECONDARY = (60, 60, 60)    # dark grey
COLOR_ACCENT = (220, 230, 245)    # light blue fill
COLOR_LINE = (180, 180, 180)      # light grey rule


def _safe(text: str) -> str:
    """Encode text to latin-1, replacing unmappable characters."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


class PDFReportWriter:
    """Generates a structured, professional PDF report for a single skill result."""

    def generate_report(
        self,
        output_path: str | Path,
        company_name: str,
        skill_name: str,
        content: str,
    ) -> None:
        """
        Build and save a PDF report.

        Args:
            output_path: Destination file path (created if missing).
            company_name: Name of the analysed company.
            skill_name: Name of the skill / analysis type.
            content: Full text output from the skill agent.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(left=18, top=18, right=18)
        pdf.add_page()

        self._draw_header(pdf, company_name, skill_name)
        self._draw_content(pdf, content)
        self._draw_footer(pdf)

        pdf.output(str(output_path))
        logger.info("PDF saved: %s", output_path)

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _draw_header(self, pdf: FPDF, company_name: str, skill_name: str) -> None:
        # Background banner
        pdf.set_fill_color(*COLOR_PRIMARY)
        pdf.rect(0, 0, 210, 38, "F")

        # Main title
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_xy(18, 8)
        title = _safe(skill_name.replace("_", " ").title())
        pdf.cell(174, 10, title, ln=True, align="C")

        # Company name
        pdf.set_font("Helvetica", "", 11)
        pdf.set_xy(18, 20)
        pdf.cell(174, 8, _safe(f"Empresa: {company_name}"), ln=True, align="C")

        # Timestamp
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_xy(18, 29)
        ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        pdf.cell(174, 7, _safe(f"Generado: {ts}"), ln=True, align="C")

        # Reset colour and move cursor below banner
        pdf.set_text_color(*COLOR_SECONDARY)
        pdf.set_xy(18, 44)

    def _draw_content(self, pdf: FPDF, content: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COLOR_SECONDARY)

        for raw_line in content.split("\n"):
            line = raw_line.rstrip()

            if line.startswith("## "):
                # Section heading
                self._section_heading(pdf, line[3:])
            elif line.startswith("# "):
                # Top-level heading
                self._top_heading(pdf, line[2:])
            elif line.startswith("- ") or line.startswith("* "):
                # Bullet point
                self._bullet(pdf, line[2:])
            elif line.strip() == "":
                pdf.ln(3)
            else:
                # Normal paragraph text
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5.5, _safe(line))
                pdf.ln(1)

    def _top_heading(self, pdf: FPDF, text: str) -> None:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.multi_cell(0, 7, _safe(text))
        # Underline rule
        y = pdf.get_y()
        pdf.set_draw_color(*COLOR_PRIMARY)
        pdf.set_line_width(0.5)
        pdf.line(18, y, 192, y)
        pdf.ln(3)
        pdf.set_text_color(*COLOR_SECONDARY)

    def _section_heading(self, pdf: FPDF, text: str) -> None:
        pdf.ln(2)
        pdf.set_fill_color(*COLOR_ACCENT)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*COLOR_PRIMARY)
        pdf.multi_cell(0, 7, _safe(f"  {text}"), fill=True)
        pdf.ln(2)
        pdf.set_text_color(*COLOR_SECONDARY)

    def _bullet(self, pdf: FPDF, text: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(22)
        pdf.cell(4, 5.5, _safe("\u2022"), ln=False)
        pdf.multi_cell(0, 5.5, _safe(text))
        pdf.ln(0.5)

    def _draw_footer(self, pdf: FPDF) -> None:
        pdf.set_y(-14)
        pdf.set_draw_color(*COLOR_LINE)
        pdf.set_line_width(0.3)
        pdf.line(18, pdf.get_y(), 192, pdf.get_y())
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 6, _safe("Generado automaticamente por el Sistema de Agentes Autonomos"), align="C")
